from pathlib import Path
from threading import Event

import pytest

from rename_date.controllers import app_controller as controller_module
from rename_date.controllers.app_controller import AppController
from rename_date.models.execution_history import ExecutionHistory
from rename_date.models.output_template_entry import OutputTemplateEntry
from rename_date.models.pattern_entry import PatternEntry
from rename_date.models.rename_item import ItemStatus, RenameItem
from rename_date.views.config_frame import resolve_selected_indices
from rename_date.services.validation import (
	InvalidPatternError,
	InvalidTemplateError,
	compile_pattern,
)
from rename_date.services.preset_io import (
	ConflictPolicy,
	create_import_plan,
	resolve_import_plan,
)


class FakeConfigFrame:
	def __init__(self) -> None:
		self.targets: list[Path] = []
		self.selected_patterns: list[PatternEntry] = []
		self.selected_template: OutputTemplateEntry | None = None
		self.selected_range_template: OutputTemplateEntry | None = None
		self.selected_month_template: OutputTemplateEntry | None = None
		self.callbacks = {}
		self.patterns = []
		self.templates = []
		self.range_templates = []
		self.month_templates = []

	def set_patterns(self, entries, *, preserve_selection=False):
		selected_names = (
			{entry.name for entry in self.selected_patterns}
			if preserve_selection
			else set()
		)
		self.patterns = list(entries)
		if preserve_selection:
			self.selected_patterns = [
				entry for entry in self.patterns if entry.name in selected_names
			]
		else:
			self.selected_patterns = self.patterns[:1]

	def set_templates(self, entries, *, preserve_selection=False):
		selected_name = (
			self.selected_template.name
			if preserve_selection and self.selected_template is not None
			else None
		)
		self.templates = list(entries)
		if preserve_selection:
			self.selected_template = next(
				(entry for entry in self.templates if entry.name == selected_name),
				None,
			)
		else:
			self.selected_template = self.templates[0] if self.templates else None

	def set_range_templates(self, entries, *, preserve_selection=False):
		selected_name = (
			self.selected_range_template.name
			if preserve_selection and self.selected_range_template is not None
			else None
		)
		self.range_templates = list(entries)
		if preserve_selection:
			self.selected_range_template = next(
				(entry for entry in self.range_templates if entry.name == selected_name),
				None,
			)
		else:
			self.selected_range_template = (
				self.range_templates[0] if self.range_templates else None
			)

	def get_preset_count(self, kind):
		return {
			"pattern": len(self.patterns),
			"single_template": len(self.templates),
			"range_template": len(self.range_templates),
			"month_template": len(self.month_templates),
		}[kind]

	def set_callbacks(self, **callbacks):
		self.callbacks.update(callbacks)

	def get_targets(self):
		return list(self.targets)

	def get_selected_patterns(self):
		return list(self.selected_patterns)

	def get_selected_template(self):
		return self.selected_template

	def get_selected_range_template(self):
		return self.selected_range_template

	def set_month_templates(self, entries, *, preserve_selection=False):
		selected_name = (
			self.selected_month_template.name
			if preserve_selection and self.selected_month_template is not None
			else None
		)
		self.month_templates = list(entries)
		if preserve_selection:
			self.selected_month_template = next(
				(entry for entry in self.month_templates if entry.name == selected_name),
				None,
			)
		else:
			self.selected_month_template = (
				self.month_templates[0] if self.month_templates else None
			)

	def get_selected_month_template(self):
		return self.selected_month_template


class FakePreviewFrame:
	def __init__(self) -> None:
		self.items = []
		self.base_dir = None

	def set_items(self, items, base_dir=None):
		self.items = list(items)
		self.base_dir = base_dir

	def clear(self):
		self.items = []
		self.base_dir = None


class FakeActionFrame:
	def __init__(self) -> None:
		self.callbacks = {}
		self.processing = False
		self.progress = 0
		self.status = ""
		self.counts = None
		self.undo_enabled = False
		self.log_enabled = True

	def set_callbacks(self, **callbacks):
		self.callbacks.update(callbacks)

	def set_processing(self, value):
		self.processing = value

	def set_progress(self, value):
		self.progress = value

	def set_status(self, value):
		self.status = value

	def set_counts(self, executable, invalid, total):
		self.counts = (executable, invalid, total)

	def set_undo_enabled(self, value):
		self.undo_enabled = value

	def get_log_enabled(self):
		return self.log_enabled


class FakeLogFrame:
	def __init__(self) -> None:
		self.callbacks = {}
		self.entries = []

	def set_callbacks(self, **callbacks):
		self.callbacks.update(callbacks)

	def set_entries(self, entries):
		self.entries = list(entries)


class FakeWindow:
	def __init__(self) -> None:
		self.config_frame = FakeConfigFrame()
		self.preview_frame = FakePreviewFrame()
		self.action_frame = FakeActionFrame()
		self.log_frame = FakeLogFrame()
		self.protocols = {}
		self.destroyed = False
		self.preset_callbacks = {}
		self.export_path: Path | None = None
		self.import_path: Path | None = None
		self.export_path_requests = []
		self.import_path_requests = []
		self.conflict_policy = ConflictPolicy.SKIP
		self.conflict_policy_requests = []

	def after(self, delay, callback, *args):
		callback(*args)

	def protocol(self, name, callback):
		self.protocols[name] = callback

	def destroy(self):
		self.destroyed = True

	def set_preset_callbacks(self, **callbacks):
		self.preset_callbacks.update(callbacks)

	def choose_preset_export_path(self, kind):
		self.export_path_requests.append(kind)
		return self.export_path

	def choose_preset_import_path(self, kind):
		self.import_path_requests.append(kind)
		return self.import_path

	def choose_preset_conflict_policy(self, conflicting_names):
		self.conflict_policy_requests.append(conflicting_names)
		return self.conflict_policy


class ImmediateThread:
	instances = []

	def __init__(self, target, args=(), daemon=False):
		self.target = target
		self.args = args
		self.daemon = daemon
		self.instances.append(self)

	def start(self):
		self.target(*self.args)


class FakePatternService:
	def __init__(self, entries):
		self.entries = list(entries)
		self.error: Exception | None = None
		self.base_dir = Path(".")
		self.export_calls = []
		self.import_entries = []
		self.prepare_calls = []
		self.apply_calls = []

	def load(self):
		return list(self.entries)

	def export_to_json(self, path):
		if self.error:
			raise self.error
		self.export_calls.append(path)

	def import_from_json(self, path):
		if self.error:
			raise self.error
		self.entries.extend(self.import_entries)
		return list(self.entries)

	def prepare_import(self, path):
		self.prepare_calls.append(path)
		if self.error:
			raise self.error
		return create_import_plan(self.entries, self.import_entries)

	def apply_import(self, plan, policy):
		self.apply_calls.append((plan, policy))
		if self.error:
			raise self.error
		result = resolve_import_plan(plan, policy)
		if result.changed:
			self.entries = list(result.updated_entries)
		return result

	def upsert(self, entry):
		if self.error:
			raise self.error
		self.entries = [item for item in self.entries if item.name != entry.name] + [entry]
		return list(self.entries)

	def delete(self, name):
		if self.error:
			raise self.error
		remaining = [item for item in self.entries if item.name != name]
		if not remaining:
			raise ValueError("last pattern")
		self.entries = remaining
		return list(self.entries)


class FakeTemplateService:
	def __init__(self, entries):
		self.entries = list(entries)
		self.error: Exception | None = None
		self.import_entries = []
		self.base_dir = Path(".")
		self.prepare_calls = []
		self.apply_calls = []

	def import_from_json(self, path):
		if self.error:
			raise self.error
		self.entries.extend(self.import_entries)
		return list(self.entries)

	def prepare_import(self, path):
		self.prepare_calls.append(path)
		if self.error:
			raise self.error
		return create_import_plan(self.entries, self.import_entries)

	def apply_import(self, plan, policy):
		self.apply_calls.append((plan, policy))
		if self.error:
			raise self.error
		result = resolve_import_plan(plan, policy)
		if result.changed:
			self.entries = list(result.updated_entries)
		return result

	def load(self):
		return list(self.entries)

	def upsert(self, entry):
		if self.error:
			raise self.error
		self.entries = [item for item in self.entries if item.name != entry.name] + [entry]
		return list(self.entries)

	def delete(self, name):
		if self.error:
			raise self.error
		remaining = [item for item in self.entries if item.name != name]
		if not remaining:
			raise ValueError("last template")
		self.entries = remaining
		return list(self.entries)


class FakeRangeTemplateService(FakeTemplateService):
	pass


class FakeMonthTemplateService(FakeTemplateService):
	pass


class FakeScannerService:
	def __init__(self, items):
		self.items = list(items)
		self.calls = []

	def scan(
		self,
		targets,
		patterns,
		output_template,
		cancel_event=None,
		progress_callback=None,
		range_output_template="{Y}{M}{D}-{Y2}{M2}{D2}",
		*,
		month_output_template="{Y}-{M}",
	):
		self.calls.append(
			(
				list(targets),
				list(patterns),
				output_template,
				range_output_template,
				cancel_event,
				month_output_template,
			)
		)
		for pattern in patterns:
			compile_pattern(pattern)
		if progress_callback:
			progress_callback(1, 1)
		return list(self.items)


class FakeRenameService:
	def __init__(self, result_items):
		self.result_items = result_items
		self.calls = []

	def execute(self, items, cancel_event=None, progress_callback=None):
		self.calls.append((items, cancel_event))
		if progress_callback:
			progress_callback(len(items), len(items))
		history = ExecutionHistory(items=list(self.result_items))
		return list(items), history


class FakeUndoService:
	def __init__(self):
		self.histories = []
		self.calls = []
		self.restored_items = []

	def push(self, history):
		self.histories.append(history)

	def has_history(self):
		return bool(self.histories)

	def undo(self, cancel_event=None, progress_callback=None):
		self.calls.append(cancel_event)
		if progress_callback and self.restored_items:
			progress_callback(len(self.restored_items), len(self.restored_items))
		self.histories.pop()
		return list(self.restored_items)


class FakeLogService:
	def __init__(self):
		self.rename_calls = []
		self.undo_calls = []
		self.base_dir = Path(".")

	def log_rename(self, items, session_id):
		self.rename_calls.append((list(items), session_id))

	def log_undo(self, items, session_id):
		self.undo_calls.append((list(items), session_id))

	def read_entries(self):
		return []


def make_controller(monkeypatch, tmp_path):
	monkeypatch.setattr(controller_module.threading, "Thread", ImmediateThread)
	pattern = PatternEntry("default", r"\((\d{4})\.(\d{1,2})\.(\d{1,2})\)")
	template = OutputTemplateEntry("default", "{Y}{M}{D}")
	range_template = OutputTemplateEntry("range default", "{Y}{M}{D}-{Y2}{M2}{D2}")
	month_template = OutputTemplateEntry("month default", "{Y}-{M}")
	source = tmp_path / "before.txt"
	target = tmp_path / "after.txt"
	item = RenameItem(source, target)
	window = FakeWindow()
	window.config_frame.targets = [tmp_path]
	window.config_frame.selected_patterns = [pattern]
	window.config_frame.selected_template = template
	window.config_frame.selected_range_template = range_template
	window.config_frame.selected_month_template = month_template
	scanner = FakeScannerService([item])
	rename = FakeRenameService([item])
	undo = FakeUndoService()
	log = FakeLogService()
	patterns = FakePatternService([pattern])
	templates = FakeTemplateService([template])
	range_templates = FakeRangeTemplateService([range_template])
	month_templates = FakeMonthTemplateService([month_template])
	patterns.base_dir = tmp_path / "config"
	templates.base_dir = tmp_path / "config"
	range_templates.base_dir = tmp_path / "config"
	month_templates.base_dir = tmp_path / "config"
	controller = AppController(
		window,
		scanner,
		rename,
		undo,
		log,
		patterns,
		templates,
		range_templates,
		month_templates,
	)
	return (
		controller,
		window,
		scanner,
		rename,
		undo,
		log,
		patterns,
		templates,
		range_templates,
		pattern,
		template,
		item,
	)


def test_preview_uses_services_and_updates_view(monkeypatch, tmp_path):
	controller, window, scanner, *_ = make_controller(monkeypatch, tmp_path)

	controller._on_preview_request()

	assert len(scanner.calls) == 1
	assert scanner.calls[0][1] == [window.config_frame.selected_patterns[0].pattern]
	assert scanner.calls[0][3] == "{Y}{M}{D}-{Y2}{M2}{D2}"
	assert window.preview_frame.items
	assert window.preview_frame.base_dir == tmp_path
	assert window.action_frame.counts == (1, 0, 1)
	assert window.action_frame.processing is False


def test_preview_warns_without_range_template(monkeypatch, tmp_path):
	controller, window, scanner, *_ = make_controller(monkeypatch, tmp_path)
	warnings = []
	monkeypatch.setattr(
		controller_module.messagebox,
		"showwarning",
		lambda *args, **kwargs: warnings.append(args),
	)
	window.config_frame.selected_range_template = None

	controller._on_preview_request()

	assert len(warnings) == 1
	assert scanner.calls == []


def test_preview_requires_month_template_for_month_pattern(monkeypatch, tmp_path):
	controller, window, scanner, *_ = make_controller(monkeypatch, tmp_path)
	warnings = []
	monkeypatch.setattr(
		controller_module.messagebox,
		"showwarning",
		lambda *args, **kwargs: warnings.append(args),
	)
	window.config_frame.selected_patterns = [
		PatternEntry("year-month", r"(\d{4})\.(\d{1,2})")
	]
	window.config_frame.selected_month_template = None

	controller._on_preview_request()

	assert len(warnings) == 1
	assert "年月用" in warnings[0][1]
	assert scanner.calls == []


def test_preview_uses_default_month_template_when_no_month_pattern(
	monkeypatch,
	tmp_path,
):
	controller, window, scanner, *_ = make_controller(monkeypatch, tmp_path)
	window.config_frame.selected_month_template = None

	controller._on_preview_request()

	assert scanner.calls[0][5] == "{Y}-{M}"


def test_invalid_pattern_error_precedes_missing_month_template_warning(
	monkeypatch,
	tmp_path,
):
	controller, window, scanner, rename, *_ = make_controller(monkeypatch, tmp_path)
	controller._on_preview_request()
	warnings = []
	errors = []
	monkeypatch.setattr(
		controller_module.messagebox,
		"showwarning",
		lambda *args, **kwargs: warnings.append(args),
	)
	monkeypatch.setattr(
		controller_module.messagebox,
		"showerror",
		lambda *args, **kwargs: errors.append(args),
	)
	window.config_frame.selected_patterns = [
		PatternEntry("year-month", r"(\d{4})\.(\d{1,2})"),
		PatternEntry("invalid", r"(\d{1,2})"),
	]
	window.config_frame.selected_month_template = None

	controller._on_preview_request()
	controller._on_execute()

	assert len(warnings) == 1
	assert "年月用" not in warnings[0][1]
	assert errors and errors[0][0] == "パターンエラー"
	assert controller._last_items == []
	assert rename.calls == []
	assert len(scanner.calls) == 2
	assert scanner.calls[-1][5] == "{Y}-{M}"


def test_preview_warns_without_required_selection(monkeypatch, tmp_path):
	controller, window, scanner, *_ = make_controller(monkeypatch, tmp_path)
	warnings = []
	monkeypatch.setattr(controller_module.messagebox, "showwarning", lambda *args, **kwargs: warnings.append(args))
	window.config_frame.targets = []

	controller._on_preview_request()

	assert len(warnings) == 1
	assert scanner.calls == []


def test_execute_logs_pushes_history_and_rescans(monkeypatch, tmp_path):
	controller, window, scanner, rename, undo, log, *_ = make_controller(monkeypatch, tmp_path)
	controller._on_preview_request()
	log.rename_calls.clear()
	rename.result_items = [controller._last_items[0]]

	controller._on_execute()

	assert len(rename.calls) == 1
	assert len(log.rename_calls) == 1
	assert len(undo.histories) == 1
	assert len(scanner.calls) == 2
	assert scanner.calls[-1][3] == "{Y}{M}{D}-{Y2}{M2}{D2}"
	assert scanner.calls[-1][5] == "{Y}-{M}"
	assert window.action_frame.processing is False


def test_execute_does_not_log_when_disabled(monkeypatch, tmp_path):
	controller, window, _, rename, _, log, *_ = make_controller(monkeypatch, tmp_path)
	controller._on_preview_request()
	window.action_frame.log_enabled = False

	controller._on_execute()

	assert rename.calls
	assert log.rename_calls == []


def test_undo_logs_new_session_id_and_rescans(monkeypatch, tmp_path):
	controller, window, scanner, _, undo, log, *_ = make_controller(monkeypatch, tmp_path)
	controller._on_preview_request()
	undo.restored_items = list(controller._last_items)
	undo.histories = [ExecutionHistory(items=list(controller._last_items)), ExecutionHistory(items=list(controller._last_items))]

	controller._on_undo()
	controller._on_undo()

	assert len(undo.calls) == 2
	assert len(log.undo_calls) == 2
	assert log.undo_calls[0][1] != log.undo_calls[1][1]
	assert len(scanner.calls) == 3
	assert all(call[3] == "{Y}{M}{D}-{Y2}{M2}{D2}" for call in scanner.calls)
	assert all(call[5] == "{Y}-{M}" for call in scanner.calls)


def test_operations_rescan_with_month_template_from_original_preview(
	monkeypatch,
	tmp_path,
):
	controller, window, scanner, _, undo, *_ = make_controller(
		monkeypatch,
		tmp_path,
	)
	controller._on_preview_request()
	window.config_frame.selected_month_template = OutputTemplateEntry(
		"changed after preview",
		"{M}-{Y}",
	)

	controller._on_execute()
	controller._on_undo()

	assert [call[5] for call in scanner.calls] == [
		"{Y}-{M}",
		"{Y}-{M}",
		"{Y}-{M}",
	]
	assert len(undo.calls) == 1


def test_pattern_and_template_errors_are_reported(monkeypatch, tmp_path):
	controller, window, _, _, _, _, patterns, templates, range_templates, pattern, template, _ = make_controller(monkeypatch, tmp_path)
	month_templates = controller.month_output_template_service
	errors = []
	monkeypatch.setattr(controller_module.messagebox, "showerror", lambda *args, **kwargs: errors.append(args))
	patterns.error = InvalidPatternError("bad pattern")
	templates.error = InvalidTemplateError("bad template")
	range_templates.error = InvalidTemplateError("bad range template")
	month_templates.error = InvalidTemplateError("bad month template")
	range_template = OutputTemplateEntry(
		"range default",
		"{Y}{M}{D}-{Y2}{M2}{D2}",
	)

	controller._on_pattern_save(pattern)
	controller._on_pattern_delete(pattern.name)
	controller._on_template_save(template)
	controller._on_template_delete(template.name)
	controller._on_range_template_save(range_template)
	controller._on_range_template_delete(range_template.name)
	controller._on_month_template_save(template)
	controller._on_month_template_delete(template.name)

	assert len(errors) == 8


def test_range_template_save_and_delete_update_config(monkeypatch, tmp_path):
	controller, window, _, _, _, _, _, _, range_templates, _, _, _ = make_controller(
		monkeypatch,
		tmp_path,
	)
	replacement = OutputTemplateEntry(
		"range replacement",
		"{Y}{M}{D}-{Y2}{M2}{D2}",
	)

	controller._on_range_template_save(replacement)

	assert replacement in range_templates.entries
	assert window.config_frame.range_templates[-1] == replacement

	controller._on_range_template_delete(replacement.name)

	assert replacement not in range_templates.entries


def test_month_template_save_and_delete_update_config(monkeypatch, tmp_path):
	controller, window, *_ = make_controller(monkeypatch, tmp_path)
	month_templates = controller.month_output_template_service
	replacement = OutputTemplateEntry("replacement month", "{Y}_{M}")

	controller._on_month_template_save(replacement)

	assert replacement in month_templates.entries
	assert window.config_frame.month_templates[-1] == replacement

	controller._on_month_template_delete(replacement.name)

	assert replacement not in month_templates.entries


def test_busy_operations_are_ignored_and_cancel_sets_event(monkeypatch, tmp_path):
	controller, window, scanner, rename, *_ = make_controller(monkeypatch, tmp_path)
	controller._busy = True
	controller._cancel_event = Event()

	controller._on_preview_request()
	controller._on_execute()
	controller._on_undo()
	controller._on_cancel()

	assert scanner.calls == []
	assert rename.calls == []
	assert controller._cancel_event.is_set()
	assert window.action_frame.status == "キャンセル中..."


@pytest.mark.parametrize("answer", [False, True])
def test_close_asks_only_while_busy(monkeypatch, tmp_path, answer):
	controller, window, *_ = make_controller(monkeypatch, tmp_path)
	answers = []
	monkeypatch.setattr(
		controller_module.messagebox,
		"askyesno",
		lambda *args, **kwargs: answers.append(args) or answer,
	)
	controller._busy = True
	controller._cancel_event = Event()

	controller._on_close()

	assert len(answers) == 1
	assert window.destroyed is answer
	assert controller._cancel_event.is_set() is answer


def test_close_destroys_immediately_when_idle(monkeypatch, tmp_path):
	controller, window, *_ = make_controller(monkeypatch, tmp_path)
	monkeypatch.setattr(controller_module.messagebox, "askyesno", lambda *args, **kwargs: pytest.fail("unexpected dialog"))

	controller._on_close()

	assert window.destroyed is True


def test_import_updates_presets_and_invalidates_preview(monkeypatch, tmp_path):
	controller, window, scanner, _, undo, _, patterns, *_ = make_controller(
		monkeypatch,
		tmp_path,
	)
	controller._on_preview_request()
	old_items = list(controller._last_items)
	added = PatternEntry("imported", r"(\d{4})-(\d{2})-(\d{2})")
	patterns.import_entries = [added]
	window.import_path = tmp_path / "patterns.json"
	notices = []
	monkeypatch.setattr(
		controller_module.messagebox,
		"showinfo",
		lambda *args, **kwargs: notices.append(args),
	)
	undo.histories = [ExecutionHistory(items=old_items)]

	controller._on_preset_import("pattern")

	assert patterns.entries[-1] == added
	assert window.config_frame.patterns[-1] == added
	assert window.preview_frame.items == []
	assert window.action_frame.counts == (0, 0, 0)
	assert "再プレビュー" in window.action_frame.status
	assert controller._last_items == []
	assert controller._last_base_dir is None
	assert controller._last_scan_params is None
	assert undo.has_history()
	assert "追加: 1件" in notices[0][1]
	assert window.conflict_policy_requests == []


def test_import_conflicts_overwrite_in_place_and_report_counts(monkeypatch, tmp_path):
	controller, window, _, _, _, _, patterns, *_ = make_controller(
		monkeypatch,
		tmp_path,
	)
	old_default = patterns.entries[0]
	second = PatternEntry("second", r"(\d{4})-(\d{2})")
	patterns.entries.append(second)
	window.config_frame.set_patterns(patterns.entries)
	window.config_frame.selected_patterns = [old_default]
	replacement_default = PatternEntry("default", r"(\d{4})\.(\d{2})")
	replacement_second = PatternEntry("second", r"(\d{4})/(\d{2})")
	added = PatternEntry("added", r"(\d{4})(\d{2})(\d{2})")
	patterns.import_entries = [replacement_second, replacement_default, added]
	window.import_path = tmp_path / "patterns.json"
	window.conflict_policy = ConflictPolicy.OVERWRITE
	notices = []
	monkeypatch.setattr(
		controller_module.messagebox,
		"showinfo",
		lambda *args, **kwargs: notices.append(args),
	)

	controller._on_preset_import("pattern")

	assert window.conflict_policy_requests == [("second", "default")]
	assert [entry.name for entry in patterns.entries] == [
		"default",
		"second",
		"added",
	]
	assert patterns.entries[:2] == [replacement_default, replacement_second]
	assert window.config_frame.selected_patterns == [replacement_default]
	assert notices[0][1].count("上書き: 2件") == 1
	assert "追加: 1件" in notices[0][1]
	assert "スキップ: 0件" in notices[0][1]
	assert "再プレビューしてください" in notices[0][1]


def test_import_skip_keeps_conflicts_adds_new_items_and_reports_counts(
	monkeypatch,
	tmp_path,
):
	controller, window, _, _, undo, _, patterns, *_ = make_controller(
		monkeypatch,
		tmp_path,
	)
	existing = patterns.entries[0]
	replacement = PatternEntry(existing.name, r"(\d{4})\.(\d{2})\.(\d{2})")
	added = PatternEntry("added", r"(\d{4})-(\d{2})-(\d{2})")
	patterns.import_entries = [replacement, added]
	window.import_path = tmp_path / "patterns.json"
	window.conflict_policy = ConflictPolicy.SKIP
	undo.histories = [ExecutionHistory(items=[])]
	notices = []
	monkeypatch.setattr(
		controller_module.messagebox,
		"showinfo",
		lambda *args, **kwargs: notices.append(args),
	)

	controller._on_preset_import("pattern")

	assert patterns.entries == [existing, added]
	assert window.conflict_policy_requests == [(existing.name,)]
	assert patterns.apply_calls[0][1] is ConflictPolicy.SKIP
	assert "追加: 1件" in notices[0][1]
	assert "上書き: 0件" in notices[0][1]
	assert "スキップ: 1件" in notices[0][1]
	assert "再プレビューしてください" in notices[0][1]
	assert undo.has_history()


def test_cancelled_conflict_resolution_preserves_import_state(monkeypatch, tmp_path):
	controller, window, scanner, _, undo, _, patterns, *_ = make_controller(
		monkeypatch,
		tmp_path,
	)
	controller._on_preview_request()
	preview_items = list(window.preview_frame.items)
	scan_params = controller._last_scan_params
	selected = list(window.config_frame.selected_patterns)
	counts = window.action_frame.counts
	undo.histories = [ExecutionHistory(items=list(controller._last_items))]
	patterns.import_entries = [patterns.entries[0]]
	window.import_path = tmp_path / "patterns.json"
	window.conflict_policy = None

	controller._on_preset_import("pattern")

	assert window.conflict_policy_requests == [("default",)]
	assert patterns.apply_calls == []
	assert window.config_frame.selected_patterns == selected
	assert window.preview_frame.items == preview_items
	assert window.action_frame.counts == counts
	assert controller._last_scan_params == scan_params
	assert len(scanner.calls) == 1
	assert undo.has_history()
	controller._on_undo()
	assert len(undo.calls) == 1
	assert not undo.has_history()


def test_all_conflicts_skipped_does_not_invalidate_preview(monkeypatch, tmp_path):
	controller, window, scanner, _, undo, _, patterns, *_ = make_controller(
		monkeypatch,
		tmp_path,
	)
	controller._on_preview_request()
	preview_items = list(window.preview_frame.items)
	scan_params = controller._last_scan_params
	status = window.action_frame.status
	counts = window.action_frame.counts
	entries_before = list(patterns.entries)
	undo.histories = [ExecutionHistory(items=list(controller._last_items))]
	patterns.import_entries = [patterns.entries[0]]
	window.import_path = tmp_path / "patterns.json"
	window.conflict_policy = ConflictPolicy.SKIP
	notices = []
	monkeypatch.setattr(
		controller_module.messagebox,
		"showinfo",
		lambda *args, **kwargs: notices.append(args),
	)

	controller._on_preset_import("pattern")

	assert patterns.entries == entries_before
	assert patterns.apply_calls[0][1] is ConflictPolicy.SKIP
	assert window.preview_frame.items == preview_items
	assert window.action_frame.status == status
	assert window.action_frame.counts == counts
	assert controller._last_scan_params == scan_params
	assert len(scanner.calls) == 1
	assert "変更はありませんでした" in notices[0][1]
	assert "スキップ: 1件" in notices[0][1]
	assert "再プレビュー" not in notices[0][1]
	assert undo.has_history()
	controller._on_undo()
	assert len(undo.calls) == 1
	assert not undo.has_history()


@pytest.mark.parametrize(
	"kind",
	["pattern", "single_template", "range_template", "month_template"],
)
def test_import_refreshes_selected_item_after_overwrite(
	monkeypatch,
	tmp_path,
	kind,
):
	controller, window, _, _, _, _, patterns, templates, range_templates, *_ = (
		make_controller(monkeypatch, tmp_path)
	)
	frame = window.config_frame
	if kind == "pattern":
		service = patterns
		selected = frame.selected_patterns[0]
		replacement = PatternEntry(selected.name, r"(\d{4})-(\d{2})-(\d{2})")
	elif kind == "single_template":
		service = templates
		selected = frame.selected_template
		assert selected is not None
		replacement = OutputTemplateEntry(selected.name, "{Y}-{M}-{D}")
	elif kind == "range_template":
		service = range_templates
		selected = frame.selected_range_template
		assert selected is not None
		replacement = OutputTemplateEntry(
			selected.name,
			"{Y}{M}{D}_{Y2}{M2}{D2}",
		)
	else:
		service = controller.month_output_template_service
		selected = frame.selected_month_template
		assert selected is not None
		replacement = OutputTemplateEntry(selected.name, "{Y}_{M}")

	setattr(service, "import_entries", [replacement])
	window.import_path = tmp_path / "presets.json"
	window.conflict_policy = ConflictPolicy.OVERWRITE
	monkeypatch.setattr(
		controller_module.messagebox,
		"showinfo",
		lambda *args, **kwargs: None,
	)

	controller._on_preset_import(kind)

	if kind == "pattern":
		assert frame.patterns[0] == replacement
		assert frame.selected_patterns == [replacement]
	elif kind == "single_template":
		assert frame.templates[0] == replacement
		assert frame.selected_template == replacement
	elif kind == "range_template":
		assert frame.range_templates[0] == replacement
		assert frame.selected_range_template == replacement
	else:
		assert frame.month_templates[0] == replacement
		assert frame.selected_month_template == replacement


@pytest.mark.parametrize(
	"kind",
	["pattern", "single_template", "range_template", "month_template"],
)
def test_import_preserves_existing_selection_by_name(
	monkeypatch,
	tmp_path,
	kind,
):
	controller, window, _, _, _, _, patterns, templates, range_templates, *_ = (
		make_controller(monkeypatch, tmp_path)
	)
	window.import_path = tmp_path / "presets.json"
	monkeypatch.setattr(
		controller_module.messagebox,
		"showinfo",
		lambda *args, **kwargs: None,
	)
	added_pattern = PatternEntry("added pattern", r"(\d{4})(\d{2})(\d{2})")
	added_template = OutputTemplateEntry("added template", "{Y}{M}{D}")
	added_month_template = OutputTemplateEntry("added month", "{Y}_{M}")

	if kind == "pattern":
		patterns.import_entries = [added_pattern]
		selected_name = patterns.entries[0].name
	elif kind == "single_template":
		templates.import_entries = [added_template]
		selected_name = templates.entries[0].name
	elif kind == "range_template":
		range_templates.import_entries = [
			OutputTemplateEntry(
				"added range",
				"{Y}{M}{D}-{Y2}{M2}{D2}",
			)
		]
		selected_name = range_templates.entries[0].name
	else:
		controller.month_output_template_service.import_entries = [
			added_month_template
		]
		selected_name = (
			controller.month_output_template_service.entries[0].name
		)

	controller._on_preset_import(kind)

	if kind == "pattern":
		assert [entry.name for entry in window.config_frame.selected_patterns] == [
			selected_name
		]
		assert added_pattern not in window.config_frame.selected_patterns
	elif kind == "single_template":
		selected_template = window.config_frame.get_selected_template()
		assert selected_template is not None
		assert selected_template.name == selected_name
		assert added_template != selected_template
	elif kind == "range_template":
		selected_range_template = (
			window.config_frame.get_selected_range_template()
		)
		assert selected_range_template is not None
		assert selected_range_template.name == selected_name
		assert selected_range_template.name != "added range"
	else:
		selected_month_template = (
			window.config_frame.get_selected_month_template()
		)
		assert selected_month_template is not None
		assert selected_month_template.name == selected_name
		assert selected_month_template != added_month_template


def test_month_template_import_preserves_selection_and_invalidates_preview(
	monkeypatch,
	tmp_path,
):
	controller, window, scanner, _, undo, _, *_ = make_controller(
		monkeypatch,
		tmp_path,
	)
	controller._on_preview_request()
	old_items = list(controller._last_items)
	undo.histories = [ExecutionHistory(items=old_items)]
	month_service = controller.month_output_template_service
	added = OutputTemplateEntry("imported month", "{Y}_{M}")
	month_service.import_entries = [added]
	window.import_path = tmp_path / "month-templates.json"
	monkeypatch.setattr(
		controller_module.messagebox,
		"showinfo",
		lambda *args, **kwargs: None,
	)

	controller._on_preset_import("month_template")

	assert month_service.entries[-1] == added
	assert window.config_frame.get_selected_month_template().name == "month default"
	assert window.preview_frame.items == []
	assert controller._last_items == []
	assert controller._last_scan_params is None
	assert undo.has_history()
	assert len(scanner.calls) == 1


def test_import_is_blocked_before_open_dialog_while_processing(monkeypatch, tmp_path):
	controller, window, *_ = make_controller(monkeypatch, tmp_path)
	warnings = []
	monkeypatch.setattr(
		controller_module.messagebox,
		"showwarning",
		lambda *args, **kwargs: warnings.append(args),
	)
	controller._busy = True

	controller._on_preset_import("pattern")

	assert window.import_path_requests == []
	assert len(warnings) == 1


def test_cancelled_import_does_not_change_preview(monkeypatch, tmp_path):
	controller, window, scanner, *_ = make_controller(monkeypatch, tmp_path)
	controller._on_preview_request()
	preview_items = list(window.preview_frame.items)
	scan_params = controller._last_scan_params
	window.import_path = None

	controller._on_preset_import("pattern")

	assert window.import_path_requests == ["pattern"]
	assert scanner.calls
	assert window.preview_frame.items == preview_items
	assert controller._last_scan_params == scan_params


def test_failed_import_does_not_change_preview_or_selection(monkeypatch, tmp_path):
	controller, window, scanner, _, _, _, patterns, *_ = make_controller(
		monkeypatch,
		tmp_path,
	)
	controller._on_preview_request()
	preview_items = list(window.preview_frame.items)
	scan_params = controller._last_scan_params
	selected_patterns = list(window.config_frame.selected_patterns)
	counts = window.action_frame.counts
	window.import_path = tmp_path / "invalid.json"
	patterns.error = ValueError("invalid preset")
	errors = []
	monkeypatch.setattr(
		controller_module.messagebox,
		"showerror",
		lambda *args, **kwargs: errors.append(args),
	)

	controller._on_preset_import("pattern")

	assert len(scanner.calls) == 1
	assert window.preview_frame.items == preview_items
	assert controller._last_scan_params == scan_params
	assert window.config_frame.selected_patterns == selected_patterns
	assert window.action_frame.counts == counts
	assert len(errors) == 1
	assert window.conflict_policy_requests == []


@pytest.mark.parametrize("import_kind", ["add", "overwrite"])
def test_undo_after_import_does_not_restore_stale_preview(
	monkeypatch,
	tmp_path,
	import_kind,
):
	controller, window, scanner, _, undo, _, patterns, *_ = make_controller(
		monkeypatch,
		tmp_path,
	)
	controller._on_preview_request()
	old_items = list(controller._last_items)
	if import_kind == "add":
		patterns.import_entries = [
			PatternEntry("imported", r"(\d{4})-(\d{2})-(\d{2})")
		]
	else:
		patterns.import_entries = [
			PatternEntry("default", r"(\d{4})-(\d{2})-(\d{2})")
		]
		window.conflict_policy = ConflictPolicy.OVERWRITE
	window.import_path = tmp_path / "patterns.json"
	undo.histories = [ExecutionHistory(items=old_items)]
	undo.restored_items = old_items
	monkeypatch.setattr(
		controller_module.messagebox,
		"showinfo",
		lambda *args, **kwargs: None,
	)
	controller._on_preset_import("pattern")

	controller._on_undo()

	assert len(scanner.calls) == 1
	assert window.preview_frame.items == []
	assert controller._last_items == []
	assert controller._last_scan_params is None
	assert window.action_frame.counts == (0, 0, 0)
	assert window.action_frame.processing is False
	assert window.action_frame.progress == 100
	assert window.action_frame.status == "Undoが完了しました"
	assert controller._busy is False


def test_export_prompts_before_overwriting_existing_external_file(
	monkeypatch,
	tmp_path,
):
	controller, window, _, _, _, _, patterns, *_ = make_controller(
		monkeypatch,
		tmp_path,
	)
	target = tmp_path / "presets.json"
	target.write_text("keep", encoding="utf-8")
	window.export_path = target
	questions = []
	monkeypatch.setattr(
		controller_module.messagebox,
		"askyesno",
		lambda *args, **kwargs: questions.append(args) or False,
	)

	controller._on_preset_export("pattern")

	assert len(questions) == 1
	assert patterns.export_calls == []
	assert target.read_text(encoding="utf-8") == "keep"


def test_export_writes_after_overwrite_is_confirmed(monkeypatch, tmp_path):
	controller, window, _, _, _, _, patterns, *_ = make_controller(
		monkeypatch,
		tmp_path,
	)
	target = tmp_path / "presets.json"
	target.write_text("existing", encoding="utf-8")
	window.export_path = target
	questions = []
	monkeypatch.setattr(
		controller_module.messagebox,
		"askyesno",
		lambda *args, **kwargs: questions.append(args) or True,
	)
	notices = []
	monkeypatch.setattr(
		controller_module.messagebox,
		"showinfo",
		lambda *args, **kwargs: notices.append(args),
	)

	controller._on_preset_export("pattern")

	assert len(questions) == 1
	assert patterns.export_calls == [target]
	assert len(notices) == 1


def test_export_rejects_internal_config_path_before_overwrite_prompt(
	monkeypatch,
	tmp_path,
):
	controller, window, _, _, _, _, patterns, *_ = make_controller(
		monkeypatch,
		tmp_path,
	)
	target = patterns.base_dir / "patterns.json"
	window.export_path = target
	errors = []
	monkeypatch.setattr(
		controller_module.messagebox,
		"askyesno",
		lambda *args, **kwargs: pytest.fail("overwrite prompt shown for internal path"),
	)
	monkeypatch.setattr(
		controller_module.messagebox,
		"showerror",
		lambda *args, **kwargs: errors.append(args),
	)

	controller._on_preset_export("pattern")

	assert patterns.export_calls == []
	assert len(errors) == 1
	assert "内部設定ファイル" in errors[0][1]


@pytest.mark.parametrize(
	"status",
	[
		"Undoが完了しました",
		"Undoがキャンセルされました",
	],
)
def test_undo_without_rescan_conditions_finishes_cleanly(
	monkeypatch,
	tmp_path,
	status,
):
	controller, window, *_ = make_controller(monkeypatch, tmp_path)
	controller._busy = True
	controller._last_scan_params = None
	controller._last_items = []
	window.action_frame.set_processing(True)

	controller._on_undo_complete([], was_cancelled=status.endswith("キャンセルされました"))

	assert controller._busy is False
	assert controller._cancel_event is None
	assert window.action_frame.processing is False
	assert window.action_frame.progress == 100
	assert window.action_frame.status == status


def test_resolve_selected_indices_preserves_multiple_and_empty_selection():
	names = ["first", "second", "third"]

	assert resolve_selected_indices(["third", "first"], names) == [0, 2]
	assert resolve_selected_indices([], names) == []

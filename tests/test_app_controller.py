from pathlib import Path
from threading import Event

import pytest

from rename_date.controllers import app_controller as controller_module
from rename_date.controllers.app_controller import AppController
from rename_date.models.execution_history import ExecutionHistory
from rename_date.models.output_template_entry import OutputTemplateEntry
from rename_date.models.pattern_entry import PatternEntry
from rename_date.models.rename_item import ItemStatus, RenameItem
from rename_date.services.validation import InvalidPatternError, InvalidTemplateError


class FakeConfigFrame:
	def __init__(self) -> None:
		self.targets: list[Path] = []
		self.selected_patterns: list[PatternEntry] = []
		self.selected_template: OutputTemplateEntry | None = None
		self.callbacks = {}
		self.patterns = []
		self.templates = []

	def set_patterns(self, entries):
		self.patterns = list(entries)

	def set_templates(self, entries):
		self.templates = list(entries)
		if self.selected_template is None and self.templates:
			self.selected_template = self.templates[0]

	def set_callbacks(self, **callbacks):
		self.callbacks.update(callbacks)

	def get_targets(self):
		return list(self.targets)

	def get_selected_patterns(self):
		return list(self.selected_patterns)

	def get_selected_template(self):
		return self.selected_template


class FakePreviewFrame:
	def __init__(self) -> None:
		self.items = []
		self.base_dir = None

	def set_items(self, items, base_dir=None):
		self.items = list(items)
		self.base_dir = base_dir


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


class FakeWindow:
	def __init__(self) -> None:
		self.config_frame = FakeConfigFrame()
		self.preview_frame = FakePreviewFrame()
		self.action_frame = FakeActionFrame()
		self.protocols = {}
		self.destroyed = False

	def after(self, delay, callback, *args):
		callback(*args)

	def protocol(self, name, callback):
		self.protocols[name] = callback

	def destroy(self):
		self.destroyed = True


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
		self.error = None

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
			raise ValueError("last pattern")
		self.entries = remaining
		return list(self.entries)


class FakeTemplateService:
	def __init__(self, entries):
		self.entries = list(entries)
		self.error = None

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


class FakeScannerService:
	def __init__(self, items):
		self.items = list(items)
		self.calls = []

	def scan(self, targets, patterns, output_template, cancel_event=None, progress_callback=None):
		self.calls.append((list(targets), list(patterns), output_template, cancel_event))
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

	def log_rename(self, items, session_id):
		self.rename_calls.append((list(items), session_id))

	def log_undo(self, items, session_id):
		self.undo_calls.append((list(items), session_id))


def make_controller(monkeypatch, tmp_path):
	monkeypatch.setattr(controller_module.threading, "Thread", ImmediateThread)
	pattern = PatternEntry("default", r"\((\d{4})\.(\d{1,2})\.(\d{1,2})\)")
	template = OutputTemplateEntry("default", "{Y}{M}{D}")
	source = tmp_path / "before.txt"
	target = tmp_path / "after.txt"
	item = RenameItem(source, target)
	window = FakeWindow()
	window.config_frame.targets = [tmp_path]
	window.config_frame.selected_patterns = [pattern]
	window.config_frame.selected_template = template
	scanner = FakeScannerService([item])
	rename = FakeRenameService([item])
	undo = FakeUndoService()
	log = FakeLogService()
	patterns = FakePatternService([pattern])
	templates = FakeTemplateService([template])
	controller = AppController(window, scanner, rename, undo, log, patterns, templates)
	return controller, window, scanner, rename, undo, log, patterns, templates, pattern, template, item


def test_preview_uses_services_and_updates_view(monkeypatch, tmp_path):
	controller, window, scanner, *_ = make_controller(monkeypatch, tmp_path)

	controller._on_preview_request()

	assert len(scanner.calls) == 1
	assert scanner.calls[0][1] == [window.config_frame.selected_patterns[0].pattern]
	assert window.preview_frame.items
	assert window.preview_frame.base_dir == tmp_path
	assert window.action_frame.counts == (1, 0, 1)
	assert window.action_frame.processing is False


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


def test_pattern_and_template_errors_are_reported(monkeypatch, tmp_path):
	controller, window, _, _, _, _, patterns, templates, pattern, template, _ = make_controller(monkeypatch, tmp_path)
	errors = []
	monkeypatch.setattr(controller_module.messagebox, "showerror", lambda *args, **kwargs: errors.append(args))
	patterns.error = InvalidPatternError("bad pattern")
	templates.error = InvalidTemplateError("bad template")

	controller._on_pattern_save(pattern)
	controller._on_pattern_delete(pattern.name)
	controller._on_template_save(template)
	controller._on_template_delete(template.name)

	assert len(errors) == 4


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

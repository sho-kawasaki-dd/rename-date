"""Coordinate views and services for the rename workflow."""

from pathlib import Path
import os
import logging
import threading
import uuid
from tkinter import messagebox

from rename_date import config
from rename_date.models.execution_history import ExecutionHistory
from rename_date.models.output_template_entry import OutputTemplateEntry
from rename_date.models.pattern_entry import PatternEntry
from rename_date.models.rename_item import ItemStatus, RenameItem
from rename_date.services.log_service import LogService
from rename_date.services.output_template_service import (
	MonthOutputTemplateService,
	OutputTemplateService,
	RangeOutputTemplateService,
)
from rename_date.services.pattern_service import PatternService
from rename_date.services.rename_service import RenameService
from rename_date.services.scanner_service import ScannerService
from rename_date.services.undo_service import UndoService
from rename_date.services.preset_io import (
	PresetIOError,
	PresetIOReason,
	ensure_external_preset_path,
)
from rename_date.services.validation import (
	InvalidPatternError,
	InvalidTemplateError,
	PatternKind,
	compile_pattern,
	pattern_kind,
)
from rename_date.views.config_frame import PresetKind
from rename_date.views.main_window import MainWindow


ScanParams = tuple[list[Path], list[str], str, str, str]


class AppController:
	"""Connect the GUI callbacks to the background service operations."""

	def __init__(
		self,
		window: MainWindow,
		scanner_service: ScannerService,
		rename_service: RenameService,
		undo_service: UndoService,
		log_service: LogService,
		pattern_service: PatternService,
		output_template_service: OutputTemplateService,
		range_output_template_service: RangeOutputTemplateService,
		month_output_template_service: MonthOutputTemplateService,
	) -> None:
		self.window = window
		self.scanner_service = scanner_service
		self.rename_service = rename_service
		self.undo_service = undo_service
		self.log_service = log_service
		self.pattern_service = pattern_service
		self.output_template_service = output_template_service
		self.range_output_template_service = range_output_template_service
		self.month_output_template_service = month_output_template_service

		self._busy = False
		self._cancel_event: threading.Event | None = None
		self._last_items: list[RenameItem] = []
		self._last_base_dir: Path | None = None
		self._last_scan_params: ScanParams | None = None
		self._worker: threading.Thread | None = None

		self.window.config_frame.set_patterns(self.pattern_service.load())
		self.window.config_frame.set_templates(self.output_template_service.load())
		if hasattr(self.window.config_frame, "set_range_templates"):
			self.window.config_frame.set_range_templates(
				self.range_output_template_service.load()
			)
		self.window.config_frame.set_month_templates(
			self.month_output_template_service.load()
		)
		self.window.config_frame.set_callbacks(
			on_pattern_save=self._on_pattern_save,
			on_pattern_delete=self._on_pattern_delete,
			on_template_save=self._on_template_save,
			on_template_delete=self._on_template_delete,
			on_range_template_save=self._on_range_template_save,
			on_range_template_delete=self._on_range_template_delete,
			on_month_template_save=self._on_month_template_save,
			on_month_template_delete=self._on_month_template_delete,
			on_preview_request=self._on_preview_request,
		)
		self.window.action_frame.set_callbacks(
			on_execute=self._on_execute,
			on_undo=self._on_undo,
			on_cancel=self._on_cancel,
		)
		self.window.set_preset_callbacks(
			on_export=self._on_preset_export,
			on_import=self._on_preset_import,
		)
		self.window.log_frame.set_callbacks(
			on_refresh=self._on_log_refresh,
			on_open_folder=self._on_open_log_folder,
		)
		self._on_log_refresh()
		self.window.protocol("WM_DELETE_WINDOW", self._on_close)

	def _on_log_refresh(self) -> None:
		try:
			entries = self.log_service.read_entries()
		except OSError as error:
			messagebox.showerror("ログ読み込みエラー", str(error), parent=self.window)
		else:
			self.window.log_frame.set_entries(entries)

	def _on_open_log_folder(self) -> None:
		try:
			os.startfile(str(self.log_service.base_dir))
		except OSError as error:
			messagebox.showerror("ログフォルダエラー", str(error), parent=self.window)

	def _on_pattern_save(self, entry: PatternEntry) -> None:
		try:
			entries = self.pattern_service.upsert(entry)
		except (InvalidPatternError, ValueError) as error:
			messagebox.showerror("パターン保存エラー", str(error), parent=self.window)
		else:
			self.window.config_frame.set_patterns(entries)

	def _on_pattern_delete(self, name: str) -> None:
		try:
			entries = self.pattern_service.delete(name)
		except ValueError as error:
			messagebox.showerror("パターン削除エラー", str(error), parent=self.window)
		else:
			self.window.config_frame.set_patterns(entries)

	def _on_template_save(self, entry: OutputTemplateEntry) -> None:
		try:
			entries = self.output_template_service.upsert(entry)
		except (InvalidTemplateError, ValueError) as error:
			messagebox.showerror("出力テンプレート保存エラー", str(error), parent=self.window)
		else:
			self.window.config_frame.set_templates(entries)

	def _on_template_delete(self, name: str) -> None:
		try:
			entries = self.output_template_service.delete(name)
		except ValueError as error:
			messagebox.showerror("出力テンプレート削除エラー", str(error), parent=self.window)
		else:
			self.window.config_frame.set_templates(entries)

	def _on_range_template_save(self, entry: OutputTemplateEntry) -> None:
		try:
			entries = self.range_output_template_service.upsert(entry)
		except (InvalidTemplateError, ValueError) as error:
			messagebox.showerror("期間テンプレート保存エラー", str(error), parent=self.window)
		else:
			self.window.config_frame.set_range_templates(entries)

	def _on_range_template_delete(self, name: str) -> None:
		try:
			entries = self.range_output_template_service.delete(name)
		except ValueError as error:
			messagebox.showerror("期間テンプレート削除エラー", str(error), parent=self.window)
		else:
			self.window.config_frame.set_range_templates(entries)

	def _on_month_template_save(self, entry: OutputTemplateEntry) -> None:
		try:
			entries = self.month_output_template_service.upsert(entry)
		except (InvalidTemplateError, ValueError) as error:
			messagebox.showerror("年月テンプレート保存エラー", str(error), parent=self.window)
		else:
			self.window.config_frame.set_month_templates(entries)

	def _on_month_template_delete(self, name: str) -> None:
		try:
			entries = self.month_output_template_service.delete(name)
		except ValueError as error:
			messagebox.showerror("年月テンプレート削除エラー", str(error), parent=self.window)
		else:
			self.window.config_frame.set_month_templates(entries)

	def _on_preset_export(self, kind: PresetKind) -> None:
		service = self._preset_service(kind)
		path = self.window.choose_preset_export_path(kind)
		if path is None:
			return

		try:
			ensure_external_preset_path(path, service.base_dir)
			if path.exists() and not messagebox.askyesno(
				"上書き確認",
				f"既存のファイルを上書きしますか？\n{path}",
				parent=self.window,
			):
				return
			service.export_to_json(path)
		except (OSError, ValueError) as error:
			self._show_preset_io_error("保存", path, error)
		else:
			messagebox.showinfo(
				"プリセット保存",
				f"{self._preset_label(kind)}を保存しました。\n{path}",
				parent=self.window,
			)

	def _on_preset_import(self, kind: PresetKind) -> None:
		if self._busy:
			messagebox.showwarning(
				"プリセット取込",
				"処理中はプリセットを取り込めません。処理の完了後に再度お試しください。",
				parent=self.window,
			)
			return

		path = self.window.choose_preset_import_path(kind)
		if path is None:
			return
		before_count = self.window.config_frame.get_preset_count(kind)
		try:
			if kind == "pattern":
				entries = self.pattern_service.import_from_json(path)
				imported_count = len(entries) - before_count
				self.window.config_frame.set_patterns(
					entries,
					preserve_selection=True,
				)
			elif kind == "single_template":
				entries = self.output_template_service.import_from_json(path)
				imported_count = len(entries) - before_count
				self.window.config_frame.set_templates(
					entries,
					preserve_selection=True,
				)
			elif kind == "range_template":
				entries = self.range_output_template_service.import_from_json(path)
				imported_count = len(entries) - before_count
				self.window.config_frame.set_range_templates(
					entries,
					preserve_selection=True,
				)
			elif kind == "month_template":
				entries = self.month_output_template_service.import_from_json(path)
				imported_count = len(entries) - before_count
				self.window.config_frame.set_month_templates(
					entries,
					preserve_selection=True,
				)
			else:
				raise ValueError(f"unknown preset kind: {kind}")
		except (OSError, ValueError) as error:
			self._show_preset_io_error("取込", path, error)
			return

		self._last_items = []
		self._last_base_dir = None
		self._last_scan_params = None
		self.window.preview_frame.clear()
		self.window.action_frame.set_counts(0, 0, 0)
		self.window.action_frame.set_progress(0)
		self.window.action_frame.set_status(
			"プリセットを取り込みました。再プレビューしてください"
		)
		messagebox.showinfo(
			"プリセット取込",
			f"{self._preset_label(kind)}を{imported_count}件取り込みました。\n"
			"再プレビューしてください。",
			parent=self.window,
		)

	@staticmethod
	def _preset_label(kind: PresetKind) -> str:
		return {
			"pattern": "入力パターン",
			"single_template": "単日出力テンプレート",
			"range_template": "期間出力テンプレート",
			"month_template": "年月出力テンプレート",
		}[kind]

	def _preset_service(
		self,
		kind: PresetKind,
	) -> (
		PatternService
		| OutputTemplateService
		| RangeOutputTemplateService
		| MonthOutputTemplateService
	):
		try:
			return {
				"pattern": self.pattern_service,
				"single_template": self.output_template_service,
				"range_template": self.range_output_template_service,
				"month_template": self.month_output_template_service,
			}[kind]
		except KeyError as error:
			raise ValueError(f"unknown preset kind: {kind}") from error

	def _show_preset_io_error(
		self,
		action: str,
		path: Path,
		error: OSError | ValueError,
	) -> None:
		if isinstance(error, PresetIOError):
			reasons = {
				PresetIOReason.INTERNAL_PATH: "内部設定ファイルは対象に指定できません。",
				PresetIOReason.INVALID_JSON: "JSONを読み込めません。ファイル内容を確認してください。",
				PresetIOReason.INVALID_FORMAT: "JSONの形式が正しくありません。",
				PresetIOReason.VALIDATION: "プリセットの検証に失敗しました。",
				PresetIOReason.DUPLICATE_NAME: "同名のプリセットがあります。",
			}
			lines = [reasons[error.reason]]
			if error.name is not None:
				lines.append(f"項目名: {error.name}")
			if error.index is not None:
				lines.append(f"項目位置: {error.index + 1}")
			if error.detail:
				lines.append(f"詳細: {error.detail}")
		else:
			lines = [f"ファイル操作に失敗しました: {error}"]
		lines.insert(0, f"ファイル: {path}")
		messagebox.showerror(
			f"プリセット{action}エラー",
			"\n".join(lines),
			parent=self.window,
		)

	def _on_preview_request(self) -> None:
		if self._busy:
			return

		targets = self.window.config_frame.get_targets()
		patterns = self.window.config_frame.get_selected_patterns()
		template = self.window.config_frame.get_selected_template()
		range_template = (
			self.window.config_frame.get_selected_range_template()
			if hasattr(self.window.config_frame, "get_selected_range_template")
			else None
		)
		month_template = self.window.config_frame.get_selected_month_template()
		if not targets:
			messagebox.showwarning("プレビュー", "対象を選択してください", parent=self.window)
			return
		if not patterns:
			messagebox.showwarning("プレビュー", "パターンを選択してください", parent=self.window)
			return
		if template is None:
			messagebox.showwarning(
				"プレビュー",
				"出力テンプレートを選択してください",
				parent=self.window,
			)
			return
		if range_template is None:
			messagebox.showwarning(
				"プレビュー",
				"期間用出力テンプレートを選択してください",
				parent=self.window,
			)
			return

		pattern_strings = [entry.pattern for entry in patterns]
		try:
			pattern_kinds = [
				pattern_kind(compile_pattern(pattern))
				for pattern in pattern_strings
			]
		except InvalidPatternError:
			self._start_scan(
				list(targets),
				pattern_strings,
				template.template,
				range_template.template,
				(
					month_template.template
					if month_template is not None
					else config.DEFAULT_MONTH_OUTPUT_TEMPLATE
				),
				targets[0] if len(targets) == 1 and targets[0].is_dir() else None,
			)
			return
		has_month_pattern = PatternKind.MONTH in pattern_kinds
		if has_month_pattern and month_template is None:
			messagebox.showwarning(
				"プレビュー",
				"年月用出力テンプレートを選択してください",
				parent=self.window,
			)
			return

		self._start_scan(
			list(targets),
			pattern_strings,
			template.template,
			range_template.template,
			(
				month_template.template
				if month_template is not None
				else config.DEFAULT_MONTH_OUTPUT_TEMPLATE
			),
			targets[0] if len(targets) == 1 and targets[0].is_dir() else None,
		)

	def _start_scan(
		self,
		targets: list[Path],
		patterns: list[str],
		output_template: str,
		range_output_template: str,
		month_output_template: str,
		base_dir: Path | None,
	) -> None:
		self._last_scan_params = (
			list(targets),
			list(patterns),
			output_template,
			range_output_template,
			month_output_template,
		)
		self._last_items = []
		self._last_base_dir = base_dir
		self._busy = True
		self._cancel_event = threading.Event()
		self.window.action_frame.set_processing(True)
		self.window.action_frame.set_status("プレビューを更新中...")
		self.window.action_frame.set_progress(0)
		self._worker = threading.Thread(
			target=self._scan_worker,
			args=(
				targets,
				patterns,
				output_template,
				range_output_template,
				month_output_template,
				base_dir,
				self._cancel_event,
			),
			daemon=True,
		)
		self._worker.start()

	def _scan_worker(
		self,
		targets: list[Path],
		patterns: list[str],
		output_template: str,
		range_output_template: str,
		month_output_template: str,
		base_dir: Path | None,
		cancel_event: threading.Event,
	) -> None:
		try:
			items = self.scanner_service.scan(
				targets,
				patterns,
				output_template,
				cancel_event=cancel_event,
				progress_callback=self._report_progress,
				range_output_template=range_output_template,
				month_output_template=month_output_template,
			)
		except InvalidPatternError as error:
			self.window.after(0, self._on_scan_error, "パターンエラー", error)
		except Exception as error:
			logging.getLogger(__name__).exception("scan failed")
			self.window.after(0, self._on_scan_error, "プレビューエラー", error)
		else:
			self.window.after(
				0,
				self._on_scan_complete,
				items,
				base_dir,
				cancel_event.is_set(),
			)

	def _on_scan_complete(
		self,
		items: list[RenameItem],
		base_dir: Path | None,
		was_cancelled: bool,
	) -> None:
		self._last_items = items
		self._last_base_dir = base_dir
		self.window.preview_frame.set_items(items, base_dir)
		self.window.action_frame.set_counts(
			sum(item.is_executable for item in items),
			sum(item.status is ItemStatus.INVALID_DATE for item in items),
			len(items),
		)
		if not was_cancelled:
			self.window.action_frame.set_progress(100)
		self.window.action_frame.set_status(
			"キャンセルされました" if was_cancelled else "プレビューを更新しました"
		)
		self.window.action_frame.set_processing(False)
		self._busy = False
		self._cancel_event = None

	def _on_scan_error(self, title: str, error: Exception) -> None:
		messagebox.showerror(title, str(error), parent=self.window)
		self.window.action_frame.set_processing(False)
		self.window.action_frame.set_status("処理に失敗しました")
		self._busy = False
		self._cancel_event = None

	def _on_execute(self) -> None:
		if self._busy:
			return
		if not self._last_items:
			messagebox.showwarning(
				"一括変換",
				"先にプレビューを更新してください",
				parent=self.window,
			)
			return

		self._busy = True
		self._cancel_event = threading.Event()
		self.window.action_frame.set_processing(True)
		self.window.action_frame.set_status("実行中...")
		self.window.action_frame.set_progress(0)
		self._worker = threading.Thread(
			target=self._execute_worker,
			args=(self._last_items, self._cancel_event),
			daemon=True,
		)
		self._worker.start()

	def _execute_worker(
		self,
		items: list[RenameItem],
		cancel_event: threading.Event,
	) -> None:
		try:
			result = self.rename_service.execute(
				items,
				cancel_event=cancel_event,
				progress_callback=self._report_progress,
			)
		except Exception as error:
			logging.getLogger(__name__).exception("rename execution failed")
			self.window.after(0, self._on_operation_error, "実行エラー", error)
		else:
			self.window.after(0, self._on_execute_complete, *result)

	def _on_execute_complete(self, items: list[RenameItem], history: ExecutionHistory) -> None:
		if self.window.action_frame.get_log_enabled():
			self.log_service.log_rename(items, history.session_id)
		if history.items:
			self.undo_service.push(history)
		self.window.action_frame.set_undo_enabled(self.undo_service.has_history())
		self._rescan_after_operation()

	def _on_undo(self) -> None:
		if self._busy or not self.undo_service.has_history():
			return

		self._busy = True
		self._cancel_event = threading.Event()
		self.window.action_frame.set_processing(True)
		self.window.action_frame.set_status("元に戻しています...")
		self.window.action_frame.set_progress(0)
		self._worker = threading.Thread(
			target=self._undo_worker,
			args=(self._cancel_event,),
			daemon=True,
		)
		self._worker.start()

	def _undo_worker(self, cancel_event: threading.Event) -> None:
		try:
			items = self.undo_service.undo(
				cancel_event=cancel_event,
				progress_callback=self._report_progress,
			)
		except Exception as error:
			logging.getLogger(__name__).exception("undo failed")
			self.window.after(0, self._on_operation_error, "Undoエラー", error)
		else:
			self.window.after(
				0,
				self._on_undo_complete,
				items,
				cancel_event.is_set(),
			)

	def _on_undo_complete(
		self,
		items: list[RenameItem],
		was_cancelled: bool = False,
	) -> None:
		if self.window.action_frame.get_log_enabled():
			self.log_service.log_undo(items, uuid.uuid4().hex[:8])
		self.window.action_frame.set_undo_enabled(self.undo_service.has_history())
		self._rescan_after_operation(
			"Undoがキャンセルされました" if was_cancelled else "Undoが完了しました"
		)

	def _rescan_after_operation(
		self,
		completion_status: str = "操作が完了しました",
	) -> None:
		if self._last_scan_params is None:
			self.window.action_frame.set_processing(False)
			self.window.action_frame.set_progress(100)
			self.window.action_frame.set_status(completion_status)
			self._busy = False
			self._cancel_event = None
			return
		(
			targets,
			patterns,
			output_template,
			range_output_template,
			month_output_template,
		) = self._last_scan_params
		base_dir = targets[0] if len(targets) == 1 and targets[0].is_dir() else None
		self._start_scan(
			targets,
			patterns,
			output_template,
			range_output_template,
			month_output_template,
			base_dir,
		)

	def _on_operation_error(self, title: str, error: Exception) -> None:
		messagebox.showerror(title, str(error), parent=self.window)
		self.window.action_frame.set_processing(False)
		self.window.action_frame.set_status("処理に失敗しました")
		self._busy = False
		self._cancel_event = None

	def _report_progress(self, done: int, total: int) -> None:
		progress = 0 if total <= 0 else int(done / total * 100)
		self.window.after(0, self.window.action_frame.set_progress, progress)

	def _on_cancel(self) -> None:
		if self._cancel_event is not None:
			self._cancel_event.set()
			self.window.action_frame.set_status("キャンセル中...")

	def _on_close(self) -> None:
		if not self._busy:
			self.window.destroy()
			return
		if messagebox.askyesno(
			"終了確認",
			"処理中です。中断して終了しますか？\nここまでの変更はログ・Undo履歴に記録されない場合があります",
			parent=self.window,
		):
			if self._cancel_event is not None:
				self._cancel_event.set()
			self.window.destroy()
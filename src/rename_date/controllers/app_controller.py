"""Coordinate views and services for the rename workflow."""

from pathlib import Path
import logging
import threading
import uuid
from tkinter import messagebox

from rename_date.models.execution_history import ExecutionHistory
from rename_date.models.output_template_entry import OutputTemplateEntry
from rename_date.models.pattern_entry import PatternEntry
from rename_date.models.rename_item import ItemStatus, RenameItem
from rename_date.services.log_service import LogService
from rename_date.services.output_template_service import OutputTemplateService
from rename_date.services.pattern_service import PatternService
from rename_date.services.rename_service import RenameService
from rename_date.services.scanner_service import ScannerService
from rename_date.services.undo_service import UndoService
from rename_date.services.validation import InvalidPatternError, InvalidTemplateError
from rename_date.views.main_window import MainWindow


ScanParams = tuple[list[Path], list[str], str]


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
	) -> None:
		self.window = window
		self.scanner_service = scanner_service
		self.rename_service = rename_service
		self.undo_service = undo_service
		self.log_service = log_service
		self.pattern_service = pattern_service
		self.output_template_service = output_template_service

		self._busy = False
		self._cancel_event: threading.Event | None = None
		self._last_items: list[RenameItem] = []
		self._last_base_dir: Path | None = None
		self._last_scan_params: ScanParams | None = None
		self._worker: threading.Thread | None = None

		self.window.config_frame.set_patterns(self.pattern_service.load())
		self.window.config_frame.set_templates(self.output_template_service.load())
		self.window.config_frame.set_callbacks(
			on_pattern_save=self._on_pattern_save,
			on_pattern_delete=self._on_pattern_delete,
			on_template_save=self._on_template_save,
			on_template_delete=self._on_template_delete,
			on_preview_request=self._on_preview_request,
		)
		self.window.action_frame.set_callbacks(
			on_execute=self._on_execute,
			on_undo=self._on_undo,
			on_cancel=self._on_cancel,
		)
		self.window.protocol("WM_DELETE_WINDOW", self._on_close)

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

	def _on_preview_request(self) -> None:
		if self._busy:
			return

		targets = self.window.config_frame.get_targets()
		patterns = self.window.config_frame.get_selected_patterns()
		template = self.window.config_frame.get_selected_template()
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

		pattern_strings = [entry.pattern for entry in patterns]
		self._start_scan(
			list(targets),
			pattern_strings,
			template.template,
			targets[0] if len(targets) == 1 and targets[0].is_dir() else None,
		)

	def _start_scan(
		self,
		targets: list[Path],
		patterns: list[str],
		output_template: str,
		base_dir: Path | None,
	) -> None:
		self._last_scan_params = (list(targets), list(patterns), output_template)
		self._last_items = []
		self._last_base_dir = base_dir
		self._busy = True
		self._cancel_event = threading.Event()
		self.window.action_frame.set_processing(True)
		self.window.action_frame.set_status("プレビューを更新中...")
		self.window.action_frame.set_progress(0)
		self._worker = threading.Thread(
			target=self._scan_worker,
			args=(targets, patterns, output_template, base_dir, self._cancel_event),
			daemon=True,
		)
		self._worker.start()

	def _scan_worker(
		self,
		targets: list[Path],
		patterns: list[str],
		output_template: str,
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
			self.window.after(0, self._on_undo_complete, items)

	def _on_undo_complete(self, items: list[RenameItem]) -> None:
		if self.window.action_frame.get_log_enabled():
			self.log_service.log_undo(items, uuid.uuid4().hex[:8])
		self.window.action_frame.set_undo_enabled(self.undo_service.has_history())
		self._rescan_after_operation()

	def _rescan_after_operation(self) -> None:
		if self._last_scan_params is None:
			self.window.action_frame.set_processing(False)
			self._busy = False
			self._cancel_event = None
			return
		targets, patterns, output_template = self._last_scan_params
		base_dir = targets[0] if len(targets) == 1 and targets[0].is_dir() else None
		self._start_scan(targets, patterns, output_template, base_dir)

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
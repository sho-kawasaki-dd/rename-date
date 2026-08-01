"""Execution controls and progress display."""

from collections.abc import Callable
import tkinter as tk
from tkinter import ttk


def _noop(*args: object, **kwargs: object) -> None:
	"""Default callback for controls that are not connected yet."""


class ActionFrame(ttk.Frame):
	"""Provide execution, undo, cancellation, and progress controls."""

	def __init__(
		self,
		parent: tk.Misc,
		on_execute: Callable[[], None] = _noop,
		on_undo: Callable[[], None] = _noop,
		on_cancel: Callable[[], None] = _noop,
		**kwargs: object,
	) -> None:
		super().__init__(parent, **kwargs)
		self._on_execute = on_execute
		self._on_undo = on_undo
		self._on_cancel = on_cancel
		self._undo_enabled = False
		self._processing = False

		self._count_var = tk.StringVar(value="実行対象: 0件 / 無効: 0件 / 合計: 0件")
		self._status_var = tk.StringVar(value="")
		self._log_enabled = tk.BooleanVar(value=True)

		self._build_widgets()

	def _build_widgets(self) -> None:
		ttk.Label(self, textvariable=self._count_var).grid(
			row=0, column=0, padx=6, pady=6, sticky="w"
		)
		ttk.Checkbutton(
			self,
			text="ログ保存",
			variable=self._log_enabled,
		).grid(row=0, column=1, padx=6, pady=6, sticky="w")

		self.execute_button = ttk.Button(
			self,
			text="一括変換を実行",
			command=self._on_execute,
		)
		self.execute_button.grid(row=0, column=2, padx=3, pady=6)

		self.undo_button = ttk.Button(self, text="Undo", command=self._on_undo)
		self.undo_button.grid(row=0, column=3, padx=3, pady=6)
		self.undo_button.configure(state="disabled")

		self.cancel_button = ttk.Button(self, text="キャンセル", command=self._on_cancel)
		self.cancel_button.grid(row=0, column=4, padx=(3, 6), pady=6)
		self.cancel_button.configure(state="disabled")

		self.progressbar = ttk.Progressbar(self, mode="determinate", maximum=100)
		self.progressbar.grid(row=1, column=0, columnspan=5, padx=6, sticky="ew")

		ttk.Label(self, textvariable=self._status_var).grid(
			row=2, column=0, columnspan=5, padx=6, pady=(3, 6), sticky="w"
		)
		self.columnconfigure(0, weight=1)

	def set_callbacks(self, **kwargs: Callable[..., None]) -> None:
		"""Replace one or more callbacks after construction."""

		callbacks = {
			"on_execute": "_on_execute",
			"on_undo": "_on_undo",
			"on_cancel": "_on_cancel",
		}
		for name, callback in kwargs.items():
			try:
				attribute = callbacks[name]
			except KeyError as error:
				raise ValueError(f"unknown callback: {name}") from error
			setattr(self, attribute, callback)
		self.execute_button.configure(command=self._on_execute)
		self.undo_button.configure(command=self._on_undo)
		self.cancel_button.configure(command=self._on_cancel)

	def set_counts(self, executable: int, invalid: int, total: int) -> None:
		"""Update the executable, invalid, and total item counts."""

		self._count_var.set(f"実行対象: {executable}件 / 無効: {invalid}件 / 合計: {total}件")

	def set_undo_enabled(self, enabled: bool) -> None:
		"""Enable or disable Undo when the frame is not processing."""

		self._undo_enabled = enabled
		self._update_button_states()

	def get_log_enabled(self) -> bool:
		"""Return whether audit logging is enabled."""

		return bool(self._log_enabled.get())

	def set_progress(self, value: int) -> None:
		"""Set the determinate progress value."""

		self.progressbar.configure(value=value)

	def set_status(self, text: str) -> None:
		"""Update the processing status text."""

		self._status_var.set(text)

	def set_processing(self, is_processing: bool) -> None:
		"""Update control states for the processing lifecycle."""

		self._processing = is_processing
		self._update_button_states()

	def _update_button_states(self) -> None:
		if self._processing:
			self.execute_button.configure(state="disabled")
			self.undo_button.configure(state="disabled")
			self.cancel_button.configure(state="normal")
			return

		self.execute_button.configure(state="normal")
		self.undo_button.configure(state="normal" if self._undo_enabled else "disabled")
		self.cancel_button.configure(state="disabled")
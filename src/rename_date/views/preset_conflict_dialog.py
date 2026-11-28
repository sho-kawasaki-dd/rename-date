"""Dialog for choosing how to resolve preset import name conflicts."""

import tkinter as tk
from collections.abc import Sequence
from tkinter import ttk

from rename_date.services.preset_io import ConflictPolicy


class PresetConflictDialog(tk.Toplevel):
	"""Modal dialog that returns an import conflict policy or cancellation."""

	def __init__(self, parent: tk.Misc, conflicting_names: Sequence[str]) -> None:
		super().__init__(parent)
		self.result: ConflictPolicy | None = None

		self.title("同名プリセットの取込")
		self.transient(parent.winfo_toplevel())
		self.minsize(420, 280)
		self.geometry("560x380")
		self.protocol("WM_DELETE_WINDOW", self._cancel)
		self.bind("<Escape>", self._cancel_on_escape)

		content = ttk.Frame(self, padding=12)
		content.grid(row=0, column=0, sticky="nsew")
		content.columnconfigure(0, weight=1)
		content.rowconfigure(1, weight=1)

		ttk.Label(
			content,
			text=(
				"既存のプリセットと同じ名前があります。"
				"競合項目の処理を選択してください。"
			),
			wraplength=520,
			justify="left",
		).grid(row=0, column=0, pady=(0, 8), sticky="w")

		list_frame = ttk.Frame(content)
		list_frame.grid(row=1, column=0, sticky="nsew")
		list_frame.columnconfigure(0, weight=1)
		list_frame.rowconfigure(0, weight=1)

		names = tk.Listbox(list_frame, height=10, exportselection=False)
		names.grid(row=0, column=0, sticky="nsew")
		scrollbar = ttk.Scrollbar(
			list_frame,
			orient="vertical",
			command=names.yview,
		)
		scrollbar.grid(row=0, column=1, sticky="ns")
		names.configure(yscrollcommand=scrollbar.set)
		for name in conflicting_names:
			names.insert(tk.END, name)

		buttons = ttk.Frame(content)
		buttons.grid(row=2, column=0, pady=(12, 0), sticky="ew")
		for column in range(3):
			buttons.columnconfigure(column, weight=1)
		ttk.Button(
			buttons,
			text="上書き",
			command=lambda: self._finish(ConflictPolicy.OVERWRITE),
		).grid(row=0, column=0, padx=(0, 4), sticky="ew")
		ttk.Button(
			buttons,
			text="スキップ",
			command=lambda: self._finish(ConflictPolicy.SKIP),
		).grid(row=0, column=1, padx=4, sticky="ew")
		cancel_button = ttk.Button(
			buttons,
			text="キャンセル",
			command=self._cancel,
		)
		cancel_button.grid(row=0, column=2, padx=(4, 0), sticky="ew")

		self.columnconfigure(0, weight=1)
		self.rowconfigure(0, weight=1)
		self.grab_set()
		cancel_button.focus_set()

	def _finish(self, result: ConflictPolicy | None) -> None:
		self.result = result
		self.destroy()

	def _cancel(self) -> None:
		self._finish(None)

	def _cancel_on_escape(self, event: tk.Event) -> str:
		if event.keysym == "Escape":
			self._cancel()
			return "break"
		return ""

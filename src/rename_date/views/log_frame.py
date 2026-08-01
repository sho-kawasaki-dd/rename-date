"""Audit log table and log folder controls."""

from collections.abc import Callable
import tkinter as tk
from tkinter import ttk
from typing import Any

from rename_date.models.log_entry import LogEntry


def _noop() -> None:
	"""Default callback for controls that are not connected yet."""


class LogFrame(ttk.Frame):
	"""Display audit log entries in reverse chronological order."""

	def __init__(self, parent: tk.Misc, **kwargs: Any) -> None:
		super().__init__(parent, **kwargs)
		self._on_refresh: Callable[[], None] = _noop
		self._on_open_folder: Callable[[], None] = _noop

		self.refresh_button = ttk.Button(self, text="更新", command=self._on_refresh)
		self.refresh_button.grid(row=0, column=0, padx=(6, 3), pady=6, sticky="w")
		self.open_folder_button = ttk.Button(
			self,
			text="ログフォルダを開く",
			command=self._on_open_folder,
		)
		self.open_folder_button.grid(row=0, column=1, padx=3, pady=6, sticky="w")

		self.tree = ttk.Treeview(
			self,
			columns=(
				"timestamp",
				"session_id",
				"action",
				"status",
				"original_path",
				"target_path",
				"message",
			),
			show="headings",
			selectmode="browse",
		)
		column_headers = {
			"timestamp": "日時",
			"session_id": "セッションID",
			"action": "操作",
			"status": "状態",
			"original_path": "変更前パス",
			"target_path": "変更後パス",
			"message": "メッセージ",
		}
		for column, heading in column_headers.items():
			self.tree.heading(column, text=heading)

		self.tree.column("timestamp", width=170, minwidth=140, stretch=False)
		self.tree.column("session_id", width=100, minwidth=80, stretch=False)
		self.tree.column("action", width=80, minwidth=60, stretch=False)
		self.tree.column("status", width=90, minwidth=70, stretch=False)
		self.tree.column("original_path", width=260, minwidth=140)
		self.tree.column("target_path", width=260, minwidth=140)
		self.tree.column("message", width=220, minwidth=100)
		self.tree.grid(row=1, column=0, columnspan=2, sticky="nsew")

		scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
		scrollbar.grid(row=1, column=2, sticky="ns")
		self.tree.configure(yscrollcommand=scrollbar.set)

		self.columnconfigure(1, weight=1)
		self.rowconfigure(1, weight=1)

	def set_callbacks(
		self,
		*,
		on_refresh: Callable[[], None],
		on_open_folder: Callable[[], None],
	) -> None:
		"""Connect the log controls to their controller callbacks."""
		self._on_refresh = on_refresh
		self._on_open_folder = on_open_folder
		self.refresh_button.configure(command=self._on_refresh)
		self.open_folder_button.configure(command=self._on_open_folder)

	def set_entries(self, entries: list[LogEntry]) -> None:
		"""Replace the table contents with newest entries first."""
		self.tree.delete(*self.tree.get_children())
		if not entries:
			self.tree.insert("", "end", values=("", "", "", "", "", "", "ログがありません"))
			return

		for entry in reversed(entries):
			self.tree.insert(
				"",
				"end",
				values=(
					entry.timestamp,
					entry.session_id,
					entry.action,
					entry.status,
					entry.original_path,
					entry.target_path,
					entry.message,
				),
			)
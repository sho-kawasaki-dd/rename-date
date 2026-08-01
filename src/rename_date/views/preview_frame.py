"""Preview table for planned file renames."""

from pathlib import Path
import tkinter as tk
from tkinter import ttk

from rename_date.models.rename_item import ItemStatus, RenameItem


class PreviewFrame(ttk.Frame):
	"""Display rename items in a read-only tree view."""

	def __init__(self, parent: tk.Misc, **kwargs: object) -> None:
		super().__init__(parent, **kwargs)

		self.tree = ttk.Treeview(
			self,
			columns=("status", "original_name", "target_name", "path"),
			show="headings",
			selectmode="browse",
		)
		column_headers = {
			"status": "状態",
			"original_name": "変更前ファイル名",
			"target_name": "変更後ファイル名",
			"path": "パス",
		}
		for column, heading in column_headers.items():
			self.tree.heading(column, text=heading)

		self.tree.column("status", width=110, minwidth=80, stretch=False)
		self.tree.column("original_name", width=220, minwidth=120)
		self.tree.column("target_name", width=220, minwidth=120)
		self.tree.column("path", width=360, minwidth=160)
		self.tree.tag_configure("invalid", foreground="gray")
		self.tree.tag_configure("conflict", background="#fff8b0")
		self.tree.grid(row=0, column=0, sticky="nsew")

		scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
		scrollbar.grid(row=0, column=1, sticky="ns")
		self.tree.configure(yscrollcommand=scrollbar.set)

		self.columnconfigure(0, weight=1)
		self.rowconfigure(0, weight=1)

	def set_items(self, items: list[RenameItem], base_dir: Path | None = None) -> None:
		"""Replace the preview rows with the supplied rename items."""

		self.tree.delete(*self.tree.get_children())
		if not items:
			self.tree.insert("", "end", values=("", "", "対象がありません", ""))
			return

		for item in items:
			path_text = self._format_parent_path(item.original_path, base_dir)
			tags: list[str] = []
			if item.status is ItemStatus.INVALID_DATE:
				tags.append("invalid")
			if item.status is ItemStatus.RESOLVED_CONFLICT:
				tags.append("conflict")
			self.tree.insert(
				"",
				"end",
				values=(
					item.status.value,
					item.original_name,
					item.target_name,
					path_text,
				),
				tags=tuple(tags),
			)

	@staticmethod
	def _format_parent_path(path: Path, base_dir: Path | None) -> str:
		if base_dir is not None:
			try:
				return str(path.parent.relative_to(base_dir))
			except ValueError:
				pass
		return str(path.parent)
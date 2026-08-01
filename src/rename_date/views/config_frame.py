"""Configuration controls for targets and preset selection."""

from collections.abc import Callable
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from tkinterdnd2 import DND_FILES

from rename_date.models.output_template_entry import OutputTemplateEntry
from rename_date.models.pattern_entry import PatternEntry
from rename_date.views.output_template_dialog import OutputTemplateEditDialog
from rename_date.views.pattern_dialog import PatternEditDialog


def _noop(*args: object, **kwargs: object) -> None:
	"""Default callback for controls that are not connected yet."""


class ConfigFrame(ttk.Frame):
	"""Frame for selecting targets and editing preset selections."""

	def __init__(
		self,
		parent: tk.Misc,
		on_pattern_save: Callable[[PatternEntry], None] = _noop,
		on_pattern_delete: Callable[[str], None] = _noop,
		on_template_save: Callable[[OutputTemplateEntry], None] = _noop,
		on_template_delete: Callable[[str], None] = _noop,
		on_preview_request: Callable[[], None] = _noop,
		**kwargs: object,
	) -> None:
		super().__init__(parent, **kwargs)
		self._on_pattern_save = on_pattern_save
		self._on_pattern_delete = on_pattern_delete
		self._on_template_save = on_template_save
		self._on_template_delete = on_template_delete
		self._on_preview_request = on_preview_request

		self._targets: list[Path] = []
		self._patterns: list[PatternEntry] = []
		self._templates: list[OutputTemplateEntry] = []

		self._build_target_section()
		self._build_pattern_section()
		self._build_template_section()

	def _build_target_section(self) -> None:
		target_section = ttk.LabelFrame(self, text="Targets", padding=6)
		target_section.grid(row=0, column=0, columnspan=2, padx=6, pady=(6, 3), sticky="nsew")
		target_section.columnconfigure(0, weight=1)
		target_section.rowconfigure(0, weight=1)

		self.target_listbox = tk.Listbox(target_section, height=4, exportselection=False)
		self.target_listbox.grid(row=0, column=0, rowspan=2, sticky="nsew")
		target_scrollbar = ttk.Scrollbar(
			target_section,
			orient="vertical",
			command=self.target_listbox.yview,
		)
		target_scrollbar.grid(row=0, column=1, rowspan=2, sticky="ns")
		self.target_listbox.configure(yscrollcommand=target_scrollbar.set)
		self.target_listbox.drop_target_register(DND_FILES)
		self.target_listbox.dnd_bind("<<Drop>>", self._on_drop)

		ttk.Button(
			target_section,
			text="Choose folder...",
			command=self._choose_folder,
		).grid(row=0, column=2, padx=(8, 0), pady=(0, 4), sticky="ew")
		ttk.Button(
			target_section,
			text="Remove selected",
			command=self._remove_selected_targets,
		).grid(row=1, column=2, padx=(8, 0), sticky="ew")

	def _build_pattern_section(self) -> None:
		pattern_section = ttk.LabelFrame(self, text="Pattern presets", padding=6)
		pattern_section.grid(row=1, column=0, padx=(6, 3), pady=3, sticky="nsew")
		pattern_section.columnconfigure(0, weight=1)
		pattern_section.rowconfigure(0, weight=1)

		self.pattern_listbox = tk.Listbox(
			pattern_section,
			selectmode="extended",
			height=5,
			exportselection=False,
		)
		self.pattern_listbox.grid(row=0, column=0, rowspan=4, sticky="nsew")

		ttk.Button(pattern_section, text="New", command=self._new_pattern).grid(
			row=0, column=1, padx=(8, 0), sticky="ew"
		)
		ttk.Button(pattern_section, text="Edit", command=self._edit_pattern).grid(
			row=1, column=1, padx=(8, 0), pady=4, sticky="ew"
		)
		ttk.Button(pattern_section, text="Delete", command=self._delete_pattern).grid(
			row=2, column=1, padx=(8, 0), sticky="ew"
		)

	def _build_template_section(self) -> None:
		template_section = ttk.LabelFrame(self, text="Output template", padding=6)
		template_section.grid(row=1, column=1, padx=(3, 6), pady=3, sticky="nsew")
		template_section.columnconfigure(0, weight=1)

		self.template_combobox = ttk.Combobox(template_section, state="readonly")
		self.template_combobox.grid(row=0, column=0, sticky="ew")

		buttons = ttk.Frame(template_section)
		buttons.grid(row=1, column=0, pady=(8, 0), sticky="e")
		ttk.Button(buttons, text="New", command=self._new_template).grid(row=0, column=0, padx=(0, 4))
		ttk.Button(buttons, text="Edit", command=self._edit_template).grid(row=0, column=1, padx=4)
		ttk.Button(buttons, text="Delete", command=self._delete_template).grid(row=0, column=2, padx=(4, 0))

		ttk.Button(self, text="Refresh preview", command=self._request_preview).grid(
			row=2, column=0, columnspan=2, padx=6, pady=(3, 6), sticky="e"
		)

		self.columnconfigure(0, weight=1)
		self.columnconfigure(1, weight=1)
		self.rowconfigure(0, weight=1)
		self.rowconfigure(1, weight=1)

	def set_callbacks(self, **kwargs: Callable[..., None]) -> None:
		"""Replace one or more callbacks after construction."""

		callbacks = {
			"on_pattern_save": "_on_pattern_save",
			"on_pattern_delete": "_on_pattern_delete",
			"on_template_save": "_on_template_save",
			"on_template_delete": "_on_template_delete",
			"on_preview_request": "_on_preview_request",
		}
		for name, callback in kwargs.items():
			try:
				attribute = callbacks[name]
			except KeyError as error:
				raise ValueError(f"unknown callback: {name}") from error
			setattr(self, attribute, callback)

	def get_targets(self) -> list[Path]:
		"""Return the currently selected target paths."""

		return list(self._targets)

	def set_patterns(self, entries: list[PatternEntry]) -> None:
		"""Replace the pattern preset list and clear its selection."""

		self._patterns = list(entries)
		self.pattern_listbox.delete(0, tk.END)
		for entry in self._patterns:
			self.pattern_listbox.insert(tk.END, entry.name)

	def get_selected_patterns(self) -> list[PatternEntry]:
		"""Return selected patterns in display order."""

		return [self._patterns[index] for index in self.pattern_listbox.curselection()]

	def set_templates(self, entries: list[OutputTemplateEntry]) -> None:
		"""Replace the output-template choices and select the first one."""

		self._templates = list(entries)
		self.template_combobox.configure(values=[entry.name for entry in self._templates])
		if self._templates:
			self.template_combobox.current(0)
		else:
			self.template_combobox.set("")

	def get_selected_template(self) -> OutputTemplateEntry | None:
		"""Return the selected output template, if one exists."""

		index = self.template_combobox.current()
		if index < 0 or index >= len(self._templates):
			return None
		return self._templates[index]

	def _choose_folder(self) -> None:
		selected = filedialog.askdirectory(parent=self.winfo_toplevel())
		if selected:
			self._add_targets([Path(selected)])

	def _request_preview(self) -> None:
		self._on_preview_request()

	def _on_drop(self, event: tk.Event) -> None:
		paths = self._parse_drop_data(str(event.data))
		self._add_targets([Path(path) for path in paths])

	@staticmethod
	def _parse_drop_data(data: str) -> list[str]:
		"""Split a Tk D&D list, preserving spaces inside braced paths."""

		try:
			interpreter = tk.Tcl()
			return list(interpreter.splitlist(data))
		except tk.TclError:
			return data.split()

	def _add_targets(self, paths: list[Path]) -> None:
		known = {path.resolve().as_posix().casefold() for path in self._targets}
		for path in paths:
			resolved = path.resolve()
			key = resolved.as_posix().casefold()
			if key in known:
				continue
			self._targets.append(resolved)
			self.target_listbox.insert(tk.END, str(resolved))
			known.add(key)

	def _remove_selected_targets(self) -> None:
		selected = list(self.target_listbox.curselection())
		for index in reversed(selected):
			del self._targets[index]
			self.target_listbox.delete(index)

	def _new_pattern(self) -> None:
		dialog = PatternEditDialog(self, initial=None)
		self.wait_window(dialog)
		if dialog.result is not None:
			self._on_pattern_save(dialog.result)

	def _edit_pattern(self) -> None:
		selected = self.pattern_listbox.curselection()
		if not selected:
			return
		dialog = PatternEditDialog(self, initial=self._patterns[selected[0]])
		self.wait_window(dialog)
		if dialog.result is not None:
			self._on_pattern_save(dialog.result)

	def _delete_pattern(self) -> None:
		selected = self.pattern_listbox.curselection()
		if not selected:
			return
		entry = self._patterns[selected[0]]
		if messagebox.askyesno(
			"Delete pattern preset",
			f'Delete pattern preset "{entry.name}"?',
			parent=self.winfo_toplevel(),
		):
			self._on_pattern_delete(entry.name)

	def _new_template(self) -> None:
		dialog = OutputTemplateEditDialog(self, initial=None)
		self.wait_window(dialog)
		if dialog.result is not None:
			self._on_template_save(dialog.result)

	def _edit_template(self) -> None:
		index = self.template_combobox.current()
		if index < 0 or index >= len(self._templates):
			return
		dialog = OutputTemplateEditDialog(self, initial=self._templates[index])
		self.wait_window(dialog)
		if dialog.result is not None:
			self._on_template_save(dialog.result)

	def _delete_template(self) -> None:
		index = self.template_combobox.current()
		if index < 0 or index >= len(self._templates):
			return
		entry = self._templates[index]
		if messagebox.askyesno(
			"Delete output template",
			f'Delete output template "{entry.name}"?',
			parent=self.winfo_toplevel(),
		):
			self._on_template_delete(entry.name)
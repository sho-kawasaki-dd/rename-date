"""Application root window and top-level view layout."""

from collections.abc import Callable
from pathlib import Path
import tkinter as tk
from tkinter import filedialog

from tkinterdnd2 import TkinterDnD
from tkinter import ttk

from rename_date import config
from rename_date.views.action_frame import ActionFrame
from rename_date.views.config_frame import ConfigFrame, PresetKind
from rename_date.views.log_frame import LogFrame
from rename_date.views.preview_frame import PreviewFrame


class MainWindow(TkinterDnD.Tk):
	"""Create the drag-and-drop application window."""

	def __init__(self) -> None:
		super().__init__()
		self.title("rename-date")
		self.geometry("900x600")
		self.minsize(700, 450)
		self._on_preset_export: Callable[[PresetKind], None] | None = None
		self._on_preset_import: Callable[[PresetKind], None] | None = None
		self._build_menu()

		self.notebook = ttk.Notebook(self)
		self.notebook.grid(row=0, column=0, sticky="nsew")

		main_tab = ttk.Frame(self.notebook)
		self.notebook.add(main_tab, text="メイン")

		self.config_frame = ConfigFrame(main_tab)
		self.config_frame.grid(row=0, column=0, padx=6, pady=(6, 3), sticky="ew")

		self.preview_frame = PreviewFrame(main_tab)
		self.preview_frame.grid(row=1, column=0, padx=6, pady=3, sticky="nsew")

		self.action_frame = ActionFrame(main_tab)
		self.action_frame.grid(row=2, column=0, padx=6, pady=(3, 6), sticky="ew")

		self.log_frame = LogFrame(self.notebook)
		self.notebook.add(self.log_frame, text="ログ")

		self.columnconfigure(0, weight=1)
		self.rowconfigure(0, weight=1)
		main_tab.columnconfigure(0, weight=1)
		main_tab.rowconfigure(1, weight=1)

	def _build_menu(self) -> None:
		menubar = tk.Menu(self, tearoff=False)
		preset_menu = tk.Menu(menubar, tearoff=False)
		menus: tuple[tuple[PresetKind, str], ...] = (
			("pattern", "入力パターン"),
			("single_template", "単日出力テンプレート"),
			("range_template", "期間出力テンプレート"),
		)
		for kind, label in menus:
			submenu = tk.Menu(preset_menu, tearoff=False)
			submenu.add_command(
				label="JSONに保存...",
				command=lambda preset_kind=kind: self._request_preset_export(preset_kind),
			)
			submenu.add_command(
				label="JSONから取込...",
				command=lambda preset_kind=kind: self._request_preset_import(preset_kind),
			)
			preset_menu.add_cascade(label=label, menu=submenu)
		menubar.add_cascade(label="プリセット", menu=preset_menu)
		self.config(menu=menubar)

	def set_preset_callbacks(
		self,
		*,
		on_export: Callable[[PresetKind], None],
		on_import: Callable[[PresetKind], None],
	) -> None:
		"""Connect preset menu actions to their controller handlers."""

		self._on_preset_export = on_export
		self._on_preset_import = on_import

	def _request_preset_export(self, kind: PresetKind) -> None:
		if self._on_preset_export is not None:
			self._on_preset_export(kind)

	def _request_preset_import(self, kind: PresetKind) -> None:
		if self._on_preset_import is not None:
			self._on_preset_import(kind)

	def choose_preset_export_path(self, kind: PresetKind) -> Path | None:
		"""Ask where to export the selected preset category."""

		filename = self._preset_filename(kind)
		selected = filedialog.asksaveasfilename(
			parent=self,
			title=f"{self._preset_label(kind)}をJSONに保存",
			defaultextension=".json",
			confirmoverwrite=False,
			filetypes=(("JSONファイル", "*.json"), ("すべてのファイル", "*.*")),
			initialfile=filename,
		)
		return Path(selected) if selected else None

	def choose_preset_import_path(self, kind: PresetKind) -> Path | None:
		"""Ask which preset JSON file to import."""

		selected = filedialog.askopenfilename(
			parent=self,
			title=f"{self._preset_label(kind)}をJSONから取込",
			filetypes=(("JSONファイル", "*.json"), ("すべてのファイル", "*.*")),
		)
		return Path(selected) if selected else None

	@staticmethod
	def _preset_label(kind: PresetKind) -> str:
		return {
			"pattern": "入力パターン",
			"single_template": "単日出力テンプレート",
			"range_template": "期間出力テンプレート",
		}[kind]

	@staticmethod
	def _preset_filename(kind: PresetKind) -> str:
		return {
			"pattern": config.PATTERNS_FILE_NAME,
			"single_template": config.OUTPUT_TEMPLATES_FILE_NAME,
			"range_template": config.RANGE_OUTPUT_TEMPLATES_FILE_NAME,
		}[kind]
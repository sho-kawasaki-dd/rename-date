"""Application root window and top-level view layout."""

from tkinterdnd2 import TkinterDnD
from tkinter import ttk

from rename_date.views.action_frame import ActionFrame
from rename_date.views.config_frame import ConfigFrame
from rename_date.views.log_frame import LogFrame
from rename_date.views.preview_frame import PreviewFrame


class MainWindow(TkinterDnD.Tk):
	"""Create the drag-and-drop application window."""

	def __init__(self) -> None:
		super().__init__()
		self.title("rename-date")
		self.geometry("900x600")
		self.minsize(700, 450)

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
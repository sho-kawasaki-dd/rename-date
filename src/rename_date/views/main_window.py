"""Application root window and top-level view layout."""

from tkinterdnd2 import TkinterDnD

from rename_date.views.action_frame import ActionFrame
from rename_date.views.config_frame import ConfigFrame
from rename_date.views.preview_frame import PreviewFrame


class MainWindow(TkinterDnD.Tk):
	"""Create the drag-and-drop application window."""

	def __init__(self) -> None:
		super().__init__()
		self.title("rename-date")
		self.geometry("900x600")
		self.minsize(700, 450)

		self.config_frame = ConfigFrame(self)
		self.config_frame.grid(row=0, column=0, padx=6, pady=(6, 3), sticky="ew")

		self.preview_frame = PreviewFrame(self)
		self.preview_frame.grid(row=1, column=0, padx=6, pady=3, sticky="nsew")

		self.action_frame = ActionFrame(self)
		self.action_frame.grid(row=2, column=0, padx=6, pady=(3, 6), sticky="ew")

		self.columnconfigure(0, weight=1)
		self.rowconfigure(1, weight=1)
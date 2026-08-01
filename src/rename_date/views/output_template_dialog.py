"""Dialog for creating and editing output-template presets."""

import tkinter as tk
from tkinter import ttk

from rename_date.models.output_template_entry import OutputTemplateEntry
from rename_date.services.validation import InvalidTemplateError, validate_output_template


class OutputTemplateEditDialog(tk.Toplevel):
    """Modal dialog that edits an output-template preset."""

    def __init__(
        self,
        parent: tk.Misc,
        initial: OutputTemplateEntry | None = None,
    ) -> None:
        super().__init__(parent)
        self.result: OutputTemplateEntry | None = None
        self._editing = initial is not None

        self.title("Output template preset")
        self.transient(parent.winfo_toplevel())
        self.protocol("WM_DELETE_WINDOW", self._cancel)

        self._name_var = tk.StringVar(value=initial.name if initial else "")
        self._template_var = tk.StringVar(value=initial.template if initial else "")

        content = ttk.Frame(self, padding=12)
        content.grid(row=0, column=0, sticky="nsew")
        content.columnconfigure(1, weight=1)

        ttk.Label(content, text="Name").grid(row=0, column=0, padx=(0, 8), pady=(0, 8), sticky="w")
        name_entry = ttk.Entry(content, textvariable=self._name_var, width=40)
        name_entry.grid(row=0, column=1, pady=(0, 8), sticky="ew")
        if self._editing:
            name_entry.state(["readonly"])

        ttk.Label(content, text="Template").grid(row=1, column=0, padx=(0, 8), pady=(0, 8), sticky="w")
        template_entry = ttk.Entry(content, textvariable=self._template_var, width=40)
        template_entry.grid(row=1, column=1, pady=(0, 8), sticky="ew")

        self._error_label = ttk.Label(content, foreground="red")
        self._error_label.grid(row=2, column=0, columnspan=2, sticky="w")

        buttons = ttk.Frame(content)
        buttons.grid(row=3, column=0, columnspan=2, pady=(12, 0), sticky="e")
        ttk.Button(buttons, text="OK", command=self._save).grid(row=0, column=0, padx=(0, 8))
        ttk.Button(buttons, text="Cancel", command=self._cancel).grid(row=0, column=1)

        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.grab_set()
        template_entry.focus_set()

    def _save(self) -> None:
        name = self._name_var.get()
        template = self._template_var.get()
        try:
            validate_output_template(template)
        except InvalidTemplateError as error:
            self._error_label.configure(text=str(error))
            return

        self.result = OutputTemplateEntry(name=name, template=template)
        self.destroy()

    def _cancel(self) -> None:
        self.result = None
        self.destroy()
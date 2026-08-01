"""Application entry point."""

import logging
import tkinter as tk
from tkinter import messagebox

from rename_date.controllers.app_controller import AppController
from rename_date.services.log_service import LogService
from rename_date.services.output_template_service import OutputTemplateService
from rename_date.services.pattern_service import PatternService
from rename_date.services.rename_service import RenameService
from rename_date.services.scanner_service import ScannerService
from rename_date.services.undo_service import UndoService
from rename_date.single_instance import SingleInstanceGuard
from rename_date.views.main_window import MainWindow


def main() -> None:
    log_service: LogService | None = None
    try:
        with SingleInstanceGuard() as guard:
            if guard.already_running:
                if not guard.activate_existing_window():
                    root = tk.Tk()
                    root.withdraw()
                    try:
                        messagebox.showinfo("rename-date", "既に起動しています", parent=root)
                    finally:
                        root.destroy()
                return

            pattern_service = PatternService()
            output_template_service = OutputTemplateService()
            log_service = LogService()
            window = MainWindow()
            AppController(
                window,
                ScannerService(),
                RenameService(),
                UndoService(),
                log_service,
                pattern_service,
                output_template_service,
            )
            window.mainloop()
    finally:
        if log_service is not None:
            log_service.close()
        logging.shutdown()
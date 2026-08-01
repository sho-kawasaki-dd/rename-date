# 開発用の手動確認スクリプトであり配布物には含めない。
"""Launch the Phase 2 views with representative dummy data."""

from pathlib import Path

from rename_date.models.output_template_entry import OutputTemplateEntry
from rename_date.models.pattern_entry import PatternEntry
from rename_date.models.rename_item import ItemStatus, RenameItem
from rename_date.views.main_window import MainWindow


def _print_callback(name: str):
	def callback(*args: object) -> None:
		print(f"{name}: {args}")

	return callback


def main() -> None:
	window = MainWindow()

	window.config_frame.set_callbacks(
		on_pattern_save=_print_callback("pattern save"),
		on_pattern_delete=_print_callback("pattern delete"),
		on_template_save=_print_callback("template save"),
		on_template_delete=_print_callback("template delete"),
		on_preview_request=_print_callback("preview request"),
	)
	window.action_frame.set_callbacks(
		on_execute=_print_callback("execute"),
		on_undo=_print_callback("undo"),
		on_cancel=_print_callback("cancel"),
	)

	window.config_frame.set_patterns(
		[
			PatternEntry("Date in parentheses", r"\((\d{4})\.(\d{1,2})\.(\d{1,2})\)"),
			PatternEntry("Date with spaces", r"(\d{4})-(\d{1,2})-(\d{1,2})"),
		]
	)
	window.config_frame.set_templates(
		[
			OutputTemplateEntry("Compact", "{Y}{M}{D}"),
			OutputTemplateEntry("Dashed", "{Y}-{M}-{D}"),
		]
	)

	base_dir = Path("C:/rename-date-demo")
	window.preview_frame.set_items(
		[
			RenameItem(
				base_dir / "report (2024.1.2).txt",
				base_dir / "report 20240102.txt",
			),
			RenameItem(
				base_dir / "report (2024.2.31).txt",
				base_dir / "report 20240231.txt",
				status=ItemStatus.INVALID_DATE,
			),
			RenameItem(
				base_dir / "summary (2024.3.4).txt",
				base_dir / "summary 20240304_1.txt",
				status=ItemStatus.RESOLVED_CONFLICT,
			),
		],
		base_dir=base_dir,
	)
	window.action_frame.set_counts(executable=2, invalid=1, total=3)
	window.action_frame.set_progress(66)
	window.action_frame.set_status("デモデータを表示中")
	window.action_frame.set_undo_enabled(True)

	window.mainloop()


if __name__ == "__main__":
	main()
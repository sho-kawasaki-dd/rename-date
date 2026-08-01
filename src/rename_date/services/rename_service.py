"""Execute planned file renames without overwriting existing files."""

from pathlib import Path
from threading import Event
from typing import Iterable

from rename_date.models.execution_history import ExecutionHistory
from rename_date.models.rename_item import ItemStatus, RenameItem


class RenameService:
	"""Apply executable rename items and record successful operations."""

	def execute(
		self,
		items: Iterable[RenameItem],
		cancel_event: Event | None = None,
	) -> tuple[list[RenameItem], ExecutionHistory]:
		"""Rename executable items and continue after individual failures."""
		result_items = list(items)
		successful_items: list[RenameItem] = []

		for item in result_items:
			if cancel_event is not None and cancel_event.is_set():
				break
			if not item.is_executable:
				continue

			if self._path_exists_casefold(item.target_path):
				item.status = ItemStatus.SKIPPED
				item.message = "target path already exists"
				continue

			try:
				item.original_path.rename(item.target_path)
			except FileExistsError as error:
				item.status = ItemStatus.SKIPPED
				item.message = str(error)
			except OSError as error:
				item.status = ItemStatus.ERROR
				item.message = str(error)
			else:
				item.status = ItemStatus.SUCCESS
				item.message = ""
				successful_items.append(item)

		return result_items, ExecutionHistory(items=successful_items)

	@staticmethod
	def _path_exists_casefold(path: Path) -> bool:
		if path.exists():
			return True
		try:
			folded_name = path.name.casefold()
			return any(
				entry.name.casefold() == folded_name
				for entry in path.parent.iterdir()
			)
		except OSError:
			return False
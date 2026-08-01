"""In-memory LIFO undo history for completed rename batches."""

from pathlib import Path
from collections.abc import Callable
from threading import Event

from rename_date.models.execution_history import ExecutionHistory
from rename_date.models.rename_item import ItemStatus, RenameItem


class UndoService:
	"""Store execution histories and restore the most recent one."""

	def __init__(self) -> None:
		self._histories: list[ExecutionHistory] = []

	def push(self, history: ExecutionHistory) -> None:
		"""Add a completed execution to the top of the undo stack."""
		self._histories.append(history)

	def has_history(self) -> bool:
		return bool(self._histories)

	def undo(
		self,
		cancel_event: Event | None = None,
		progress_callback: Callable[[int, int], None] | None = None,
	) -> list[RenameItem]:
		"""Restore the latest execution in reverse order."""
		if not self._histories:
			return []

		history = self._histories[-1]
		restored_items: list[RenameItem] = []
		total = len(history.items)
		for index, item in enumerate(reversed(history.items), start=1):
			if cancel_event is not None and cancel_event.is_set():
				break

			try:
				if not item.target_path.exists():
					item.status = ItemStatus.SKIPPED
					item.message = "renamed file is missing"
					restored_items.append(item)
					continue
				if self._path_exists_casefold(item.original_path):
					item.status = ItemStatus.SKIPPED
					item.message = "original path is occupied"
					restored_items.append(item)
					continue

				try:
					item.target_path.rename(item.original_path)
				except (FileNotFoundError, FileExistsError) as error:
					item.status = ItemStatus.SKIPPED
					item.message = str(error)
				except OSError as error:
					item.status = ItemStatus.ERROR
					item.message = str(error)
				else:
					item.status = ItemStatus.SUCCESS
					item.message = ""
				restored_items.append(item)
			finally:
				if progress_callback is not None:
					progress_callback(index, total)

		self._histories.pop()
		return restored_items

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
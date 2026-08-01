"""Data model for a single planned or completed rename."""

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class ItemStatus(StrEnum):
	PENDING = "PENDING"
	INVALID_DATE = "INVALID_DATE"
	RESOLVED_CONFLICT = "RESOLVED_CONFLICT"
	SUCCESS = "SUCCESS"
	SKIPPED = "SKIPPED"
	ERROR = "ERROR"


@dataclass
class RenameItem:
	original_path: Path
	target_path: Path
	status: ItemStatus = ItemStatus.PENDING
	message: str = ""

	@property
	def original_name(self) -> str:
		return self.original_path.name

	@property
	def target_name(self) -> str:
		return self.target_path.name

	@property
	def parent_dir(self) -> Path:
		return self.original_path.parent

	@property
	def is_executable(self) -> bool:
		return self.status in (ItemStatus.PENDING, ItemStatus.RESOLVED_CONFLICT)
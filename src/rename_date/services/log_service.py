"""Audit logging with size-based rotation."""

import logging
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Iterable

from rename_date import config
from rename_date.models.rename_item import RenameItem


class LogService:
	"""Write rename and undo results as UTF-8 TSV audit records."""

	def __init__(self, base_dir: Path | None = None) -> None:
		self.base_dir = base_dir if base_dir is not None else config.get_log_dir()
		self.base_dir.mkdir(parents=True, exist_ok=True)
		self.log_path = self.base_dir / "rename_log.txt"
		self.logger = logging.getLogger(config.AUDIT_LOGGER_NAME)
		self.logger.setLevel(logging.INFO)
		self.logger.propagate = False
		self.handler = self._get_handler()

	def log_rename(self, items: Iterable[RenameItem], session_id: str) -> None:
		self._log_items(items, session_id, "RENAME")

	def log_undo(self, items: Iterable[RenameItem], session_id: str) -> None:
		self._log_items(items, session_id, "UNDO")

	def close(self) -> None:
		"""Detach and close this service's logging handler."""
		if self.handler in self.logger.handlers:
			self.logger.removeHandler(self.handler)
		self.handler.close()

	def _get_handler(self) -> RotatingFileHandler:
		desired_path = self.log_path.resolve()
		for existing in list(self.logger.handlers):
			if not getattr(existing, "_rename_date_handler", False):
				continue
			existing_path = Path(getattr(existing, "baseFilename", "")).resolve()
			if existing_path == desired_path:
				return existing  # type: ignore[return-value]
			self.logger.removeHandler(existing)
			existing.close()

		handler = RotatingFileHandler(
			self.log_path,
			maxBytes=config.LOG_MAX_BYTES,
			backupCount=config.LOG_BACKUP_COUNT,
			encoding="utf-8",
			delay=True,
		)
		handler.namer = self._rotation_name
		handler.setFormatter(logging.Formatter("%(message)s"))
		handler._rename_date_handler = True  # type: ignore[attr-defined]
		self.logger.addHandler(handler)
		return handler

	@staticmethod
	def _rotation_name(path: str) -> str:
		source = Path(path)
		name, generation = source.name.rsplit(".", 1)
		if name.endswith(".txt"):
			name = name[:-4]
		return str(source.with_name(f"{name}.{generation}.txt"))

	def _log_items(
		self,
		items: Iterable[RenameItem],
		session_id: str,
		action: str,
	) -> None:
		for item in items:
			fields = (
				datetime.now().isoformat(),
				session_id,
				action,
				item.status.value,
				str(item.original_path),
				str(item.target_path),
				item.message,
			)
			self.logger.info("\t".join(self._escape(field) for field in fields))

	@staticmethod
	def _escape(value: str) -> str:
		return value.replace("\t", r"\t").replace("\r", r"\r").replace("\n", r"\n")
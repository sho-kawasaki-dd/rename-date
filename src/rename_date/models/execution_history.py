"""Data model for one batch rename execution."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime

from rename_date.models.rename_item import RenameItem


@dataclass
class ExecutionHistory:
	timestamp: datetime = field(default_factory=datetime.now)
	session_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
	items: list[RenameItem] = field(default_factory=list)
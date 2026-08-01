"""Data model for a single audit log record."""

from dataclasses import dataclass


@dataclass
class LogEntry:
	timestamp: str
	session_id: str
	action: str
	status: str
	original_path: str
	target_path: str
	message: str
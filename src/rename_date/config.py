"""Application-wide configuration values and data directories."""

import os
from pathlib import Path


DEFAULT_PATTERN_NAME = "既定 (YYYY.M.D)"
DEFAULT_PATTERN_REGEX = r"\((\d{4})\.(\d{1,2})\.(\d{1,2})\)"
DEFAULT_TEMPLATE_NAME = "既定 YYYYMMDD"
DEFAULT_OUTPUT_TEMPLATE = "{Y}{M}{D}"
DEFAULT_RANGE_TEMPLATE_NAME = "既定 YYYYMMDD-[YYYY]MMDD"
DEFAULT_RANGE_OUTPUT_TEMPLATE = "{Y}{M}{D}-{Y2}{M2}{D2}"
PATTERNS_FILE_NAME = "patterns.json"
OUTPUT_TEMPLATES_FILE_NAME = "output_templates.json"
RANGE_OUTPUT_TEMPLATES_FILE_NAME = "range_output_templates.json"
PRESET_FILE_NAMES = (
	PATTERNS_FILE_NAME,
	OUTPUT_TEMPLATES_FILE_NAME,
	RANGE_OUTPUT_TEMPLATES_FILE_NAME,
)

EXCLUDED_DIR_NAMES = {
	".git",
	".svn",
	".hg",
	"node_modules",
	"__pycache__",
	".venv",
	"venv",
	".idea",
	".vscode",
}

LOG_MAX_BYTES = 1_048_576
LOG_BACKUP_COUNT = 5
AUDIT_LOGGER_NAME = "rename_date.audit"


def get_appdata_dir() -> Path:
	"""Return the application's root directory under the user's AppData."""
	appdata = os.environ.get("APPDATA")
	if not appdata:
		appdata = str(Path.home() / "AppData" / "Roaming")
	return Path(appdata) / "rename-date"


def get_config_dir() -> Path:
	"""Return the directory used for persisted application configuration."""
	return get_appdata_dir() / "config"


def get_log_dir() -> Path:
	"""Return the directory used for application logs."""
	return get_appdata_dir() / "logs"
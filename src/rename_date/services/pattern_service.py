"""Persistence and validation for regular-expression presets."""

from pathlib import Path

from rename_date import config
from rename_date.models.pattern_entry import PatternEntry
from rename_date.services.preset_io import (
    PresetIOError,
    PresetIOReason,
    entries_from_json,
    ensure_external_preset_path,
    read_json,
    write_json_atomic,
)
from rename_date.services.validation import compile_pattern


class PatternService:
    """Manage the user's saved rename pattern presets."""

    _file_name = config.PATTERNS_FILE_NAME
    _temp_prefix = ".patterns-"

    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = base_dir if base_dir is not None else config.get_config_dir()
        self.file_path = self.base_dir / self._file_name

    def load(self) -> list[PatternEntry]:
        """Load presets, restoring the default preset when storage is invalid."""
        try:
            entries = self._read_entries(self.file_path, encoding="utf-8")
        except (OSError, TypeError, ValueError, KeyError):
            entries = [self._default_entry()]
            self.save(entries)
        return entries

    def save(self, entries: list[PatternEntry]) -> None:
        """Validate and atomically persist a non-empty preset list."""
        self._validate_entries(entries)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        write_json_atomic(
            self.file_path,
            [entry.to_dict() for entry in entries],
            self._temp_prefix,
        )

    def export_to_json(self, path: Path) -> None:
        """Export all currently stored presets to an external JSON file."""
        ensure_external_preset_path(path, self.base_dir)
        entries = self._load_strict()
        write_json_atomic(
            path,
            [entry.to_dict() for entry in entries],
            f".{path.stem}-",
        )

    def import_from_json(self, path: Path) -> list[PatternEntry]:
        """Append presets from an external JSON file and persist them once."""
        ensure_external_preset_path(path, self.base_dir)
        imported = self._read_entries(path, encoding="utf-8-sig")
        existing = self._load_strict()
        existing_names = {entry.name for entry in existing}
        for index, entry in enumerate(imported):
            if entry.name in existing_names:
                raise PresetIOError(
                    PresetIOReason.DUPLICATE_NAME,
                    f"pattern preset name already exists: {entry.name}",
                    name=entry.name,
                    index=index,
                )

        combined = [*existing, *imported]
        self._validate_entries(combined)
        self.save(combined)
        return combined

    def _load_strict(self) -> list[PatternEntry]:
        """Read internal storage without restoring defaults on failure."""
        return self._read_entries(self.file_path, encoding="utf-8")

    @classmethod
    def _read_entries(cls, path: Path, *, encoding: str) -> list[PatternEntry]:
        return cls._entries_from_json(read_json(path, encoding=encoding))

    def upsert(self, entry: PatternEntry) -> list[PatternEntry]:
        """Replace a preset with the same name or append a new preset."""
        entries = self.load()
        for index, existing in enumerate(entries):
            if existing.name == entry.name:
                entries[index] = entry
                break
        else:
            entries.append(entry)
        self.save(entries)
        return entries

    def delete(self, name: str) -> list[PatternEntry]:
        """Delete a named preset while preserving at least one preset."""
        entries = self.load()
        remaining = [entry for entry in entries if entry.name != name]
        if not remaining:
            raise ValueError("at least one pattern preset must remain")
        if len(remaining) != len(entries):
            self.save(remaining)
        return remaining

    @staticmethod
    def _default_entry() -> PatternEntry:
        return PatternEntry(
            name=config.DEFAULT_PATTERN_NAME,
            pattern=config.DEFAULT_PATTERN_REGEX,
        )

    @classmethod
    def _entries_from_json(cls, data: object) -> list[PatternEntry]:
        return entries_from_json(
            data,
            kind="pattern",
            keys=("name", "pattern"),
            entry_factory=PatternEntry.from_dict,
            validate_entries=cls._validate_entries,
        )

    @staticmethod
    def _validate_entries(entries: list[PatternEntry]) -> None:
        if not isinstance(entries, list) or not entries:
            raise ValueError("at least one pattern preset is required")

        names: set[str] = set()
        for entry in entries:
            if not isinstance(entry, PatternEntry):
                raise TypeError("entries must contain PatternEntry values")
            if not isinstance(entry.name, str) or not isinstance(entry.pattern, str):
                raise TypeError("pattern preset fields must be strings")
            if entry.name in names:
                raise ValueError("pattern preset names must be unique")
            names.add(entry.name)
            compile_pattern(entry.pattern)

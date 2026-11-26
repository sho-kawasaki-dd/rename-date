"""Persistence and validation for output-template presets."""

from pathlib import Path

from rename_date import config
from rename_date.models.output_template_entry import OutputTemplateEntry
from rename_date.services.preset_io import (
    PresetIOError,
    PresetIOReason,
    entries_from_json,
    ensure_external_preset_path,
    read_json,
    write_json_atomic,
)
from rename_date.services.validation import (
    validate_output_template,
    validate_range_output_template,
)


class OutputTemplateService:
    """Manage the user's saved output-template presets."""

    _file_name = config.OUTPUT_TEMPLATES_FILE_NAME
    _temp_prefix = ".output-templates-"

    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = base_dir if base_dir is not None else config.get_config_dir()
        self.file_path = self.base_dir / self._file_name

    def load(self) -> list[OutputTemplateEntry]:
        """Load presets, restoring the default preset when storage is invalid."""
        try:
            entries = self._read_entries(self.file_path, encoding="utf-8")
        except (OSError, TypeError, ValueError, KeyError):
            entries = [self._default_entry()]
            self.save(entries)
        return entries

    def save(self, entries: list[OutputTemplateEntry]) -> None:
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

    def import_from_json(self, path: Path) -> list[OutputTemplateEntry]:
        """Append presets from an external JSON file and persist them once."""
        ensure_external_preset_path(path, self.base_dir)
        imported = self._read_entries(path, encoding="utf-8-sig")
        existing = self._load_strict()
        existing_names = {entry.name for entry in existing}
        for index, entry in enumerate(imported):
            if entry.name in existing_names:
                raise PresetIOError(
                    PresetIOReason.DUPLICATE_NAME,
                    f"output-template preset name already exists: {entry.name}",
                    name=entry.name,
                    index=index,
                )

        combined = [*existing, *imported]
        self._validate_entries(combined)
        self.save(combined)
        return combined

    def _load_strict(self) -> list[OutputTemplateEntry]:
        """Read internal storage without restoring defaults on failure."""
        return self._read_entries(self.file_path, encoding="utf-8")

    @classmethod
    def _read_entries(
        cls,
        path: Path,
        *,
        encoding: str,
    ) -> list[OutputTemplateEntry]:
        return cls._entries_from_json(read_json(path, encoding=encoding))

    def upsert(self, entry: OutputTemplateEntry) -> list[OutputTemplateEntry]:
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

    def delete(self, name: str) -> list[OutputTemplateEntry]:
        """Delete a named preset while preserving at least one preset."""
        entries = self.load()
        remaining = [entry for entry in entries if entry.name != name]
        if not remaining:
            raise ValueError("at least one output-template preset must remain")
        if len(remaining) != len(entries):
            self.save(remaining)
        return remaining

    @classmethod
    def _default_entry(cls) -> OutputTemplateEntry:
        return OutputTemplateEntry(
            name=config.DEFAULT_TEMPLATE_NAME,
            template=config.DEFAULT_OUTPUT_TEMPLATE,
        )

    @classmethod
    def _entries_from_json(cls, data: object) -> list[OutputTemplateEntry]:
        return entries_from_json(
            data,
            kind="output-template",
            keys=("name", "template"),
            entry_factory=OutputTemplateEntry.from_dict,
            validate_entries=cls._validate_entries,
        )

    @classmethod
    def _validate_template(cls, template: str) -> None:
        validate_output_template(template)

    @classmethod
    def _validate_entries(cls, entries: list[OutputTemplateEntry]) -> None:
        if not isinstance(entries, list) or not entries:
            raise ValueError("at least one output-template preset is required")

        names: set[str] = set()
        for entry in entries:
            if not isinstance(entry, OutputTemplateEntry):
                raise TypeError("entries must contain OutputTemplateEntry values")
            if not isinstance(entry.name, str) or not isinstance(entry.template, str):
                raise TypeError("output-template preset fields must be strings")
            if entry.name in names:
                raise ValueError("output-template preset names must be unique")
            names.add(entry.name)
            cls._validate_template(entry.template)


class RangeOutputTemplateService(OutputTemplateService):
    """Manage the user's saved range-date output-template presets."""

    _file_name = config.RANGE_OUTPUT_TEMPLATES_FILE_NAME
    _temp_prefix = ".range-output-templates-"

    @classmethod
    def _default_entry(cls) -> OutputTemplateEntry:
        return OutputTemplateEntry(
            name=config.DEFAULT_RANGE_TEMPLATE_NAME,
            template=config.DEFAULT_RANGE_OUTPUT_TEMPLATE,
        )

    @classmethod
    def _validate_template(cls, template: str) -> None:
        validate_range_output_template(template)
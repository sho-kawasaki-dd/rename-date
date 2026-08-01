"""Persistence and validation for output-template presets."""

import json
import os
import tempfile
from pathlib import Path

from rename_date import config
from rename_date.models.output_template_entry import OutputTemplateEntry
from rename_date.services.validation import validate_output_template


class OutputTemplateService:
    """Manage the user's saved output-template presets."""

    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = base_dir if base_dir is not None else config.get_config_dir()
        self.file_path = self.base_dir / "output_templates.json"

    def load(self) -> list[OutputTemplateEntry]:
        """Load presets, restoring the default preset when storage is invalid."""
        try:
            with self.file_path.open("r", encoding="utf-8") as file:
                entries = self._entries_from_json(json.load(file))
        except (OSError, json.JSONDecodeError, TypeError, ValueError, KeyError):
            entries = [self._default_entry()]
            self.save(entries)
        return entries

    def save(self, entries: list[OutputTemplateEntry]) -> None:
        """Validate and atomically persist a non-empty preset list."""
        self._validate_entries(entries)
        self.base_dir.mkdir(parents=True, exist_ok=True)

        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.base_dir,
                prefix=".output-templates-",
                suffix=".tmp",
                delete=False,
            ) as file:
                temporary_path = Path(file.name)
                json.dump(
                    [entry.to_dict() for entry in entries],
                    file,
                    ensure_ascii=False,
                    indent=2,
                )
                file.write("\n")
            os.replace(temporary_path, self.file_path)
            temporary_path = None
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

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

    @staticmethod
    def _default_entry() -> OutputTemplateEntry:
        return OutputTemplateEntry(
            name=config.DEFAULT_TEMPLATE_NAME,
            template=config.DEFAULT_OUTPUT_TEMPLATE,
        )

    @classmethod
    def _entries_from_json(cls, data: object) -> list[OutputTemplateEntry]:
        if not isinstance(data, list) or not data:
            raise ValueError("output-template storage must contain a non-empty list")

        entries: list[OutputTemplateEntry] = []
        for item in data:
            if not isinstance(item, dict):
                raise TypeError("each output-template preset must be an object")
            if set(item) != {"name", "template"}:
                raise ValueError("output-template preset has an invalid schema")
            if not all(isinstance(item[key], str) for key in item):
                raise TypeError("output-template preset fields must be strings")
            entries.append(OutputTemplateEntry.from_dict(item))

        cls._validate_entries(entries)
        return entries

    @staticmethod
    def _validate_entries(entries: list[OutputTemplateEntry]) -> None:
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
            validate_output_template(entry.template)
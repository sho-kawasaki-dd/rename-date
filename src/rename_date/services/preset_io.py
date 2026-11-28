"""Shared JSON I/O helpers for preset services."""

import json
import os
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Generic, Protocol, TypeVar

from rename_date import config


class NamedPreset(Protocol):
    name: str


Entry = TypeVar("Entry", bound=NamedPreset)


class ConflictPolicy(str, Enum):
    """How an import handles names already present in the stored presets."""

    OVERWRITE = "overwrite"
    SKIP = "skip"


@dataclass(frozen=True)
class PresetImportPlan(Generic[Entry]):
    """Validated existing and imported presets, ready for conflict resolution."""

    existing_entries: tuple[Entry, ...]
    imported_entries: tuple[Entry, ...]
    conflicting_names: tuple[str, ...]


@dataclass(frozen=True)
class PresetImportResult(Generic[Entry]):
    """Resolved preset list and the counts resulting from an import."""

    updated_entries: list[Entry]
    added_count: int
    overwritten_count: int
    skipped_count: int

    @property
    def changed(self) -> bool:
        return self.added_count > 0 or self.overwritten_count > 0


def create_import_plan(
    existing_entries: list[Entry],
    imported_entries: list[Entry],
) -> PresetImportPlan[Entry]:
    """Capture existing-name conflicts in the order they occur in the import."""
    existing_names = {entry.name for entry in existing_entries}
    conflicting_names = tuple(
        entry.name for entry in imported_entries if entry.name in existing_names
    )
    return PresetImportPlan(
        existing_entries=tuple(existing_entries),
        imported_entries=tuple(imported_entries),
        conflicting_names=conflicting_names,
    )


def resolve_import_plan(
    plan: PresetImportPlan[Entry],
    policy: ConflictPolicy,
) -> PresetImportResult[Entry]:
    """Combine a validated import plan according to its conflict policy."""
    if not isinstance(policy, ConflictPolicy):
        raise ValueError("unsupported preset import conflict policy")

    updated_entries = list(plan.existing_entries)
    existing_indexes = {
        entry.name: index for index, entry in enumerate(updated_entries)
    }
    added_count = 0
    overwritten_count = 0
    skipped_count = 0

    for entry in plan.imported_entries:
        existing_index = existing_indexes.get(entry.name)
        if existing_index is None:
            existing_indexes[entry.name] = len(updated_entries)
            updated_entries.append(entry)
            added_count += 1
        elif policy is ConflictPolicy.OVERWRITE:
            updated_entries[existing_index] = entry
            overwritten_count += 1
        else:
            skipped_count += 1

    return PresetImportResult(
        updated_entries=updated_entries,
        added_count=added_count,
        overwritten_count=overwritten_count,
        skipped_count=skipped_count,
    )


class PresetIOReason(str, Enum):
    """Reason an external preset JSON operation was rejected."""

    INTERNAL_PATH = "internal_path"
    INVALID_JSON = "invalid_json"
    INVALID_FORMAT = "invalid_format"
    VALIDATION = "validation"
    DUPLICATE_NAME = "duplicate_name"


class PresetIOError(ValueError):
    """Preset JSON error with optional location and item details."""

    def __init__(
        self,
        reason: PresetIOReason,
        detail: str,
        *,
        name: str | None = None,
        index: int | None = None,
    ) -> None:
        super().__init__(detail)
        self.reason = reason
        self.name = name
        self.index = index
        self.detail = detail


def ensure_external_preset_path(path: Path, base_dir: Path) -> None:
    """Reject paths resolving to any of this installation's preset files."""
    target = os.path.normcase(str(path.resolve(strict=False)))
    for file_name in config.PRESET_FILE_NAMES:
        internal_path = os.path.normcase(
            str((base_dir / file_name).resolve(strict=False))
        )
        if target == internal_path:
            raise PresetIOError(
                PresetIOReason.INTERNAL_PATH,
                "preset JSON paths cannot target internal configuration files",
            )


def read_json(path: Path, *, encoding: str) -> object:
    """Read JSON without substituting defaults for file or parse failures."""
    try:
        with path.open("r", encoding=encoding) as file:
            return json.load(file)
    except json.JSONDecodeError as error:
        raise PresetIOError(
            PresetIOReason.INVALID_JSON,
            "preset file contains invalid JSON",
        ) from error


def entries_from_json(
    data: object,
    *,
    kind: str,
    keys: tuple[str, str],
    entry_factory: Callable[[dict[str, str]], Entry],
    validate_entries: Callable[[list[Entry]], None],
) -> list[Entry]:
    """Parse a preset array with errors annotated by item name and position."""
    if not isinstance(data, list) or not data:
        raise PresetIOError(
            PresetIOReason.INVALID_FORMAT,
            f"{kind} storage must contain a non-empty list",
        )

    entries: list[Entry] = []
    names: set[str] = set()
    for index, item in enumerate(data):
        if not isinstance(item, dict):
            raise PresetIOError(
                PresetIOReason.INVALID_FORMAT,
                f"each {kind} preset must be an object",
                index=index,
            )
        name = item.get("name")
        if set(item) != set(keys):
            raise PresetIOError(
                PresetIOReason.INVALID_FORMAT,
                f"{kind} preset has an invalid schema",
                name=name if isinstance(name, str) else None,
                index=index,
            )
        if not all(isinstance(item[key], str) for key in keys):
            raise PresetIOError(
                PresetIOReason.INVALID_FORMAT,
                f"{kind} preset fields must be strings",
                name=name if isinstance(name, str) else None,
                index=index,
            )

        entry_data = {key: item[key] for key in keys}
        entry = entry_factory(entry_data)
        if entry.name in names:
            raise PresetIOError(
                PresetIOReason.DUPLICATE_NAME,
                f"{kind} preset name is duplicated: {entry.name}",
                name=entry.name,
                index=index,
            )
        try:
            validate_entries([entry])
        except (TypeError, ValueError) as error:
            raise PresetIOError(
                PresetIOReason.VALIDATION,
                str(error),
                name=entry.name,
                index=index,
            ) from error
        names.add(entry.name)
        entries.append(entry)
    return entries


def write_json_atomic(path: Path, entries: list[dict[str, str]], prefix: str) -> None:
    """Write UTF-8 JSON through a temporary file beside the destination."""
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=prefix,
            suffix=".tmp",
            delete=False,
        ) as file:
            temporary_path = Path(file.name)
            json.dump(entries, file, ensure_ascii=False, indent=2)
            file.write("\n")
        os.replace(temporary_path, path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)

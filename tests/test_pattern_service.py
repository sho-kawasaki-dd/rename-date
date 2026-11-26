"""Tests for PatternService."""

import json
from pathlib import Path

import pytest

from rename_date import config
from rename_date.models.pattern_entry import PatternEntry
from rename_date.services.preset_io import PresetIOError, PresetIOReason
from rename_date.services.pattern_service import PatternService
from rename_date.services.validation import InvalidPatternError


def test_initial_load_creates_default_preset(tmp_path):
    service = PatternService(tmp_path)

    entries = service.load()

    assert entries == [
        PatternEntry(
            config.DEFAULT_PATTERN_NAME,
            config.DEFAULT_PATTERN_REGEX,
        )
    ]
    assert (tmp_path / "patterns.json").exists()


def test_save_and_load_json(tmp_path, default_pattern):
    service = PatternService(tmp_path)
    custom = PatternEntry("custom", default_pattern.pattern)

    service.save([default_pattern, custom])

    assert service.load() == [default_pattern, custom]
    assert json.loads((tmp_path / "patterns.json").read_text(encoding="utf-8")) == [
        default_pattern.to_dict(),
        custom.to_dict(),
    ]


def test_save_rejects_invalid_patterns(tmp_path, default_pattern):
    service = PatternService(tmp_path)

    with pytest.raises(InvalidPatternError):
        service.save([PatternEntry("bad", "(2024)")])


@pytest.mark.parametrize(
    "pattern",
    [
        r"(a)(b)(c)(d)",
        r"(a)(b)(c)(d)(e)",
        r"(a)(b)(c)(d)(e)(f)",
    ],
)
def test_save_accepts_range_patterns_with_four_to_six_groups(tmp_path, pattern):
    service = PatternService(tmp_path)

    service.save([PatternEntry("range", pattern)])
    entries = service.load()

    assert entries == [PatternEntry("range", pattern)]


@pytest.mark.parametrize("pattern", [r"(a)(b)", r"(a)(b)(c)(d)(e)(f)(g)"])
def test_save_rejects_patterns_outside_three_to_six_groups(tmp_path, pattern):
    service = PatternService(tmp_path)

    with pytest.raises(InvalidPatternError):
        service.save([PatternEntry("invalid", pattern)])


def test_broken_json_falls_back_to_default(tmp_path):
    service = PatternService(tmp_path)
    (tmp_path / "patterns.json").write_text("{broken", encoding="utf-8")

    entries = service.load()

    assert len(entries) == 1
    assert entries[0].name == config.DEFAULT_PATTERN_NAME


def test_schema_error_falls_back_to_default(tmp_path):
    service = PatternService(tmp_path)
    (tmp_path / "patterns.json").write_text("{}", encoding="utf-8")

    entries = service.load()

    assert len(entries) == 1
    assert entries[0].name == config.DEFAULT_PATTERN_NAME


def test_upsert_replaces_same_name(tmp_path, default_pattern):
    service = PatternService(tmp_path)
    service.save([default_pattern])
    replacement = PatternEntry(
        default_pattern.name,
        default_pattern.pattern,
    )

    entries = service.upsert(replacement)

    assert entries == [replacement]
    assert service.load() == [replacement]


def test_delete_rejects_removing_last_preset(tmp_path, default_pattern):
    service = PatternService(tmp_path)
    service.save([default_pattern])

    with pytest.raises(ValueError):
        service.delete(default_pattern.name)


def test_export_and_import_preserve_order_and_utf8_without_bom(
    tmp_path,
    default_pattern,
):
    source_service = PatternService(tmp_path / "source")
    destination_service = PatternService(tmp_path / "destination")
    entries = [
        default_pattern,
        PatternEntry("日本語", r"(\d{4})-(\d{2})-(\d{2})"),
    ]
    source_service.save(entries)

    export_path = tmp_path / "export.json"
    source_service.export_to_json(export_path)
    exported_bytes = export_path.read_bytes()
    assert not exported_bytes.startswith(b"\xef\xbb\xbf")
    assert json.loads(exported_bytes.decode("utf-8")) == [
        entry.to_dict() for entry in entries
    ]

    destination_service.save([PatternEntry("existing", r"(\d{4})(\d{2})(\d{2})")])
    import_path = tmp_path / "import.json"
    import_path.write_bytes(b"\xef\xbb\xbf" + exported_bytes)
    source_bytes = import_path.read_bytes()

    imported = destination_service.import_from_json(import_path)

    assert imported == [
        PatternEntry("existing", r"(\d{4})(\d{2})(\d{2})"),
        *entries,
    ]
    assert import_path.read_bytes() == source_bytes
    assert not destination_service.file_path.read_bytes().startswith(b"\xef\xbb\xbf")


def test_import_rejects_duplicate_name_without_changing_internal_file(
    tmp_path,
    default_pattern,
):
    service = PatternService(tmp_path / "config")
    service.save([default_pattern])
    original_bytes = service.file_path.read_bytes()
    import_path = tmp_path / "duplicate.json"
    import_path.write_text(
        json.dumps([default_pattern.to_dict()]),
        encoding="utf-8",
    )

    with pytest.raises(PresetIOError) as error:
        service.import_from_json(import_path)

    assert error.value.reason is PresetIOReason.DUPLICATE_NAME
    assert error.value.name == default_pattern.name
    assert error.value.index == 0
    assert service.file_path.read_bytes() == original_bytes


def test_import_rejects_late_invalid_entry_without_changing_either_file(
    tmp_path,
    default_pattern,
):
    service = PatternService(tmp_path / "config")
    service.save([default_pattern])
    original_bytes = service.file_path.read_bytes()
    import_path = tmp_path / "invalid.json"
    import_path.write_text(
        json.dumps(
            [
                {"name": "valid", "pattern": r"(\d{4})(\d{2})(\d{2})"},
                {"name": "invalid", "pattern": r"(\d{4})"},
            ]
        ),
        encoding="utf-8",
    )
    imported_bytes = import_path.read_bytes()

    with pytest.raises(PresetIOError) as error:
        service.import_from_json(import_path)

    assert error.value.reason is PresetIOReason.VALIDATION
    assert error.value.name == "invalid"
    assert error.value.index == 1
    assert service.file_path.read_bytes() == original_bytes
    assert import_path.read_bytes() == imported_bytes


@pytest.mark.parametrize("operation", ["export", "import"])
def test_json_operations_reject_internal_preset_paths(
    tmp_path,
    default_pattern,
    operation,
):
    service = PatternService(tmp_path / "config")
    service.save([default_pattern])
    path = service.file_path

    with pytest.raises(PresetIOError) as error:
        if operation == "export":
            service.export_to_json(path)
        else:
            service.import_from_json(path)

    assert error.value.reason is PresetIOReason.INTERNAL_PATH


@pytest.mark.parametrize(
    "file_name",
    ["patterns.json", "output_templates.json", "range_output_templates.json"],
)
def test_json_operations_reject_case_insensitive_and_relative_internal_paths(
    tmp_path,
    monkeypatch,
    default_pattern,
    file_name,
):
    base_dir = tmp_path / "config"
    service = PatternService(base_dir)
    service.save([default_pattern])
    monkeypatch.chdir(base_dir)
    relative_path = Path(file_name)
    differently_cased_path = base_dir / file_name.upper()

    for path in (relative_path, differently_cased_path):
        with pytest.raises(PresetIOError) as error:
            service.export_to_json(path)
        assert error.value.reason is PresetIOReason.INTERNAL_PATH


def test_json_operations_do_not_restore_missing_internal_storage(tmp_path):
    service = PatternService(tmp_path / "config")
    import_path = tmp_path / "valid.json"
    import_path.write_text(
        json.dumps([{"name": "custom", "pattern": r"(\d{4})(\d{2})(\d{2})"}]),
        encoding="utf-8",
    )

    with pytest.raises(FileNotFoundError):
        service.export_to_json(tmp_path / "export.json")
    with pytest.raises(FileNotFoundError):
        service.import_from_json(import_path)

    assert not service.file_path.exists()
    assert import_path.exists()
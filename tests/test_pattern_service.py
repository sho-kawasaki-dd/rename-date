"""Tests for PatternService."""

import json

import pytest

from rename_date import config
from rename_date.models.pattern_entry import PatternEntry
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
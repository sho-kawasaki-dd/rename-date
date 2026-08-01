"""Tests for ScannerService."""

from pathlib import Path
from threading import Event

import pytest

from rename_date.models.rename_item import ItemStatus
from rename_date.services.scanner_service import ScannerService
from rename_date.services.validation import InvalidPatternError, InvalidTemplateError


def scan_default(targets, default_pattern):
    return ScannerService().scan(
        targets,
        default_pattern.pattern,
        default_pattern.output_template,
    )


def test_scans_sample_tree_and_resolves_existing_conflict(sample_tree, default_pattern):
    items = scan_default([sample_tree], default_pattern)
    by_name = {item.original_name: item for item in items}

    assert by_name["テスト (2024.1.5).txt"].target_name == "テスト 20240105.txt"
    assert by_name["メモ (2024.12.31) v2.txt"].target_name == "メモ 20241231 v2.txt"
    assert (
        by_name["二重 (2023.1.1) と (2023.2.2).txt"].target_name
        == "二重 20230101 と 20230202.txt"
    )
    assert by_name["既存 (2024.1.5).txt"].target_name == "既存 20240105_1.txt"
    assert by_name["既存 (2024.1.5).txt"].status == ItemStatus.RESOLVED_CONFLICT
    assert by_name["報告 (2025.3.7).pdf"].target_name == "報告 20250307.pdf"
    assert by_name["不正 (2024.13.45).txt"].status == ItemStatus.INVALID_DATE
    assert "既存 20240105.txt" not in by_name
    assert all("隠し" not in name and name != "x (2024.1.1).txt" for name in by_name)


def test_supports_custom_template_and_preserves_extension(tmp_path):
    source = tmp_path / "報告 (2025.3.7).tar.gz"
    source.write_text("sample", encoding="utf-8")

    items = ScannerService().scan(
        [source],
        r"\((\d{4})\.(\d{1,2})\.(\d{1,2})\)",
        "{Y}-{M}-{D}",
    )

    assert items[0].target_name == "報告 2025-03-07.tar.gz"


def test_excludes_unchanged_files(tmp_path):
    source = tmp_path / "20240101.txt"
    source.write_text("sample", encoding="utf-8")

    assert ScannerService().scan([source], r"(2024)(01)(01)", "{Y}{M}{D}") == []


def test_rejects_invalid_pattern_and_template(tmp_path, default_pattern):
    source = tmp_path / "file.txt"
    source.write_text("sample", encoding="utf-8")
    service = ScannerService()

    with pytest.raises(InvalidPatternError):
        service.scan([source], "(2024)", default_pattern.output_template)
    with pytest.raises(InvalidPatternError):
        service.scan([source], "(2024)(01)", default_pattern.output_template)
    with pytest.raises(InvalidTemplateError):
        service.scan([source], default_pattern.pattern, "{Y}{M}")


def test_deduplicates_mixed_folder_and_file_targets(sample_tree, default_pattern):
    selected = sample_tree / "テスト (2024.1.5).txt"
    items = scan_default([sample_tree, selected], default_pattern)

    assert sum(item.original_path == selected.resolve() for item in items) == 1


def test_cancel_event_returns_partial_results(tmp_path, default_pattern):
    source = tmp_path / "cancel (2024.1.1).txt"
    source.write_text("sample", encoding="utf-8")
    cancel_event = Event()
    cancel_event.set()

    assert (
        ScannerService().scan(
            [tmp_path],
            default_pattern.pattern,
            default_pattern.output_template,
            cancel_event,
        )
        == []
    )


def test_direct_file_applies_only_hidden_filter(tmp_path, default_pattern):
    hidden = tmp_path / ".hidden (2024.1.1).txt"
    direct = tmp_path / "node_modules" / "direct (2024.1.1).txt"
    direct.parent.mkdir()
    hidden.write_text("sample", encoding="utf-8")
    direct.write_text("sample", encoding="utf-8")

    items = scan_default([hidden, direct], default_pattern)

    assert [item.original_name for item in items] == [direct.name]


def test_skips_symbolic_links(tmp_path, default_pattern):
    target_file = tmp_path / "target (2024.1.1).txt"
    target_dir = tmp_path / "target-dir"
    target_dir.mkdir()
    target_file.write_text("sample", encoding="utf-8")
    (target_dir / "nested (2024.1.1).txt").write_text("sample", encoding="utf-8")
    file_link = tmp_path / "file-link (2024.1.1).txt"
    dir_link = tmp_path / "dir-link"
    try:
        file_link.symlink_to(target_file)
        dir_link.symlink_to(target_dir, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symbolic links are unavailable")

    names = {item.original_name for item in scan_default([tmp_path], default_pattern)}

    assert "file-link (2024.1.1).txt" not in names
    assert "nested (2024.1.1).txt" not in names


def test_resolves_collision_within_batch(tmp_path, default_pattern):
    first = tmp_path / "同名 (2024.1.2).txt"
    second = tmp_path / "同名 (2024.01.02).txt"
    first.write_text("first", encoding="utf-8")
    second.write_text("second", encoding="utf-8")

    items = scan_default([tmp_path], default_pattern)
    targets = {item.target_name for item in items}

    assert targets == {"同名 20240102.txt", "同名 20240102_1.txt"}
    assert sum(item.status == ItemStatus.RESOLVED_CONFLICT for item in items) == 1
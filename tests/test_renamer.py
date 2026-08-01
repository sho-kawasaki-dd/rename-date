"""Tests for RenameService."""

from pathlib import Path

from rename_date.models.rename_item import ItemStatus, RenameItem
from rename_date.services.rename_service import RenameService


def test_execute_renames_files_and_records_successful_history(tmp_path):
    source = tmp_path / "before.txt"
    target = tmp_path / "after.txt"
    source.write_text("sample", encoding="utf-8")

    result, history = RenameService().execute([RenameItem(source, target)])

    assert result[0].status == ItemStatus.SUCCESS
    assert history.items == result
    assert target.read_text(encoding="utf-8") == "sample"
    assert not source.exists()


def test_execute_skips_collision_injected_at_rename(monkeypatch, tmp_path):
    source = tmp_path / "before.txt"
    target = tmp_path / "after.txt"
    source.write_text("sample", encoding="utf-8")

    def raise_collision(self, destination):
        raise FileExistsError("collision")

    monkeypatch.setattr(Path, "rename", raise_collision)
    result, history = RenameService().execute([RenameItem(source, target)])

    assert result[0].status == ItemStatus.SKIPPED
    assert result[0].message == "collision"
    assert history.items == []


def test_execute_continues_after_oserror(monkeypatch, tmp_path):
    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"
    first.write_text("first", encoding="utf-8")
    second.write_text("second", encoding="utf-8")

    def raise_error(self, destination):
        raise OSError("failure")

    monkeypatch.setattr(Path, "rename", raise_error)
    result, history = RenameService().execute(
        [
            RenameItem(first, tmp_path / "first-new.txt"),
            RenameItem(second, tmp_path / "second-new.txt"),
        ]
    )

    assert [item.status for item in result] == [ItemStatus.ERROR, ItemStatus.ERROR]
    assert history.items == []


def test_execute_skips_non_executable_items(tmp_path):
    item = RenameItem(
        tmp_path / "invalid.txt",
        tmp_path / "invalid-new.txt",
        status=ItemStatus.INVALID_DATE,
    )

    result, history = RenameService().execute([item])

    assert result == [item]
    assert item.status == ItemStatus.INVALID_DATE
    assert history.items == []


def test_execute_reports_progress_for_each_result_item(tmp_path):
    first = tmp_path / "first.txt"
    first_target = tmp_path / "first-new.txt"
    first.write_text("first", encoding="utf-8")
    second = RenameItem(
        tmp_path / "invalid.txt",
        tmp_path / "invalid-new.txt",
        status=ItemStatus.INVALID_DATE,
    )
    progress: list[tuple[int, int]] = []

    RenameService().execute(
        [RenameItem(first, first_target), second],
        progress_callback=lambda done, total: progress.append((done, total)),
    )

    assert progress == [(1, 2), (2, 2)]
"""Tests for UndoService."""

from pathlib import Path

from rename_date.models.execution_history import ExecutionHistory
from rename_date.models.rename_item import ItemStatus, RenameItem
from rename_date.services.undo_service import UndoService


def make_history(root: Path, name: str) -> ExecutionHistory:
    original = root / f"{name}.txt"
    target = root / f"{name}-renamed.txt"
    original.write_text(name, encoding="utf-8")
    original.rename(target)
    return ExecutionHistory(items=[RenameItem(original, target, ItemStatus.SUCCESS)])


def test_undo_restores_in_reverse_order(monkeypatch, tmp_path):
    first_original = tmp_path / "first.txt"
    second_original = tmp_path / "second.txt"
    first_target = tmp_path / "first-renamed.txt"
    second_target = tmp_path / "second-renamed.txt"
    first_original.write_text("first", encoding="utf-8")
    second_original.write_text("second", encoding="utf-8")
    first_original.rename(first_target)
    second_original.rename(second_target)
    history = ExecutionHistory(
        items=[
            RenameItem(first_original, first_target, ItemStatus.SUCCESS),
            RenameItem(second_original, second_target, ItemStatus.SUCCESS),
        ]
    )
    calls = []
    real_rename = Path.rename

    def record_rename(self, destination):
        calls.append(self.name)
        return real_rename(self, destination)

    monkeypatch.setattr(Path, "rename", record_rename)
    service = UndoService()
    service.push(history)
    restored = service.undo()

    assert calls == ["second-renamed.txt", "first-renamed.txt"]
    assert [item.status for item in restored] == [ItemStatus.SUCCESS, ItemStatus.SUCCESS]
    assert first_original.exists() and second_original.exists()
    assert not service.has_history()


def test_undo_skips_missing_file(tmp_path):
    history = make_history(tmp_path, "missing")
    history.items[0].target_path.unlink()
    service = UndoService()
    service.push(history)

    result = service.undo()

    assert result[0].status == ItemStatus.SKIPPED
    assert service.has_history() is False


def test_undo_skips_occupied_original_path(tmp_path):
    history = make_history(tmp_path, "occupied")
    history.items[0].original_path.write_text("new file", encoding="utf-8")
    service = UndoService()
    service.push(history)

    result = service.undo()

    assert result[0].status == ItemStatus.SKIPPED
    assert history.items[0].target_path.exists()


def test_undo_uses_lifo_stack(tmp_path):
    first = make_history(tmp_path, "first")
    second = make_history(tmp_path, "second")
    service = UndoService()
    service.push(first)
    service.push(second)

    service.undo()
    assert service.has_history()
    assert (tmp_path / "second.txt").exists()
    service.undo()
    assert not service.has_history()
    assert (tmp_path / "first.txt").exists()


def test_undo_empty_stack_returns_empty_list():
    assert UndoService().undo() == []


def test_undo_reports_progress_for_each_history_item(tmp_path):
    first_original = tmp_path / "first.txt"
    second_original = tmp_path / "second.txt"
    first_target = tmp_path / "first-renamed.txt"
    second_target = tmp_path / "second-renamed.txt"
    first_original.write_text("first", encoding="utf-8")
    second_original.write_text("second", encoding="utf-8")
    first_original.rename(first_target)
    second_original.rename(second_target)
    service = UndoService()
    service.push(
        ExecutionHistory(
            items=[
                RenameItem(first_original, first_target, ItemStatus.SUCCESS),
                RenameItem(second_original, second_target, ItemStatus.SUCCESS),
            ]
        )
    )
    progress: list[tuple[int, int]] = []

    service.undo(
        progress_callback=lambda done, total: progress.append((done, total)),
    )

    assert progress == [(1, 2), (2, 2)]
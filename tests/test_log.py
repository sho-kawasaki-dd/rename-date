"""Tests for LogService."""

from pathlib import Path

from rename_date import config
from rename_date.models.rename_item import ItemStatus, RenameItem
from rename_date.services.log_service import LogService


def test_log_creates_directory_and_appends_escaped_tsv(tmp_path):
    log_dir = tmp_path / "nested" / "logs"
    service = LogService(log_dir)
    item = RenameItem(
        Path("before\tname\n.txt"),
        Path("after.txt"),
        ItemStatus.ERROR,
        "message\tline\nnext",
    )

    assert not (log_dir / "rename_log.txt").exists()
    service.log_rename([item], "session-1")
    service.log_undo([item], "session-1")
    service.close()

    lines = (log_dir / "rename_log.txt").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    fields = lines[0].split("\t")
    assert len(fields) == 7
    assert fields[1:4] == ["session-1", "RENAME", "ERROR"]
    assert r"\t" in lines[0] and r"\n" in lines[0]
    assert "UNDO" in lines[1]


def test_log_handler_is_not_duplicated(tmp_path):
    first = LogService(tmp_path)
    second = LogService(tmp_path)

    service_handlers = [
        handler
        for handler in first.logger.handlers
        if getattr(handler, "_rename_date_handler", False)
    ]
    assert len(service_handlers) == 1
    second.close()


def test_log_reads_entries_and_unescapes_fields(tmp_path):
    service = LogService(tmp_path)
    item = RenameItem(
        Path("before\tname\n.txt"),
        Path("after.txt"),
        ItemStatus.ERROR,
        "message\tline\nnext",
    )

    service.log_rename([item], "session-1")
    entries = service.read_entries()
    service.close()

    assert len(entries) == 1
    assert entries[0].session_id == "session-1"
    assert entries[0].action == "RENAME"
    assert entries[0].status == "ERROR"
    assert entries[0].original_path == "before\tname\n.txt"
    assert entries[0].message == "message\tline\nnext"


def test_log_read_skips_invalid_lines_and_missing_file(tmp_path):
    service = LogService(tmp_path)
    assert service.read_entries() == []

    service.log_path.write_text("invalid\tline\n", encoding="utf-8")
    assert service.read_entries() == []
    service.close()


def test_log_rotates_with_expected_names_and_limit(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "LOG_MAX_BYTES", 100)
    monkeypatch.setattr(config, "LOG_BACKUP_COUNT", 2)
    service = LogService(tmp_path)
    item = RenameItem(
        Path("before.txt"),
        Path("after.txt"),
        ItemStatus.SUCCESS,
        "x" * 80,
    )

    service.log_rename([item] * 10, "rotation")
    service.close()

    generations = sorted(tmp_path.glob("rename_log.*.txt"))
    assert generations
    assert len(generations) <= 2
    assert not (tmp_path / "rename_log.txt.1").exists()
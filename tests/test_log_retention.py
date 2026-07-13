from __future__ import annotations

from pathlib import Path

from diagnostics.log_retention import prune_files, rotate_file


def test_rotate_file_keeps_bounded_numbered_backups(tmp_path) -> None:
    path = tmp_path / "events.jsonl"
    path.write_text("first", encoding="utf-8")

    assert rotate_file(path, max_bytes=1, backup_count=2) is True
    assert path.exists() is False
    assert (tmp_path / "events.jsonl.1").read_text(encoding="utf-8") == "first"

    path.write_text("second", encoding="utf-8")
    rotate_file(path, max_bytes=1, backup_count=2)
    path.write_text("third", encoding="utf-8")
    rotate_file(path, max_bytes=1, backup_count=2)

    assert (tmp_path / "events.jsonl.1").read_text(encoding="utf-8") == "third"
    assert (tmp_path / "events.jsonl.2").read_text(encoding="utf-8") == "second"
    assert (tmp_path / "events.jsonl.3").exists() is False


def test_prune_files_keeps_newest_entries(tmp_path) -> None:
    paths = []
    for index in range(6):
        path = tmp_path / f"report-{index}.json"
        path.write_text(str(index), encoding="utf-8")
        path.touch()
        paths.append(path)

    removed = prune_files(tmp_path, "*.json", keep=3)

    assert removed == 3
    assert len(list(tmp_path.glob("*.json"))) == 3


def test_rotate_missing_or_small_file_is_noop(tmp_path) -> None:
    missing = tmp_path / "missing.log"
    assert rotate_file(missing, max_bytes=10) is False
    missing.write_text("small", encoding="utf-8")
    assert rotate_file(missing, max_bytes=10) is False
    assert missing.read_text(encoding="utf-8") == "small"

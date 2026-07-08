from __future__ import annotations

from pathlib import Path

from storage import data as storage_data
from storage.files import create_backup, restore_backup


def _use_sqlite(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("config.constant.APP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr("config.constant.BACKUP_DIR", str(tmp_path / "data" / "backups"))
    monkeypatch.setenv("WATCHBANE_STORAGE_BACKEND", "sqlite")


def _movie(title: str) -> dict:
    return {
        "main_info": {
            "title": title,
            "year": 2020,
            "user_score": 8,
            "country": "US",
            "media_type": "tv",
        },
        "raw_scores": {},
        "tags_vibe": {},
        "genre": {},
    }


def test_create_backup_includes_sqlite_db_when_backend_is_sqlite(tmp_path, monkeypatch) -> None:
    _use_sqlite(tmp_path, monkeypatch)
    storage_data.save_dataset({"Alpha": _movie("Alpha")})

    backup_path = create_backup()

    assert isinstance(backup_path, Path)
    assert backup_path.suffix == ".sqlite3"
    assert backup_path.is_file()


def test_restore_backup_restores_sqlite_database(tmp_path, monkeypatch) -> None:
    _use_sqlite(tmp_path, monkeypatch)
    storage_data.save_dataset({"Alpha": _movie("Alpha")})
    backup_path = create_backup()
    storage_data.clean_dataset()

    restored_count = restore_backup(backup_path)

    assert restored_count == 1
    assert list(storage_data.load_dataset()) == ["Alpha"]

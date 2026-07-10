from __future__ import annotations

from pathlib import Path

from storage import data as storage_data
from storage.files import create_backup, restore_backup
from storage.sqlite.backup import backup_sqlite_database, restore_sqlite_database


def _use_sqlite(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("config.constant.APP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr("config.constant.BACKUP_DIR", str(tmp_path / "data" / "backups"))


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
        "genre": {},
    }


def test_create_backup_includes_sqlite_runtime_db(tmp_path, monkeypatch) -> None:
    _use_sqlite(tmp_path, monkeypatch)
    storage_data.save_dataset({"Alpha": _movie("Alpha")})

    backup_path = create_backup()

    assert isinstance(backup_path, Path)
    assert backup_path.suffix == ".sqlite3"
    assert backup_path.is_file()


def test_backup_sqlite_database_requires_existing_source(tmp_path) -> None:
    missing_db = tmp_path / "missing.sqlite3"

    try:
        backup_sqlite_database(db_path=missing_db, backup_dir=tmp_path / "backups")
    except FileNotFoundError as exc:
        assert str(missing_db) in str(exc)
    else:
        raise AssertionError("backup_sqlite_database should reject a missing source database")

    assert missing_db.exists() is False


def test_restore_backup_restores_sqlite_database(tmp_path, monkeypatch) -> None:
    _use_sqlite(tmp_path, monkeypatch)
    storage_data.save_dataset({"Alpha": _movie("Alpha")})
    backup_path = create_backup()
    storage_data.clean_dataset()

    restored_count = restore_backup(backup_path)

    assert restored_count == 1
    assert list(storage_data.load_dataset()) == ["Alpha"]


def test_restore_sqlite_database_rejects_invalid_backup_without_touching_target(tmp_path) -> None:
    from storage.sqlite import watched_repository
    import sqlite3

    db_path = tmp_path / "watchbane.sqlite3"
    invalid_backup = tmp_path / "invalid.sqlite3"
    watched_repository.save_dataset_dict({"Alpha": _movie("Alpha")}, path=db_path)
    with sqlite3.connect(invalid_backup) as conn:
        conn.execute("CREATE TABLE unrelated(id INTEGER PRIMARY KEY)")

    try:
        restore_sqlite_database(invalid_backup, db_path=db_path)
    except ValueError as exc:
        assert "watched_records" in str(exc)
    else:
        raise AssertionError("restore_sqlite_database should reject invalid SQLite backups")

    assert list(watched_repository.load_dataset_dict(path=db_path)) == ["Alpha"]


def test_restore_sqlite_database_rejects_incomplete_schema_without_touching_target(tmp_path) -> None:
    from storage.sqlite import watched_repository
    import sqlite3

    db_path = tmp_path / "watchbane.sqlite3"
    incomplete_backup = tmp_path / "incomplete.sqlite3"
    watched_repository.save_dataset_dict({"Alpha": _movie("Alpha")}, path=db_path)
    with sqlite3.connect(incomplete_backup) as conn:
        conn.execute(
            """
            CREATE TABLE watched_records (
              dataset_key TEXT PRIMARY KEY,
              title TEXT NOT NULL,
              title_normalized TEXT NOT NULL,
              media_type TEXT NOT NULL DEFAULT 'tv',
              payload_json TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            )
            """
        )

    try:
        restore_sqlite_database(incomplete_backup, db_path=db_path)
    except ValueError as exc:
        assert "schema_migrations" in str(exc)
        assert "candidate_records" in str(exc)
    else:
        raise AssertionError("restore_sqlite_database should reject incomplete SQLite backups")

    assert list(watched_repository.load_dataset_dict(path=db_path)) == ["Alpha"]

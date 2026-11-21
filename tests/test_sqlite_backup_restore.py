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
    backups_before_restore = set((tmp_path / "data" / "backups").iterdir())

    restored_count = restore_backup(backup_path)

    assert restored_count == 1
    assert list(storage_data.load_dataset()) == ["Alpha"]
    backups_after_restore = set((tmp_path / "data" / "backups").iterdir())
    assert len(backups_after_restore - backups_before_restore) == 1


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


def test_console_backup_menu_hides_corruption_details_and_preserves_target(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    from ui.console import backup_menu

    _use_sqlite(tmp_path, monkeypatch)
    storage_data.save_dataset({"Alpha": _movie("Alpha")})
    corrupt_backup = tmp_path / "private-runtime-path.sqlite3"
    corrupt_backup.write_bytes(b"not a sqlite database")
    answers = iter(["1", "yes"])
    monkeypatch.setattr(
        backup_menu.storage_files,
        "get_latest_backups",
        lambda _limit: [corrupt_backup],
    )
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))

    backup_menu.open_backup_menu()

    output = capsys.readouterr().out
    assert "Backup повреждён или несовместим. Данные не изменены." in output
    assert str(corrupt_backup) not in output
    assert list(storage_data.load_dataset()) == ["Alpha"]


def test_failed_backup_is_never_listed_and_prior_backup_stays_restorable(tmp_path, monkeypatch):
    import sqlite3
    import pytest

    from storage.files import get_latest_backups

    _use_sqlite(tmp_path, monkeypatch)
    storage_data.save_dataset({"Alpha": _movie("Alpha")})
    prior = create_backup()
    storage_data.save_dataset({"Beta": _movie("Beta")})
    connect = sqlite3.connect
    listed_during_copy = []

    class InterruptedCopy(sqlite3.Connection):
        def backup(self, target, *args, **kwargs):
            listed_during_copy[:] = get_latest_backups()
            raise sqlite3.OperationalError("simulated copy failure")

    def fail_copy(database, *args, **kwargs):
        return connect(database, *args, factory=InterruptedCopy, **kwargs)

    with monkeypatch.context() as failed:
        failed.setattr("storage.sqlite.backup.sqlite3.connect", fail_copy)
        with pytest.raises(sqlite3.OperationalError, match="simulated copy failure"):
            create_backup()
    assert listed_during_copy == [prior]
    assert get_latest_backups() == [prior]
    assert set(prior.parent.iterdir()) == {prior}
    assert list(storage_data.load_dataset()) == ["Beta"]
    assert restore_backup(prior) == 1
    assert list(storage_data.load_dataset()) == ["Alpha"]


def test_restore_rejects_live_wal_connection_without_detaching_it(tmp_path, monkeypatch):
    import sqlite3
    import pytest

    _use_sqlite(tmp_path, monkeypatch)
    storage_data.save_dataset({"Old": _movie("Old")})
    prior = create_backup()
    storage_data.save_dataset({"Current": _movie("Current")})
    from storage.sqlite.connection import get_db_path

    from contextlib import closing
    with closing(sqlite3.connect(get_db_path())) as live:
        assert live.execute("PRAGMA journal_mode").fetchone() == ("wal",)
        assert live.execute("SELECT COUNT(*) FROM watched_records").fetchone() == (1,)
        with pytest.raises(sqlite3.OperationalError, match="locked"):
            restore_backup(prior)
        live.execute("UPDATE watched_records SET dataset_key='Committed after refusal'")
        live.commit()
        assert list(storage_data.load_dataset()) == ["Committed after refusal"]

    assert restore_backup(prior) == 1
    assert list(storage_data.load_dataset()) == ["Old"]
    from storage.files import get_latest_backups
    safety_backup = get_latest_backups()[0]
    assert safety_backup != prior
    assert restore_backup(safety_backup) == 1
    assert list(storage_data.load_dataset()) == ["Committed after refusal"]


def test_console_reports_busy_restore_without_claiming_backup_is_corrupt(tmp_path, monkeypatch, capsys):
    from contextlib import closing
    import sqlite3
    from storage.sqlite.connection import get_db_path
    from ui.console import backup_menu

    _use_sqlite(tmp_path, monkeypatch)
    storage_data.save_dataset({"Old": _movie("Old")})
    create_backup()
    storage_data.save_dataset({"Current": _movie("Current")})
    answers = iter(["1", "yes"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))
    with closing(sqlite3.connect(get_db_path())) as live:
        live.execute("SELECT COUNT(*) FROM watched_records").fetchone()
        backup_menu.open_backup_menu()
    assert "Профиль занят" in capsys.readouterr().out
    assert list(storage_data.load_dataset()) == ["Current"]

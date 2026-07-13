from __future__ import annotations

from pathlib import Path
import sqlite3

import pytest

from storage.sqlite.backup import backup_sqlite_database, restore_sqlite_database
from storage.sqlite.connection import connect
from storage.sqlite.migrations import MIGRATIONS, Migration, apply_migrations
from storage.sqlite.startup import (
    StartupDatabaseError,
    ensure_sqlite_startup_migration,
    inspect_sqlite_startup,
)


def _patch_backup_dir(monkeypatch, tmp_path: Path) -> Path:
    backup_dir = tmp_path / "backups"
    monkeypatch.setattr("config.constant.BACKUP_DIR", str(backup_dir))
    return backup_dir


def _create_schema(path: Path, count: int = len(MIGRATIONS)) -> None:
    conn = connect(path)
    try:
        apply_migrations(conn, migrations=MIGRATIONS[:count])
    finally:
        conn.close()


def test_non_database_is_preserved_and_never_replaced(monkeypatch, tmp_path) -> None:
    backup_dir = _patch_backup_dir(monkeypatch, tmp_path)
    db_path = tmp_path / "watchbane.sqlite3"
    original = b"not a sqlite database\x00private-data"
    db_path.write_bytes(original)

    with pytest.raises(StartupDatabaseError) as raised:
        ensure_sqlite_startup_migration(db_path=db_path)

    assert db_path.read_bytes() == original
    assert raised.value.preserved_path is not None
    assert raised.value.preserved_path.read_bytes() == original
    assert raised.value.preserved_path.is_relative_to(backup_dir / "diagnostics")


def test_recorded_core_migration_with_missing_table_stops_before_repair(monkeypatch, tmp_path) -> None:
    _patch_backup_dir(monkeypatch, tmp_path)
    db_path = tmp_path / "watchbane.sqlite3"
    _create_schema(db_path)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("DROP TABLE watched_records")
        conn.commit()
    finally:
        conn.close()

    report = inspect_sqlite_startup(db_path)
    assert report["status"] == "partial_schema"
    with pytest.raises(StartupDatabaseError):
        ensure_sqlite_startup_migration(db_path=db_path)

    conn = sqlite3.connect(db_path)
    try:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert "watched_records" not in tables
    finally:
        conn.close()


def test_missing_migration_row_and_partially_applied_idempotent_ddl_are_completed(tmp_path) -> None:
    db_path = tmp_path / "watchbane.sqlite3"
    _create_schema(db_path)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("DELETE FROM schema_migrations WHERE version = 6")
        conn.commit()
    finally:
        conn.close()

    result = ensure_sqlite_startup_migration(db_path=db_path)

    assert result["schema_version"] == 6
    conn = sqlite3.connect(db_path)
    try:
        assert conn.execute("SELECT COUNT(*) FROM schema_migrations WHERE version = 6").fetchone()[0] == 1
        assert conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='recommendation_deck_state'"
        ).fetchone()[0] == 1
    finally:
        conn.close()


def test_gap_in_migration_history_is_completed_in_version_order(tmp_path) -> None:
    db_path = tmp_path / "watchbane.sqlite3"
    _create_schema(db_path)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("DELETE FROM schema_migrations WHERE version = 3")
        conn.commit()
    finally:
        conn.close()

    result = ensure_sqlite_startup_migration(db_path=db_path)

    assert result["schema_version"] == 6
    conn = sqlite3.connect(db_path)
    try:
        versions = [row[0] for row in conn.execute("SELECT version FROM schema_migrations ORDER BY version")]
        assert versions == [1, 2, 3, 4, 5, 6]
    finally:
        conn.close()


@pytest.mark.parametrize("table_name", ["candidate_fts", "recommendation_deck_state"])
def test_missing_derived_table_is_recreated_without_touching_user_tables(tmp_path, table_name) -> None:
    db_path = tmp_path / "watchbane.sqlite3"
    _create_schema(db_path)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            INSERT INTO app_settings(key, value_json, updated_at)
            VALUES ('sentinel', '123', '2026-01-01T00:00:00+00:00')
            """
        )
        conn.execute(f"DROP TABLE {table_name}")
        conn.commit()
    finally:
        conn.close()

    result = ensure_sqlite_startup_migration(db_path=db_path)

    assert table_name in result["repaired_tables"]
    conn = sqlite3.connect(db_path)
    try:
        assert conn.execute("SELECT value_json FROM app_settings WHERE key='sentinel'").fetchone()[0] == "123"
        assert conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE name=?", (table_name,)
        ).fetchone()[0] == 1
    finally:
        conn.close()


def test_newer_schema_is_rejected_without_deleting_history(monkeypatch, tmp_path) -> None:
    _patch_backup_dir(monkeypatch, tmp_path)
    db_path = tmp_path / "watchbane.sqlite3"
    _create_schema(db_path)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT INTO schema_migrations(version, name, applied_at) VALUES (999, 'future', 'now')"
        )
        conn.commit()
    finally:
        conn.close()

    with pytest.raises(StartupDatabaseError, match="newer"):
        ensure_sqlite_startup_migration(db_path=db_path)

    conn = sqlite3.connect(db_path)
    try:
        assert conn.execute("SELECT name FROM schema_migrations WHERE version=999").fetchone()[0] == "future"
    finally:
        conn.close()


def test_old_release_schema_migrates_to_current(tmp_path) -> None:
    db_path = tmp_path / "watchbane.sqlite3"
    _create_schema(db_path, count=4)

    result = ensure_sqlite_startup_migration(db_path=db_path)

    assert result["schema_version"] == len(MIGRATIONS)


def test_failed_migration_rolls_back_ddl_and_history(tmp_path) -> None:
    db_path = tmp_path / "watchbane.sqlite3"

    def fail_after_ddl(conn: sqlite3.Connection) -> None:
        conn.execute("CREATE TABLE must_rollback (id INTEGER PRIMARY KEY)")
        raise RuntimeError("injected migration failure")

    conn = connect(db_path)
    try:
        with pytest.raises(RuntimeError, match="injected"):
            apply_migrations(conn, migrations=(Migration(1, "fails", fail_after_ddl),))
        assert conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE name='must_rollback'"
        ).fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0] == 0
    finally:
        conn.close()


def test_existing_backup_is_not_restored_automatically(monkeypatch, tmp_path) -> None:
    backup_dir = _patch_backup_dir(monkeypatch, tmp_path)
    healthy_path = tmp_path / "healthy.sqlite3"
    _create_schema(healthy_path)
    backup_path = backup_sqlite_database(db_path=healthy_path, backup_dir=backup_dir)
    backup_bytes = backup_path.read_bytes()

    runtime_path = tmp_path / "watchbane.sqlite3"
    corrupt_bytes = b"broken runtime; do not replace"
    runtime_path.write_bytes(corrupt_bytes)

    with pytest.raises(StartupDatabaseError):
        ensure_sqlite_startup_migration(db_path=runtime_path)

    assert runtime_path.read_bytes() == corrupt_bytes
    assert backup_path.read_bytes() == backup_bytes


def test_explicit_restore_atomically_replaces_corrupt_runtime_and_preserves_it(monkeypatch, tmp_path) -> None:
    backup_dir = _patch_backup_dir(monkeypatch, tmp_path)
    healthy_path = tmp_path / "healthy.sqlite3"
    _create_schema(healthy_path)
    conn = sqlite3.connect(healthy_path)
    try:
        conn.execute(
            """
            INSERT INTO watched_records(
                dataset_key, title, title_normalized, media_type, payload_json, created_at, updated_at
            ) VALUES ('movie|1', 'Kept', 'kept', 'movie', '{}', 'now', 'now')
            """
        )
        conn.commit()
    finally:
        conn.close()
    backup_path = backup_sqlite_database(db_path=healthy_path, backup_dir=backup_dir)

    runtime_path = tmp_path / "watchbane.sqlite3"
    corrupt_bytes = b"broken runtime selected for explicit restore"
    runtime_path.write_bytes(corrupt_bytes)

    assert restore_sqlite_database(backup_path, db_path=runtime_path) == 1
    preserved = list((backup_dir / "diagnostics").rglob("watchbane.sqlite3"))
    assert any(path.read_bytes() == corrupt_bytes for path in preserved)
    assert inspect_sqlite_startup(runtime_path)["ok"] is True
    assert runtime_path.with_suffix(".sqlite3.restoring").exists() is False


def test_corrupt_backup_is_rejected_before_target_is_touched(tmp_path) -> None:
    runtime_path = tmp_path / "watchbane.sqlite3"
    _create_schema(runtime_path)
    before = runtime_path.read_bytes()
    corrupt_backup = tmp_path / "corrupt-backup.sqlite3"
    corrupt_backup.write_bytes(b"not a sqlite backup")

    with pytest.raises(sqlite3.DatabaseError):
        restore_sqlite_database(corrupt_backup, db_path=runtime_path)

    assert runtime_path.read_bytes() == before
    assert runtime_path.with_suffix(".sqlite3.restoring").exists() is False

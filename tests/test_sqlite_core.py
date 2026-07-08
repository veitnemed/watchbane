from __future__ import annotations

import sqlite3

from storage.sqlite.connection import DEFAULT_BUSY_TIMEOUT_MS, connect, get_db_path
from storage.sqlite.migrations import Migration, apply_migrations, get_current_schema_version


def test_get_db_path_uses_runtime_data_dir(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("config.constant.APP_DATA_DIR", str(tmp_path))

    db_path = get_db_path()

    assert db_path == tmp_path / "watchbane.sqlite3"


def test_connect_creates_db_and_enables_pragmas(tmp_path) -> None:
    db_path = tmp_path / "runtime" / "watchbane.sqlite3"

    conn = connect(db_path)
    try:
        assert db_path.is_file()
        assert conn.row_factory is sqlite3.Row
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == DEFAULT_BUSY_TIMEOUT_MS
        assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    finally:
        conn.close()


def test_apply_migrations_is_idempotent(tmp_path) -> None:
    db_path = tmp_path / "watchbane.sqlite3"
    calls: list[int] = []

    def migration(conn: sqlite3.Connection) -> None:
        calls.append(1)
        conn.execute("CREATE TABLE example (id INTEGER PRIMARY KEY)")

    conn = connect(db_path)
    try:
        migrations = (Migration(1, "example", migration),)

        assert apply_migrations(conn, migrations=migrations) == 1
        assert apply_migrations(conn, migrations=migrations) == 1

        assert calls == [1]
        assert get_current_schema_version(conn) == 1
    finally:
        conn.close()

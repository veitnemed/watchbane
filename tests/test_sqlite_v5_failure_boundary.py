"""Real v4 databases at the two v5 startup failure boundaries."""
from contextlib import closing
from dataclasses import replace
import json
import sqlite3

import pytest

from storage.sqlite import backup, migrations
from storage.sqlite.connection import connect
from storage.sqlite.startup import ensure_sqlite_startup_migration


@pytest.mark.parametrize("boundary", ["backup", "after_v5_writes"])
def test_v5_failure_keeps_v4_reopenable_and_retryable(tmp_path, monkeypatch, boundary):
    db = tmp_path / "watchbane.sqlite3"
    backups_dir = tmp_path / "backups" / "migrations"
    history = migrations.MIGRATIONS
    with closing(connect(db)) as conn:
        assert migrations.apply_migrations(conn, migrations=history[:4]) == 4
        conn.execute("""
            INSERT INTO watched_records
                (dataset_key, title, title_normalized, media_type, tmdb_id, user_score,
                 payload_json, created_at, updated_at)
            VALUES ('fixture', 'Fixture', 'fixture', 'movie', 801, 7.9, ?, 't1', 't2')
        """, (json.dumps({"main_info": {"user_score": 7.9, "watched_at": "2025-02-01"}}),))
        conn.commit()

    def snapshot(path):
        with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as conn:
            assert conn.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
            schema = conn.execute("SELECT sql FROM sqlite_master WHERE name='watched_records'").fetchone()[0]
            rows = conn.execute("SELECT * FROM watched_records").fetchall()
            ledger = conn.execute("SELECT * FROM schema_migrations ORDER BY version").fetchall()
            return schema, rows, ledger

    before = snapshot(db)

    def fail_backup(**_):
        raise OSError("injected backup error before v5")

    def fail_after_v5(conn):
        stored = list(backups_dir.glob("*.sqlite3"))
        assert len(stored) == 1 and snapshot(stored[0]) == before
        history[4].apply(conn)  # Real score conversion and table replacement.
        assert conn.execute("SELECT user_score FROM watched_records").fetchone()[0] == 2
        assert "user_score INTEGER" in conn.execute(
            "SELECT sql FROM sqlite_master WHERE name='watched_records'"
        ).fetchone()[0]
        raise OSError("injected failure after v5 writes")

    with monkeypatch.context() as patch:
        if boundary == "backup":
            patch.setattr(backup, "backup_sqlite_database", fail_backup)
        else:
            patch.setattr(migrations, "MIGRATIONS", (*history[:4], replace(history[4], apply=fail_after_v5), *history[5:]))
        with pytest.raises(OSError, match="injected"):
            ensure_sqlite_startup_migration(base_dir=tmp_path, db_path=db)

    assert snapshot(db) == before
    assert len(list(backups_dir.glob("*.sqlite3"))) == int(boundary == "after_v5_writes")
    assert ensure_sqlite_startup_migration(base_dir=tmp_path, db_path=db)["schema_version"] == 6
    with closing(sqlite3.connect(db)) as conn:
        assert conn.execute("SELECT user_score FROM watched_records").fetchone() == (2,)
        assert conn.execute("PRAGMA integrity_check").fetchall() == [("ok",)]

from __future__ import annotations

import sqlite3
from pathlib import Path

from tools.migrations import strip_watched_tags_vibe as migration


def _create_watched_table(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE watched_records (
          dataset_key TEXT PRIMARY KEY,
          title TEXT NOT NULL,
          title_normalized TEXT NOT NULL,
          media_type TEXT NOT NULL DEFAULT 'tv',
          year INTEGER,
          user_score REAL,
          country TEXT,
          tmdb_id INTEGER,
          imdb_id TEXT,
          payload_json TEXT NOT NULL,
          meta_json TEXT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        """
    )


def test_migrate_sqlite_watched_strips_tags_vibe_dry_run(tmp_path: Path) -> None:
    db_path = tmp_path / "watchbane.sqlite3"
    conn = sqlite3.connect(db_path)
    try:
        _create_watched_table(conn)
        payload = (
            '{"main_info": {"title": "Show"}, '
            '"tags_vibe": {"vibe_dark": 1}}'
        )
        conn.execute(
            """
            INSERT INTO watched_records(
              dataset_key, title, title_normalized, media_type, payload_json,
              meta_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("Show", "Show", "show", "tv", payload, "{}", "2026-01-01", "2026-01-01"),
        )
        conn.commit()
    finally:
        conn.close()

    stats = migration.migrate_sqlite_watched(db_path, dry_run=True)
    assert stats["sqlite_records_migrated"] == 1

    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT payload_json FROM watched_records WHERE dataset_key = ?",
            ("Show",),
        ).fetchone()
        assert row is not None
        assert '"tags_vibe"' in row[0]
    finally:
        conn.close()


def test_migrate_sqlite_watched_strips_tags_vibe_apply(tmp_path: Path) -> None:
    db_path = tmp_path / "watchbane.sqlite3"
    conn = sqlite3.connect(db_path)
    try:
        _create_watched_table(conn)
        payload = (
            '{"main_info": {"title": "Show"}, '
            '"tags_vibe": {"vibe_dark": 1}}'
        )
        conn.execute(
            """
            INSERT INTO watched_records(
              dataset_key, title, title_normalized, media_type, payload_json,
              meta_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("Show", "Show", "show", "tv", payload, "{}", "2026-01-01", "2026-01-01"),
        )
        conn.commit()
    finally:
        conn.close()

    stats = migration.migrate_sqlite_watched(db_path, dry_run=False)
    assert stats["sqlite_records_migrated"] == 1

    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT payload_json FROM watched_records WHERE dataset_key = ?",
            ("Show",),
        ).fetchone()
        assert row is not None
        assert '"tags_vibe"' not in row[0]
    finally:
        conn.close()

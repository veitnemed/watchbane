"""SQLite startup initialization."""

from __future__ import annotations

from pathlib import Path

from storage.sqlite.connection import connect, get_db_path
from storage.sqlite.migrations import apply_migrations


IMPORT_MARKER_KEY = "legacy_json_import_completed"


def is_sqlite_runtime_empty(db_path: str | Path | None = None) -> bool:
    conn = connect(db_path)
    try:
        apply_migrations(conn)
        checks = (
            "SELECT COUNT(*) AS count FROM watched_records",
            "SELECT COUNT(*) AS count FROM candidate_records",
            "SELECT COUNT(*) AS count FROM candidate_criteria",
            "SELECT COUNT(*) AS count FROM candidate_actions",
            "SELECT COUNT(*) AS count FROM candidate_impressions",
            "SELECT COUNT(*) AS count FROM app_settings",
            "SELECT COUNT(*) AS count FROM poster_cache_entries",
        )
        return all(int(conn.execute(sql).fetchone()["count"]) == 0 for sql in checks)
    finally:
        conn.close()


def ensure_sqlite_startup_migration(
    *,
    base_dir: str | Path = "data",
    db_path: str | Path | None = None,
) -> dict:
    """Create or migrate the SQLite runtime schema."""
    target_db = Path(db_path) if db_path is not None else get_db_path()
    conn = connect(target_db)
    try:
        schema_version = apply_migrations(conn)
    finally:
        conn.close()

    return {
        "ok": True,
        "db_path": str(target_db),
        "schema_version": schema_version,
        "legacy_imported": False,
        "legacy_import_report": None,
    }


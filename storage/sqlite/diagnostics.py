"""Read-only diagnostics for the SQLite runtime database."""

from __future__ import annotations

from pathlib import Path
import sqlite3
from typing import Any

from config import constant
from storage.sqlite.connection import get_db_path
from storage.sqlite.migrations import get_current_schema_version
from storage.sqlite.session import connection


TABLES = (
    "watched_records",
    "candidate_records",
    "candidate_criteria",
    "candidate_actions",
    "app_settings",
    "poster_cache_entries",
)

LEGACY_JSON_PATHS = (
    constant.FILE_NAME,
    constant.META_JSON,
    constant.CANDIDATE_POOL_JSON,
    constant.CRITERIA_POOL_JSON,
    str(Path(constant.APP_DATA_DIR) / "watchlist.json"),
    str(Path(constant.APP_DATA_DIR) / "hidden.json"),
    str(Path(constant.APP_DATA_DIR) / "posters.json"),
)


def _pragma_rows(conn: sqlite3.Connection, pragma_name: str) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(f"PRAGMA {pragma_name}")]


def _table_counts(conn: sqlite3.Connection) -> dict[str, int]:
    counts: dict[str, int] = {}
    for table in TABLES:
        row = conn.execute(f"SELECT COUNT(*) AS count FROM {table}").fetchone()
        counts[table] = int(row["count"] if row is not None else 0)
    return counts


def _duplicate_rows(conn: sqlite3.Connection, sql: str) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(sql)]


def _legacy_json_presence(base_dir: str | Path | None = None) -> list[dict[str, Any]]:
    root = Path(base_dir) if base_dir is not None else Path(".")
    result = []
    for path_text in LEGACY_JSON_PATHS:
        path = root / path_text
        if path.exists():
            result.append(
                {
                    "path": path_text,
                    "exists": True,
                    "canonical": False,
                    "size_bytes": path.stat().st_size,
                }
            )
    return result


def build_sqlite_diagnostics(
    *,
    conn: sqlite3.Connection | None = None,
    path: str | Path | None = None,
    base_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Return read-only SQLite diagnostics without repairing data."""
    active, owned = connection(conn, path)
    try:
        quick_check = _pragma_rows(active, "quick_check")
        foreign_key_check = _pragma_rows(active, "foreign_key_check")
        watched_duplicate_titles = _duplicate_rows(
            active,
            """
            SELECT title_normalized, media_type, year, COUNT(*) AS count
            FROM watched_records
            WHERE payload_json != '{}'
            GROUP BY title_normalized, media_type, year
            HAVING COUNT(*) > 1
            ORDER BY count DESC, title_normalized ASC
            """,
        )
        watched_duplicate_tmdb = _duplicate_rows(
            active,
            """
            SELECT media_type, tmdb_id, COUNT(*) AS count
            FROM watched_records
            WHERE tmdb_id IS NOT NULL AND payload_json != '{}'
            GROUP BY media_type, tmdb_id
            HAVING COUNT(*) > 1
            ORDER BY count DESC, media_type ASC, tmdb_id ASC
            """,
        )
        candidate_duplicate_titles = _duplicate_rows(
            active,
            """
            SELECT title_normalized, media_type, year, COUNT(*) AS count
            FROM candidate_records
            GROUP BY title_normalized, media_type, year
            HAVING COUNT(*) > 1
            ORDER BY count DESC, title_normalized ASC
            """,
        )
        orphaned_actions = _duplicate_rows(
            active,
            """
            SELECT action, identity_key
            FROM candidate_actions
            WHERE identity_key NOT IN (SELECT pool_key FROM candidate_records)
            ORDER BY action ASC, identity_key ASC
            """,
        )

        return {
            "db_path": str(get_db_path(path)),
            "schema_version": get_current_schema_version(active),
            "quick_check": quick_check,
            "quick_check_ok": quick_check == [{"quick_check": "ok"}],
            "foreign_key_check": foreign_key_check,
            "foreign_key_check_ok": foreign_key_check == [],
            "table_counts": _table_counts(active),
            "duplicates": {
                "watched_title_identity": watched_duplicate_titles,
                "watched_tmdb_identity": watched_duplicate_tmdb,
                "candidate_title_identity": candidate_duplicate_titles,
            },
            "orphaned_candidate_actions": orphaned_actions,
            "legacy_json_files": _legacy_json_presence(base_dir),
        }
    finally:
        if owned:
            active.close()

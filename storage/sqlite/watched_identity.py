"""Identity lookup helpers for SQLite watched records."""

from __future__ import annotations

from pathlib import Path
import sqlite3

from dataset.models.identity import find_case_insensitive_key, normalize_title_key
from dataset.models.media_type import normalize_media_type
from storage.sqlite.session import connection
from storage.sqlite.watched_read import load_dataset_dict
from storage.sqlite.watched_write import EMPTY_PAYLOAD_JSON


def find_exact_title(
    title: str,
    *,
    conn: sqlite3.Connection | None = None,
    path: str | Path | None = None,
) -> str | None:
    data = load_dataset_dict(conn=conn, path=path)
    return find_case_insensitive_key(data, title)


def is_origin_title(
    title: str,
    *,
    conn: sqlite3.Connection | None = None,
    path: str | Path | None = None,
) -> bool:
    return find_exact_title(title, conn=conn, path=path) is None


def find_watched_identity(
    title: str,
    *,
    year: int | None = None,
    media_type: str | None = None,
    tmdb_id: int | None = None,
    conn: sqlite3.Connection | None = None,
    path: str | Path | None = None,
) -> str | None:
    """Find a watched dataset key using indexed identity columns."""
    active, owned = connection(conn, path)
    clauses = ["title_normalized = ?"]
    params: list[object] = [normalize_title_key(title)]
    if year is not None:
        clauses.append("year = ?")
        params.append(year)
    if media_type is not None:
        clauses.append("media_type = ?")
        params.append(normalize_media_type(media_type))
    if tmdb_id is not None:
        clauses.append("tmdb_id = ?")
        params.append(tmdb_id)
    try:
        row = active.execute(
            f"""
            SELECT dataset_key
            FROM watched_records
            WHERE {' AND '.join(clauses)}
              AND payload_json != ?
            ORDER BY dataset_key
            LIMIT 1
            """,
            (*params, EMPTY_PAYLOAD_JSON),
        ).fetchone()
        return None if row is None else row["dataset_key"]
    finally:
        if owned:
            active.close()

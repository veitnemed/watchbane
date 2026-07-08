"""Read helpers for SQLite watched dataset payloads."""

from __future__ import annotations

from pathlib import Path
import sqlite3

from storage.normalize import normalize_movie_tags
from storage.sqlite.json_codec import loads_json
from storage.sqlite.session import connection


def load_dataset_dict(
    *,
    conn: sqlite3.Connection | None = None,
    path: str | Path | None = None,
) -> dict:
    """Load watched records in the legacy dataset dict shape."""
    active, owned = connection(conn, path)
    try:
        result = {}
        for row in active.execute(
            "SELECT dataset_key, payload_json FROM watched_records ORDER BY rowid"
        ):
            payload = loads_json(row["payload_json"], {})
            if isinstance(payload, dict) and payload:
                result[row["dataset_key"]] = normalize_movie_tags(payload)
        return result
    finally:
        if owned:
            active.close()

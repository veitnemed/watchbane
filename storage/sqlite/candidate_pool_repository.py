"""SQLite repository for candidate pool payloads."""

from __future__ import annotations

from pathlib import Path
import sqlite3

from candidates.pool.normalization import normalize_storage_pool
from candidates.pool.watched_cleanup import purge_watched_from_pool
from storage.sqlite.candidate_write import insert_candidate_record
from storage.sqlite.json_codec import loads_json
from storage.sqlite.session import connection, transaction, utc_now


def load_candidate_pool_dict(
    *,
    conn: sqlite3.Connection | None = None,
    path: str | Path | None = None,
) -> dict:
    """Load the candidate pool in legacy dict shape."""
    active, owned = connection(conn, path)
    try:
        result = {}
        for row in active.execute(
            "SELECT pool_key, payload_json FROM candidate_records ORDER BY rowid"
        ):
            payload = loads_json(row["payload_json"], {})
            if isinstance(payload, dict):
                result[row["pool_key"]] = payload
        return result
    finally:
        if owned:
            active.close()


def save_candidate_pool_dict(
    data: dict,
    *,
    conn: sqlite3.Connection | None = None,
    path: str | Path | None = None,
    purge_watched: bool = True,
) -> None:
    """Persist candidate pool with the same normalization as JSON write-path."""
    active, owned = connection(conn, path)
    normalized = normalize_storage_pool(data)
    if purge_watched:
        normalized = purge_watched_from_pool(normalized)
    try:
        with transaction(active, owned):
            active.execute("DELETE FROM candidate_records")
            timestamp = utc_now()
            for pool_key, candidate in normalized.items():
                insert_candidate_record(
                    active,
                    pool_key=pool_key,
                    candidate=candidate,
                    timestamp=timestamp,
                )
    finally:
        if owned:
            active.close()


def clear_candidate_pool(
    *,
    conn: sqlite3.Connection | None = None,
    path: str | Path | None = None,
) -> None:
    active, owned = connection(conn, path)
    try:
        with transaction(active, owned):
            active.execute("DELETE FROM candidate_records")
    finally:
        if owned:
            active.close()

"""Meta helpers for SQLite watched records."""

from __future__ import annotations

from pathlib import Path
import sqlite3

from dataset.models.identity import find_case_insensitive_key
from storage.sqlite.json_codec import loads_json
from storage.sqlite.session import connection, transaction, utc_now
from storage.sqlite.watched_write import upsert_watched_row


def _upsert_meta_only_row(conn: sqlite3.Connection, dataset_key: str, meta: dict) -> None:
    existing = conn.execute(
        "SELECT payload_json, created_at FROM watched_records WHERE dataset_key = ?",
        (dataset_key,),
    ).fetchone()
    payload = loads_json(existing["payload_json"], {}) if existing is not None else {}
    created_at = existing["created_at"] if existing is not None else None
    upsert_watched_row(
        conn,
        dataset_key=dataset_key,
        payload=payload if isinstance(payload, dict) else {},
        meta=meta,
        created_at=created_at,
    )


def load_meta_dict(
    *,
    conn: sqlite3.Connection | None = None,
    path: str | Path | None = None,
) -> dict:
    """Load watched meta in the legacy meta dict shape."""
    active, owned = connection(conn, path)
    try:
        result = {}
        for row in active.execute(
            """
            SELECT dataset_key, meta_json
            FROM watched_records
            WHERE meta_json IS NOT NULL
            ORDER BY rowid
            """
        ):
            meta_obj = loads_json(row["meta_json"], {})
            if isinstance(meta_obj, dict):
                result[row["dataset_key"]] = meta_obj
        return result
    finally:
        if owned:
            active.close()


def save_meta_dict(
    meta: dict,
    *,
    conn: sqlite3.Connection | None = None,
    path: str | Path | None = None,
) -> None:
    """Persist watched meta without discarding independently stored dataset."""
    active, owned = connection(conn, path)
    normalized = {
        str(title): meta_obj
        for title, meta_obj in (meta if isinstance(meta, dict) else {}).items()
        if isinstance(meta_obj, dict)
    }
    try:
        with transaction(active, owned):
            for dataset_key, meta_obj in normalized.items():
                _upsert_meta_only_row(active, dataset_key, meta_obj)

            keep_keys = set(normalized)
            for row in active.execute(
                "SELECT dataset_key, payload_json FROM watched_records"
            ).fetchall():
                if row["dataset_key"] in keep_keys:
                    continue
                payload = loads_json(row["payload_json"], {})
                if isinstance(payload, dict) and payload:
                    active.execute(
                        """
                        UPDATE watched_records
                        SET meta_json = NULL, updated_at = ?
                        WHERE dataset_key = ?
                        """,
                        (utc_now(), row["dataset_key"]),
                    )
                else:
                    active.execute(
                        "DELETE FROM watched_records WHERE dataset_key = ?",
                        (row["dataset_key"],),
                    )
    finally:
        if owned:
            active.close()


def get_meta_obj(
    title: str,
    *,
    conn: sqlite3.Connection | None = None,
    path: str | Path | None = None,
) -> dict | None:
    meta = load_meta_dict(conn=conn, path=path)
    key = find_case_insensitive_key(meta, title)
    return meta.get(key) if key is not None else None

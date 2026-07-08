"""SQLite repository for watched dataset and meta records."""

from __future__ import annotations

from datetime import datetime, timezone
from contextlib import nullcontext
from pathlib import Path
import sqlite3
from typing import Any

from dataset.models.identity import find_case_insensitive_key
from storage.normalize import normalize_movie_tags
from storage.sqlite.connection import connect
from storage.sqlite.migrations import apply_migrations
from storage.sqlite.records import dumps_json, extract_watched_record, loads_json


EMPTY_PAYLOAD_JSON = dumps_json({})


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _connection(conn: sqlite3.Connection | None, path: str | Path | None):
    if conn is not None:
        apply_migrations(conn)
        return conn, False
    active = connect(path)
    apply_migrations(active)
    return active, True


def _transaction(active: sqlite3.Connection, owned: bool):
    return active if owned else nullcontext(active)


def _upsert_watched_row(
    conn: sqlite3.Connection,
    *,
    dataset_key: str,
    payload: dict,
    meta: dict | None,
    created_at: str | None = None,
    updated_at: str | None = None,
) -> None:
    row = extract_watched_record(dataset_key, payload, meta=meta)
    timestamp = updated_at or _now()
    conn.execute(
        """
        INSERT INTO watched_records(
          dataset_key, title, title_normalized, media_type, year, user_score,
          country, tmdb_id, imdb_id, payload_json, meta_json, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(dataset_key) DO UPDATE SET
          title = excluded.title,
          title_normalized = excluded.title_normalized,
          media_type = excluded.media_type,
          year = excluded.year,
          user_score = excluded.user_score,
          country = excluded.country,
          tmdb_id = excluded.tmdb_id,
          imdb_id = excluded.imdb_id,
          payload_json = excluded.payload_json,
          meta_json = excluded.meta_json,
          updated_at = excluded.updated_at
        """,
        (
            row.dataset_key,
            row.title,
            row.title_normalized,
            row.media_type,
            row.year,
            row.user_score,
            row.country,
            row.tmdb_id,
            row.imdb_id,
            row.payload_json,
            row.meta_json,
            created_at or timestamp,
            timestamp,
        ),
    )


def _upsert_meta_only_row(conn: sqlite3.Connection, dataset_key: str, meta: dict) -> None:
    existing = conn.execute(
        "SELECT payload_json, created_at FROM watched_records WHERE dataset_key = ?",
        (dataset_key,),
    ).fetchone()
    payload = loads_json(existing["payload_json"], {}) if existing is not None else {}
    created_at = existing["created_at"] if existing is not None else None
    _upsert_watched_row(
        conn,
        dataset_key=dataset_key,
        payload=payload if isinstance(payload, dict) else {},
        meta=meta,
        created_at=created_at,
    )


def load_dataset_dict(
    *,
    conn: sqlite3.Connection | None = None,
    path: str | Path | None = None,
) -> dict:
    """Load watched records in the legacy dataset dict shape."""
    active, owned = _connection(conn, path)
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


def save_dataset_dict(
    data: dict,
    *,
    conn: sqlite3.Connection | None = None,
    path: str | Path | None = None,
) -> None:
    """Persist watched records without discarding independently stored meta."""
    active, owned = _connection(conn, path)
    normalized = {
        str(title): normalize_movie_tags(movie)
        for title, movie in (data if isinstance(data, dict) else {}).items()
        if isinstance(movie, dict)
    }
    try:
        with _transaction(active, owned):
            existing_meta = {
                row["dataset_key"]: loads_json(row["meta_json"], None)
                for row in active.execute(
                    "SELECT dataset_key, meta_json FROM watched_records"
                )
            }
            for dataset_key, movie in normalized.items():
                meta_obj = existing_meta.get(dataset_key)
                _upsert_watched_row(
                    active,
                    dataset_key=dataset_key,
                    payload=movie,
                    meta=meta_obj if isinstance(meta_obj, dict) else None,
                )

            keep_keys = set(normalized)
            for row in active.execute(
                "SELECT dataset_key, meta_json FROM watched_records"
            ).fetchall():
                if row["dataset_key"] in keep_keys:
                    continue
                if row["meta_json"] is None:
                    active.execute(
                        "DELETE FROM watched_records WHERE dataset_key = ?",
                        (row["dataset_key"],),
                    )
                else:
                    active.execute(
                        """
                        UPDATE watched_records
                        SET payload_json = ?, updated_at = ?
                        WHERE dataset_key = ?
                        """,
                        (EMPTY_PAYLOAD_JSON, _now(), row["dataset_key"]),
                    )
    finally:
        if owned:
            active.close()


def load_meta_dict(
    *,
    conn: sqlite3.Connection | None = None,
    path: str | Path | None = None,
) -> dict:
    """Load watched meta in the legacy meta dict shape."""
    active, owned = _connection(conn, path)
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
    active, owned = _connection(conn, path)
    normalized = {
        str(title): meta_obj
        for title, meta_obj in (meta if isinstance(meta, dict) else {}).items()
        if isinstance(meta_obj, dict)
    }
    try:
        with _transaction(active, owned):
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
                        (_now(), row["dataset_key"]),
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


def delete_watched(
    dataset_key: str,
    *,
    conn: sqlite3.Connection | None = None,
    path: str | Path | None = None,
) -> None:
    """Delete a watched payload while preserving meta compatibility."""
    active, owned = _connection(conn, path)
    try:
        with _transaction(active, owned):
            row = active.execute(
                "SELECT meta_json FROM watched_records WHERE dataset_key = ?",
                (dataset_key,),
            ).fetchone()
            if row is None:
                return
            if row["meta_json"] is None:
                active.execute(
                    "DELETE FROM watched_records WHERE dataset_key = ?",
                    (dataset_key,),
                )
            else:
                active.execute(
                    """
                    UPDATE watched_records
                    SET payload_json = ?, updated_at = ?
                    WHERE dataset_key = ?
                    """,
                    (EMPTY_PAYLOAD_JSON, _now(), dataset_key),
                )
    finally:
        if owned:
            active.close()

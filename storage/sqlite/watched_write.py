"""Write helpers for SQLite watched dataset payloads."""

from __future__ import annotations

from pathlib import Path
import sqlite3

from storage.normalize import normalize_movie_tags
from storage.sqlite.json_codec import dumps_json, loads_json
from storage.sqlite.session import connection, transaction, utc_now
from storage.sqlite.watched_mapper import extract_watched_record


EMPTY_PAYLOAD_JSON = dumps_json({})


def upsert_watched_row(
    conn: sqlite3.Connection,
    *,
    dataset_key: str,
    payload: dict,
    meta: dict | None,
    created_at: str | None = None,
    updated_at: str | None = None,
) -> None:
    row = extract_watched_record(dataset_key, payload, meta=meta)
    timestamp = updated_at or utc_now()
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


def save_dataset_dict(
    data: dict,
    *,
    conn: sqlite3.Connection | None = None,
    path: str | Path | None = None,
) -> None:
    """Persist watched records without discarding independently stored meta."""
    active, owned = connection(conn, path)
    normalized = {
        str(title): normalize_movie_tags(movie)
        for title, movie in (data if isinstance(data, dict) else {}).items()
        if isinstance(movie, dict)
    }
    try:
        with transaction(active, owned):
            existing_meta = {
                row["dataset_key"]: loads_json(row["meta_json"], None)
                for row in active.execute(
                    "SELECT dataset_key, meta_json FROM watched_records"
                )
            }
            for dataset_key, movie in normalized.items():
                meta_obj = existing_meta.get(dataset_key)
                upsert_watched_row(
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
                        (EMPTY_PAYLOAD_JSON, utc_now(), row["dataset_key"]),
                    )
    finally:
        if owned:
            active.close()


def delete_watched(
    dataset_key: str,
    *,
    conn: sqlite3.Connection | None = None,
    path: str | Path | None = None,
) -> None:
    """Delete a watched payload while preserving meta compatibility."""
    active, owned = connection(conn, path)
    try:
        with transaction(active, owned):
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
                    (EMPTY_PAYLOAD_JSON, utc_now(), dataset_key),
                )
    finally:
        if owned:
            active.close()

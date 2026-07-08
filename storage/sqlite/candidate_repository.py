"""SQLite repository for candidate pool and criteria."""

from __future__ import annotations

from contextlib import nullcontext
from datetime import datetime, timezone
from pathlib import Path
import sqlite3

from candidates.pool.normalization import normalize_storage_pool
from candidates.pool.watched_cleanup import purge_watched_from_pool
from dataset.models.media_type import normalize_media_type
from storage.sqlite.connection import connect
from storage.sqlite.migrations import apply_migrations
from storage.sqlite.records import dumps_json, extract_candidate_record, loads_json


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


def load_candidate_pool_dict(
    *,
    conn: sqlite3.Connection | None = None,
    path: str | Path | None = None,
) -> dict:
    """Load the candidate pool in legacy dict shape."""
    active, owned = _connection(conn, path)
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
    active, owned = _connection(conn, path)
    normalized = normalize_storage_pool(data)
    if purge_watched:
        normalized = purge_watched_from_pool(normalized)
    try:
        with _transaction(active, owned):
            active.execute("DELETE FROM candidate_records")
            timestamp = _now()
            for pool_key, candidate in normalized.items():
                row = extract_candidate_record(pool_key, candidate)
                active.execute(
                    """
                    INSERT INTO candidate_records(
                      pool_key, title, title_normalized, media_type, year, tmdb_id,
                      criteria_name, tmdb_score, tmdb_votes, tmdb_popularity,
                      quality_score, hidden_gem_score, final_score, payload_json,
                      created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row.pool_key,
                        row.title,
                        row.title_normalized,
                        row.media_type,
                        row.year,
                        row.tmdb_id,
                        row.criteria_name,
                        row.tmdb_score,
                        row.tmdb_votes,
                        row.tmdb_popularity,
                        row.quality_score,
                        row.hidden_gem_score,
                        row.final_score,
                        row.payload_json,
                        timestamp,
                        timestamp,
                    ),
                )
    finally:
        if owned:
            active.close()


def clear_candidate_pool(
    *,
    conn: sqlite3.Connection | None = None,
    path: str | Path | None = None,
) -> None:
    active, owned = _connection(conn, path)
    try:
        with _transaction(active, owned):
            active.execute("DELETE FROM candidate_records")
    finally:
        if owned:
            active.close()


def load_candidate_criteria_dict(
    *,
    conn: sqlite3.Connection | None = None,
    path: str | Path | None = None,
) -> dict:
    """Load candidate criteria in legacy dict shape."""
    active, owned = _connection(conn, path)
    try:
        result = {}
        for row in active.execute(
            "SELECT criteria_name, criteria_json FROM candidate_criteria ORDER BY rowid"
        ):
            criteria = loads_json(row["criteria_json"], {})
            if isinstance(criteria, dict):
                result[row["criteria_name"]] = criteria
        return result
    finally:
        if owned:
            active.close()


def save_candidate_criteria_dict(
    data: dict,
    *,
    conn: sqlite3.Connection | None = None,
    path: str | Path | None = None,
) -> None:
    """Persist candidate criteria in legacy dict shape."""
    active, owned = _connection(conn, path)
    criteria_data = data if isinstance(data, dict) else {}
    try:
        with _transaction(active, owned):
            active.execute("DELETE FROM candidate_criteria")
            timestamp = _now()
            for criteria_name, criteria in criteria_data.items():
                if isinstance(criteria, dict) is False:
                    continue
                active.execute(
                    """
                    INSERT INTO candidate_criteria(
                      criteria_name, criteria_json, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?)
                    """,
                    (str(criteria_name), dumps_json(criteria), timestamp, timestamp),
                )
    finally:
        if owned:
            active.close()


def query_candidate_records(
    *,
    conn: sqlite3.Connection | None = None,
    path: str | Path | None = None,
    media_type: str | None = None,
    min_year: int | None = None,
    max_year: int | None = None,
    min_tmdb_score: float | None = None,
    min_final_score: float | None = None,
    criteria_name: str | None = None,
    limit: int | None = None,
) -> list[dict]:
    """Query candidates using indexed SQLite columns and return payload dicts."""
    active, owned = _connection(conn, path)
    clauses: list[str] = []
    params: list[object] = []
    if media_type is not None:
        clauses.append("media_type = ?")
        params.append(normalize_media_type(media_type))
    if min_year is not None:
        clauses.append("year >= ?")
        params.append(min_year)
    if max_year is not None:
        clauses.append("year <= ?")
        params.append(max_year)
    if min_tmdb_score is not None:
        clauses.append("tmdb_score >= ?")
        params.append(min_tmdb_score)
    if min_final_score is not None:
        clauses.append("final_score >= ?")
        params.append(min_final_score)
    if criteria_name is not None:
        clauses.append("criteria_name = ?")
        params.append(criteria_name)

    sql = "SELECT payload_json FROM candidate_records"
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY final_score DESC, quality_score DESC, tmdb_score DESC, title_normalized ASC"
    if limit is not None:
        sql += " LIMIT ?"
        params.append(int(limit))

    try:
        return [
            payload
            for row in active.execute(sql, params)
            if isinstance((payload := loads_json(row["payload_json"], {})), dict)
        ]
    finally:
        if owned:
            active.close()


def get_worst_candidate_records(
    *,
    conn: sqlite3.Connection | None = None,
    path: str | Path | None = None,
    limit: int = 50,
) -> list[dict]:
    """Return lowest-scoring candidates for eviction-style flows."""
    active, owned = _connection(conn, path)
    try:
        return [
            payload
            for row in active.execute(
                """
                SELECT payload_json
                FROM candidate_records
                ORDER BY final_score ASC, quality_score ASC, tmdb_score ASC, title_normalized ASC
                LIMIT ?
                """,
                (int(limit),),
            )
            if isinstance((payload := loads_json(row["payload_json"], {})), dict)
        ]
    finally:
        if owned:
            active.close()

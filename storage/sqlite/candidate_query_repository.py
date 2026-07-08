"""Indexed SQLite query helpers for candidate records."""

from __future__ import annotations

from pathlib import Path
import sqlite3

from dataset.models.media_type import normalize_media_type
from storage.sqlite.json_codec import loads_json
from storage.sqlite.session import connection


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
    active, owned = connection(conn, path)
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
    active, owned = connection(conn, path)
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

"""Shared write helpers for SQLite candidate records."""

from __future__ import annotations

import sqlite3

from storage.sqlite.candidate_mapper import extract_candidate_record


def insert_candidate_record(
    conn: sqlite3.Connection,
    *,
    pool_key: str,
    candidate: dict,
    timestamp: str,
) -> None:
    row = extract_candidate_record(pool_key, candidate)
    conn.execute(
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

"""SQLite repository for candidate search criteria."""

from __future__ import annotations

from pathlib import Path
import sqlite3

from storage.sqlite.json_codec import dumps_json, loads_json
from storage.sqlite.session import connection, transaction, utc_now


def load_candidate_criteria_dict(
    *,
    conn: sqlite3.Connection | None = None,
    path: str | Path | None = None,
) -> dict:
    """Load candidate criteria in legacy dict shape."""
    active, owned = connection(conn, path)
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
    active, owned = connection(conn, path)
    criteria_data = data if isinstance(data, dict) else {}
    try:
        with transaction(active, owned):
            active.execute("DELETE FROM candidate_criteria")
            timestamp = utc_now()
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

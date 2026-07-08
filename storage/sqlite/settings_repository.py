"""SQLite repository for app settings."""

from __future__ import annotations

from pathlib import Path
import sqlite3
from typing import Any

from storage.sqlite.json_codec import dumps_json, loads_json
from storage.sqlite.session import connection, transaction, utc_now


def _now() -> str:
    return utc_now()


def load_settings_dict(
    *,
    conn: sqlite3.Connection | None = None,
    path: str | Path | None = None,
) -> dict:
    active, owned = connection(conn, path)
    try:
        result = {}
        for row in active.execute("SELECT key, value_json FROM app_settings ORDER BY key"):
            result[row["key"]] = loads_json(row["value_json"])
        return result
    finally:
        if owned:
            active.close()


def save_settings_dict(
    data: dict,
    *,
    conn: sqlite3.Connection | None = None,
    path: str | Path | None = None,
) -> None:
    active, owned = connection(conn, path)
    settings = data if isinstance(data, dict) else {}
    try:
        with transaction(active, owned):
            active.execute("DELETE FROM app_settings")
            timestamp = _now()
            for key, value in settings.items():
                active.execute(
                    """
                    INSERT INTO app_settings(key, value_json, updated_at)
                    VALUES (?, ?, ?)
                    """,
                    (str(key), dumps_json(value), timestamp),
                )
    finally:
        if owned:
            active.close()


def set_setting(
    key: str,
    value: Any,
    *,
    conn: sqlite3.Connection | None = None,
    path: str | Path | None = None,
) -> None:
    active, owned = connection(conn, path)
    try:
        with transaction(active, owned):
            active.execute(
                """
                INSERT INTO app_settings(key, value_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                  value_json = excluded.value_json,
                  updated_at = excluded.updated_at
                """,
                (key, dumps_json(value), _now()),
            )
    finally:
        if owned:
            active.close()


def get_setting(
    key: str,
    default: Any = None,
    *,
    conn: sqlite3.Connection | None = None,
    path: str | Path | None = None,
) -> Any:
    active, owned = connection(conn, path)
    try:
        row = active.execute(
            "SELECT value_json FROM app_settings WHERE key = ?",
            (key,),
        ).fetchone()
        return default if row is None else loads_json(row["value_json"], default)
    finally:
        if owned:
            active.close()

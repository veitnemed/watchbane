"""SQLite repository for app settings."""

from __future__ import annotations

from contextlib import nullcontext
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from typing import Any

from storage.sqlite.connection import connect
from storage.sqlite.migrations import apply_migrations
from storage.sqlite.json_codec import dumps_json, loads_json


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


def load_settings_dict(
    *,
    conn: sqlite3.Connection | None = None,
    path: str | Path | None = None,
) -> dict:
    active, owned = _connection(conn, path)
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
    active, owned = _connection(conn, path)
    settings = data if isinstance(data, dict) else {}
    try:
        with _transaction(active, owned):
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
    active, owned = _connection(conn, path)
    try:
        with _transaction(active, owned):
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
    active, owned = _connection(conn, path)
    try:
        row = active.execute(
            "SELECT value_json FROM app_settings WHERE key = ?",
            (key,),
        ).fetchone()
        return default if row is None else loads_json(row["value_json"], default)
    finally:
        if owned:
            active.close()

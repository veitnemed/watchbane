"""SQLite repository for poster-cache metadata."""

from __future__ import annotations

from contextlib import nullcontext
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from typing import Any

from posters.cache import poster_identity_key
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


def _clean_year(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _entry_tuple(identity: str, entry: dict, timestamp: str):
    title = str(entry.get("title") or identity).strip()
    return (
        identity,
        title,
        _clean_year(entry.get("year")),
        entry.get("poster_path"),
        entry.get("poster_url"),
        entry.get("local_path"),
        entry.get("status"),
        entry.get("source"),
        dumps_json(entry),
        str(entry.get("updated_at") or timestamp),
    )


def load_poster_cache_dict(
    *,
    conn: sqlite3.Connection | None = None,
    path: str | Path | None = None,
) -> dict:
    active, owned = _connection(conn, path)
    try:
        result = {}
        for row in active.execute(
            "SELECT identity_key, payload_json FROM poster_cache_entries ORDER BY rowid"
        ):
            entry = loads_json(row["payload_json"], {})
            if isinstance(entry, dict):
                result[row["identity_key"]] = entry
        return result
    finally:
        if owned:
            active.close()


def save_poster_cache_dict(
    data: dict,
    *,
    conn: sqlite3.Connection | None = None,
    path: str | Path | None = None,
) -> None:
    active, owned = _connection(conn, path)
    cache = data if isinstance(data, dict) else {}
    try:
        with _transaction(active, owned):
            active.execute("DELETE FROM poster_cache_entries")
            timestamp = _now()
            for identity, entry in cache.items():
                if isinstance(entry, dict) is False:
                    continue
                active.execute(
                    """
                    INSERT INTO poster_cache_entries(
                      identity_key, title, year, poster_path, poster_url,
                      local_path, status, source, payload_json, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    _entry_tuple(str(identity), entry, timestamp),
                )
    finally:
        if owned:
            active.close()


def lookup_poster_cache_entry(
    title: str,
    year: Any,
    *,
    conn: sqlite3.Connection | None = None,
    path: str | Path | None = None,
) -> dict | None:
    cache = load_poster_cache_dict(conn=conn, path=path)
    entry = cache.get(poster_identity_key(title, year))
    return entry if isinstance(entry, dict) else None


def upsert_poster_cache_entry(
    title: str,
    year: Any,
    poster_info: dict,
    *,
    conn: sqlite3.Connection | None = None,
    path: str | Path | None = None,
) -> dict:
    active, owned = _connection(conn, path)
    identity = poster_identity_key(title, year)
    timestamp = _now()
    entry = {
        "title": title,
        "year": year,
        "source": poster_info.get("source"),
        "poster_path": poster_info.get("poster_path"),
        "poster_url": poster_info.get("poster_url"),
        "local_path": poster_info.get("local_path"),
        "status": poster_info.get("status", "missing"),
        "updated_at": timestamp,
    }
    try:
        with _transaction(active, owned):
            active.execute(
                """
                INSERT INTO poster_cache_entries(
                  identity_key, title, year, poster_path, poster_url,
                  local_path, status, source, payload_json, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(identity_key) DO UPDATE SET
                  title = excluded.title,
                  year = excluded.year,
                  poster_path = excluded.poster_path,
                  poster_url = excluded.poster_url,
                  local_path = excluded.local_path,
                  status = excluded.status,
                  source = excluded.source,
                  payload_json = excluded.payload_json,
                  updated_at = excluded.updated_at
                """,
                _entry_tuple(identity, entry, timestamp),
            )
        return entry
    finally:
        if owned:
            active.close()

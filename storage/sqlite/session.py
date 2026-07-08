"""Shared SQLite session and transaction helpers."""

from __future__ import annotations

from contextlib import nullcontext
from datetime import datetime, timezone
from pathlib import Path
import sqlite3

from storage.sqlite.connection import connect
from storage.sqlite.migrations import apply_migrations


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connection(conn: sqlite3.Connection | None, path: str | Path | None):
    if conn is not None:
        apply_migrations(conn)
        return conn, False
    active = connect(path)
    apply_migrations(active)
    return active, True


def transaction(active: sqlite3.Connection, owned: bool):
    return active if owned else nullcontext(active)

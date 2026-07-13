"""SQLite connection helpers."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import sqlite3
import time
from typing import Iterator

from config import constant


DB_FILENAME = "watchbane.sqlite3"
DEFAULT_BUSY_TIMEOUT_MS = 5000


def get_db_path(path: str | Path | None = None) -> Path:
    """Return the active SQLite database path."""
    if path is not None:
        return Path(path)
    return Path(constant.APP_DATA_DIR) / DB_FILENAME


def connect(path: str | Path | None = None) -> sqlite3.Connection:
    """Open an app SQLite connection with required pragmas."""
    db_path = get_db_path(path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path, timeout=DEFAULT_BUSY_TIMEOUT_MS / 1000)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute(f"PRAGMA busy_timeout={DEFAULT_BUSY_TIMEOUT_MS}")
    deadline = time.monotonic() + DEFAULT_BUSY_TIMEOUT_MS / 1000
    while True:
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            break
        except sqlite3.OperationalError as error:
            if "locked" not in str(error).casefold() or time.monotonic() >= deadline:
                conn.close()
                raise
            time.sleep(0.05)
    return conn


@contextmanager
def transaction(
    conn: sqlite3.Connection | None = None,
    *,
    path: str | Path | None = None,
) -> Iterator[sqlite3.Connection]:
    """Run a transaction and close owned connections."""
    owned = conn is None
    active_conn = connect(path) if conn is None else conn
    try:
        with active_conn:
            yield active_conn
    finally:
        if owned:
            active_conn.close()

"""SQLite repository for the current recommendation deck snapshot."""

from __future__ import annotations

from pathlib import Path
import sqlite3

from storage.sqlite.json_codec import dumps_json, loads_json
from storage.sqlite.session import connection, transaction, utc_now


def load_current_deck(
    *,
    conn: sqlite3.Connection | None = None,
    path: str | Path | None = None,
) -> dict | None:
    active, owned = connection(conn, path)
    try:
        row = active.execute(
            "SELECT state_json FROM recommendation_deck_state WHERE singleton_id = 1"
        ).fetchone()
        if row is None:
            return None
        payload = loads_json(row["state_json"])
        return payload if isinstance(payload, dict) else None
    finally:
        if owned:
            active.close()


def save_current_deck(
    deck: dict,
    *,
    conn: sqlite3.Connection | None = None,
    path: str | Path | None = None,
) -> None:
    if not isinstance(deck, dict) or not str(deck.get("deck_id") or "").strip():
        raise ValueError("recommendation deck snapshot requires deck_id")
    active, owned = connection(conn, path)
    try:
        with transaction(active, owned):
            active.execute(
                """
                INSERT INTO recommendation_deck_state(
                  singleton_id, deck_id, state_json, updated_at
                )
                VALUES (1, ?, ?, ?)
                ON CONFLICT(singleton_id) DO UPDATE SET
                  deck_id = excluded.deck_id,
                  state_json = excluded.state_json,
                  updated_at = excluded.updated_at
                """,
                (str(deck["deck_id"]), dumps_json(deck), utc_now()),
            )
    finally:
        if owned:
            active.close()


def clear_current_deck(
    *,
    conn: sqlite3.Connection | None = None,
    path: str | Path | None = None,
) -> None:
    active, owned = connection(conn, path)
    try:
        with transaction(active, owned):
            active.execute(
                "DELETE FROM recommendation_deck_state WHERE singleton_id = 1"
            )
    finally:
        if owned:
            active.close()

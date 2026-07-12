"""SQLite repository for recommendation impression history."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
import sqlite3

from candidates.models.keys import title_identity_key
from dataset.models.media_type import normalize_media_type
from storage.sqlite.session import connection, transaction, utc_now


ImpressionIdentity = tuple[str, str]


def _identity(item: dict | tuple[str, str]) -> ImpressionIdentity:
    if isinstance(item, dict):
        return title_identity_key(item), normalize_media_type(item.get("media_type"))
    if isinstance(item, tuple) and len(item) == 2:
        return str(item[0]), normalize_media_type(item[1])
    raise TypeError("impression item must be a candidate dict or (identity_key, media_type)")


def record_impressions(
    items: Iterable[dict | tuple[str, str]],
    *,
    deck_id: str | None = None,
    shown_at: str | None = None,
    conn: sqlite3.Connection | None = None,
    path: str | Path | None = None,
) -> int:
    """Insert or increment a deck's impressions in one transaction."""
    identities = tuple(dict.fromkeys(_identity(item) for item in items))
    if not identities:
        return 0
    timestamp = str(shown_at or utc_now())
    rows = [
        (identity_key, media_type, timestamp, timestamp, deck_id)
        for identity_key, media_type in identities
    ]
    active, owned = connection(conn, path)
    try:
        with transaction(active, owned):
            active.executemany(
                """
                INSERT INTO candidate_impressions(
                  identity_key, media_type, shown_count,
                  first_shown_at, last_shown_at, last_deck_id
                )
                VALUES (?, ?, 1, ?, ?, ?)
                ON CONFLICT(identity_key, media_type) DO UPDATE SET
                  shown_count = candidate_impressions.shown_count + 1,
                  last_shown_at = excluded.last_shown_at,
                  last_deck_id = excluded.last_deck_id
                """,
                rows,
            )
        return len(rows)
    finally:
        if owned:
            active.close()


def get_impression(
    identity_key: str,
    media_type: str,
    *,
    conn: sqlite3.Connection | None = None,
    path: str | Path | None = None,
) -> dict | None:
    active, owned = connection(conn, path)
    try:
        row = active.execute(
            """
            SELECT identity_key, media_type, shown_count,
                   first_shown_at, last_shown_at, last_deck_id
            FROM candidate_impressions
            WHERE identity_key = ? AND media_type = ?
            """,
            (str(identity_key), normalize_media_type(media_type)),
        ).fetchone()
        return dict(row) if row is not None else None
    finally:
        if owned:
            active.close()


def forget_impressions(
    items: Iterable[dict | tuple[str, str]],
    *,
    conn: sqlite3.Connection | None = None,
    path: str | Path | None = None,
) -> int:
    """Remove recent-seen history for explicit user restore actions."""
    identities = tuple(dict.fromkeys(_identity(item) for item in items))
    if not identities:
        return 0
    active, owned = connection(conn, path)
    try:
        with transaction(active, owned):
            removed = 0
            for identity_key, media_type in identities:
                cursor = active.execute(
                    "DELETE FROM candidate_impressions WHERE identity_key = ? AND media_type = ?",
                    (identity_key, media_type),
                )
                removed += max(0, int(cursor.rowcount))
        return removed
    finally:
        if owned:
            active.close()


def get_recently_seen(
    cutoff_at: str,
    *,
    conn: sqlite3.Connection | None = None,
    path: str | Path | None = None,
) -> list[dict]:
    active, owned = connection(conn, path)
    try:
        return [
            dict(row)
            for row in active.execute(
                """
                SELECT identity_key, media_type, shown_count,
                       first_shown_at, last_shown_at, last_deck_id
                FROM candidate_impressions
                WHERE last_shown_at > ?
                ORDER BY last_shown_at DESC, identity_key, media_type
                """,
                (str(cutoff_at),),
            )
        ]
    finally:
        if owned:
            active.close()


def get_shown_counts(
    items: Iterable[dict | tuple[str, str]] | None = None,
    *,
    conn: sqlite3.Connection | None = None,
    path: str | Path | None = None,
) -> dict[ImpressionIdentity, int]:
    requested = None if items is None else set(_identity(item) for item in items)
    active, owned = connection(conn, path)
    try:
        counts = {
            (str(row["identity_key"]), str(row["media_type"])): int(row["shown_count"])
            for row in active.execute(
                "SELECT identity_key, media_type, shown_count FROM candidate_impressions"
            )
        }
        if requested is None:
            return counts
        return {identity: counts.get(identity, 0) for identity in requested}
    finally:
        if owned:
            active.close()

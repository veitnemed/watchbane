"""SQLite repository for candidate pool payloads."""

from __future__ import annotations

from pathlib import Path
import sqlite3

from candidates.pool.normalization import normalize_storage_pool
from candidates.pool.watched_cleanup import purge_watched_from_pool
from candidates.models.keys import candidate_state_identity_key
from candidates.search.fts_index import rebuild_fts_index
from storage.sqlite.candidate_write import insert_candidate_record
from storage.sqlite.json_codec import loads_json
from storage.sqlite.session import connection, transaction, utc_now


def load_candidate_pool_dict(
    *,
    conn: sqlite3.Connection | None = None,
    path: str | Path | None = None,
) -> dict:
    """Load the candidate pool in legacy dict shape."""
    active, owned = connection(conn, path)
    try:
        result = {}
        for row in active.execute(
            "SELECT pool_key, payload_json FROM candidate_records ORDER BY rowid"
        ):
            payload = loads_json(row["payload_json"], {})
            if isinstance(payload, dict):
                result[row["pool_key"]] = payload
        return result
    finally:
        if owned:
            active.close()


def save_candidate_pool_dict(
    data: dict,
    *,
    conn: sqlite3.Connection | None = None,
    path: str | Path | None = None,
    purge_watched: bool = True,
) -> None:
    """Persist candidate pool with the same normalization as JSON write-path."""
    active, owned = connection(conn, path)
    normalized = normalize_storage_pool(data)
    if purge_watched:
        normalized = purge_watched_from_pool(normalized)
    try:
        with transaction(active, owned):
            active.execute("DELETE FROM candidate_records")
            timestamp = utc_now()
            for pool_key, candidate in normalized.items():
                insert_candidate_record(
                    active,
                    pool_key=pool_key,
                    candidate=candidate,
                    timestamp=timestamp,
                )
            rebuild_fts_index(active)
    finally:
        if owned:
            active.close()


def merge_candidate_pool_dict(
    data: dict,
    *,
    conn: sqlite3.Connection | None = None,
    path: str | Path | None = None,
    max_records: int = 1000,
) -> dict[str, int]:
    """Atomically upsert an incremental refill and evict only unprotected low-value rows."""
    active, owned = connection(conn, path)
    incoming = normalize_storage_pool(data)
    cap = max(1, int(max_records))
    try:
        with transaction(active, owned):
            timestamp = utc_now()
            incoming_keys: set[str] = set()
            for pool_key, candidate in incoming.items():
                media_type = str(candidate.get("media_type") or "tv").strip().casefold()
                tmdb_id = candidate.get("tmdb_id")
                active.execute("DELETE FROM candidate_records WHERE pool_key = ?", (pool_key,))
                if tmdb_id not in (None, ""):
                    active.execute(
                        "DELETE FROM candidate_records WHERE media_type = ? AND tmdb_id = ?",
                        (media_type, int(tmdb_id)),
                    )
                insert_candidate_record(
                    active,
                    pool_key=pool_key,
                    candidate=candidate,
                    timestamp=timestamp,
                )
                incoming_keys.add(pool_key)

            protected_identities = {
                str(row["identity_key"])
                for row in active.execute("SELECT identity_key FROM candidate_actions")
            }
            deck_row = active.execute(
                "SELECT state_json FROM recommendation_deck_state WHERE singleton_id = 1"
            ).fetchone()
            if deck_row is not None:
                deck = loads_json(deck_row["state_json"], {})
                if isinstance(deck, dict):
                    for candidate in list(deck.get("active") or []) + list(deck.get("reserve") or []):
                        if isinstance(candidate, dict):
                            protected_identities.add(candidate_state_identity_key(candidate))

            rows = active.execute(
                """
                SELECT pool_key, payload_json
                FROM candidate_records
                ORDER BY final_score ASC, quality_score ASC, tmdb_score ASC,
                         title_normalized ASC, pool_key ASC
                """
            ).fetchall()
            overflow = max(0, len(rows) - cap)
            evicted_keys: list[str] = []
            if overflow:
                for row in rows:
                    pool_key = str(row["pool_key"])
                    candidate = loads_json(row["payload_json"], {})
                    if pool_key in incoming_keys:
                        continue
                    if isinstance(candidate, dict) and candidate_state_identity_key(candidate) in protected_identities:
                        continue
                    evicted_keys.append(pool_key)
                    if len(evicted_keys) >= overflow:
                        break
                if evicted_keys:
                    active.executemany(
                        "DELETE FROM candidate_records WHERE pool_key = ?",
                        [(key,) for key in evicted_keys],
                    )
            rebuild_fts_index(active)
            count = int(active.execute("SELECT COUNT(*) AS count FROM candidate_records").fetchone()["count"])
        return {
            "merged": len(incoming),
            "evicted": len(evicted_keys),
            "pool_size": count,
        }
    finally:
        if owned:
            active.close()


def clear_candidate_pool(
    *,
    conn: sqlite3.Connection | None = None,
    path: str | Path | None = None,
) -> None:
    active, owned = connection(conn, path)
    try:
        with transaction(active, owned):
            active.execute("DELETE FROM candidate_records")
            rebuild_fts_index(active)
    finally:
        if owned:
            active.close()

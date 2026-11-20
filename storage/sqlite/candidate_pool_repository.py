"""SQLite repository for candidate pool payloads."""

from __future__ import annotations

from pathlib import Path
import sqlite3

from candidates.pool.normalization import normalize_storage_pool
from candidates.pool.watched_cleanup import purge_watched_from_pool
from candidates.models.keys import candidate_state_identity_key, candidate_typed_state_key, pool_entry_key
from candidates.models.schema import normalize_candidate_for_storage
from candidates.scoring.sort_keys import candidate_sort_score
from candidates.search.fts_index import rebuild_fts_index
from storage.sqlite.candidate_mapper import extract_candidate_record
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


def _incremental_candidates(data: dict) -> dict[tuple, tuple[str, dict]]:
    """Normalize fields, but never use the loose title key as a typed identity."""
    result = {}
    for value in (data if isinstance(data, dict) else {}).values():
        if not isinstance(value, dict):
            continue
        candidate = normalize_candidate_for_storage(value)
        loose = pool_entry_key(candidate)
        row = extract_candidate_record(loose, candidate)
        identity = (row.media_type, row.tmdb_id) if row.tmdb_id is not None else (loose,)
        old = result.get(identity)
        if old is None or candidate_sort_score(candidate) > candidate_sort_score(old[1]):
            result[identity] = loose, candidate
    return result


def _pick_incremental_slot(active: sqlite3.Connection, loose: str, identity: tuple):
    if len(identity) == 2:
        current = active.execute(
            """SELECT pool_key, tmdb_id, payload_json, created_at FROM candidate_records
               WHERE media_type = ? AND tmdb_id = ?""", identity
        ).fetchone()
        if current is not None:
            return current["pool_key"], current

    current = active.execute(
        """SELECT pool_key, tmdb_id, payload_json, created_at FROM candidate_records
           WHERE pool_key = ?""", (loose,)
    ).fetchone()
    if len(identity) == 1:
        if current is not None and current["tmdb_id"] is None:
            return loose, current
        # Reuse a legacy alternative after its original collision disappears.
        base = f"legacy:{loose}"
        prefix = f"{base}:"
        for old in active.execute(
            """SELECT pool_key, tmdb_id, payload_json, created_at FROM candidate_records
               WHERE tmdb_id IS NULL AND (pool_key = ? OR substr(pool_key, 1, ?) = ?)
               ORDER BY pool_key""",
            (base, len(prefix), prefix),
        ):
            payload = loads_json(old["payload_json"], {})
            if isinstance(payload, dict) and pool_entry_key(payload) == loose:
                return old["pool_key"], old
    else:
        base = f"tmdb:{identity[0]}:{identity[1]}"
    if current is None:
        return loose, None

    alternative, suffix = base, 1
    while (current := active.execute(
        "SELECT pool_key, tmdb_id, payload_json, created_at FROM candidate_records WHERE pool_key = ?",
        (alternative,),
    ).fetchone()) is not None:
        suffix += 1
        alternative = f"{base}:{suffix}"
    return alternative, None


def merge_candidate_pool_dict(
    data: dict,
    *,
    conn: sqlite3.Connection | None = None,
    path: str | Path | None = None,
    max_records: int = 1000,
) -> dict[str, int]:
    """Atomically upsert an incremental refill and evict only unprotected low-value rows."""
    incoming = _incremental_candidates(data)
    cap = max(1, int(max_records))
    active, owned = connection(conn, path)
    try:
        with transaction(active, owned):
            if not active.in_transaction:
                active.execute("BEGIN IMMEDIATE")
            timestamp = utc_now()
            for identity, (loose, candidate) in incoming.items():
                pool_key, existing_row = _pick_incremental_slot(active, loose, identity)
                candidate["pool_entry_key"] = pool_key
                if existing_row is not None:
                    existing = loads_json(existing_row["payload_json"], {})
                    if isinstance(existing, dict) and existing.get("details_enrichment_status") == "success":
                        for field_name in (
                            "adult", "runtime", "runtime_minutes", "episode_run_time",
                            "number_of_seasons", "number_of_episodes", "content_rating",
                            "keywords", "details_enrichment_contract_version",
                            "details_enrichment_status", "details_enriched_at",
                        ):
                            if field_name in existing and field_name not in candidate:
                                candidate[field_name] = existing[field_name]
                if existing_row is not None:
                    active.execute("DELETE FROM candidate_records WHERE pool_key = ?", (pool_key,))
                insert_candidate_record(
                    active,
                    pool_key=pool_key,
                    candidate=candidate,
                    timestamp=timestamp,
                )
                if existing_row is not None:
                    active.execute(
                        "UPDATE candidate_records SET created_at = ? WHERE pool_key = ?",
                        (existing_row["created_at"], pool_key),
                    )

            protected_identities = {
                str(row["identity_key"])
                for row in active.execute("SELECT identity_key FROM candidate_actions")
            }
            for row in active.execute(
                "SELECT title, year, media_type FROM watched_records WHERE payload_json != '{}'"
            ):
                protected_identities.add(
                    candidate_state_identity_key(
                        {
                            "title": row["title"],
                            "year": row["year"],
                            "media_type": row["media_type"],
                        }
                    )
                )
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
                    if isinstance(candidate, dict) and (
                        candidate_typed_state_key(candidate) in protected_identities
                        or candidate_state_identity_key(candidate) in protected_identities
                    ):
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

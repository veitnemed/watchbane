"""Transactional user-state transitions for candidate titles."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3

from candidates.models.keys import candidate_action_identity_key, candidate_imdb_identity, candidate_state_identity_key
from candidates.models.schema import coerce_candidate_number, normalize_candidate_record
from common import valid
from dataset.add_flow.save import build_movie_record_from_defaults
from dataset.models.identity import (
    build_dataset_record_key,
    normalize_title_key,
)
from dataset.models.media_type import normalize_media_type
from dataset.models.user_rating import normalize_user_rating
from dataset.records.features import build_computed_scores
from dataset.transfer.candidate import build_candidate_transfer_payload
from storage.normalize import normalize_raw_scores
from storage.sqlite import action_repository, impression_repository
from storage.sqlite.connection import connect
from storage.sqlite.json_codec import loads_json
from storage.sqlite.migrations import apply_migrations
from storage.sqlite.watched_mapper import extract_watched_record
from storage.sqlite.watched_write import delete_watched, update_watched_user_score, upsert_watched_row


STATE_AVAILABLE = "available"
STATE_WATCHLIST = "watchlist"
STATE_WATCHED = "watched"
STATE_HIDDEN = "hidden"


def load_action_candidates(
    action: str,
    *,
    path: str | Path | None = None,
) -> list[dict]:
    """Load normalized candidate payloads currently assigned to one action state."""
    stored = action_repository.load_effective_candidate_actions_dict(action, path=path)
    return [
        entry["candidate"]
        for entry in stored.values()
        if isinstance(entry, dict) and isinstance(entry.get("candidate"), dict)
    ]


def _candidate_year(candidate: dict) -> int | None:
    value = coerce_candidate_number(candidate.get("year"))
    if value is None or isinstance(value, bool):
        return None
    return int(value)


def _candidate_tmdb_id(candidate: dict) -> int | None:
    value = coerce_candidate_number(candidate.get("tmdb_id"))
    if value is None or isinstance(value, bool):
        return None
    return int(value)


def _find_watched_row(conn: sqlite3.Connection, candidate: dict, *, allow_legacy=True):
    media_type = normalize_media_type(candidate.get("media_type"))
    tmdb_id = _candidate_tmdb_id(candidate)
    if tmdb_id is not None:
        row = conn.execute(
            "SELECT * FROM watched_records WHERE media_type = ? AND tmdb_id = ? AND payload_json != '{}' LIMIT 1",
            (media_type, tmdb_id),
        ).fetchone()
        if row is not None or not allow_legacy:
            return row

    title = str(candidate.get("title") or candidate.get("name") or "").strip()
    year = _candidate_year(candidate)
    # For a known TMDb identity, the title/year fallback may attach an
    # unlinked legacy row, but a different known ID is a different work.
    matches = conn.execute(
        """
        SELECT * FROM watched_records
        WHERE title_normalized = ? AND media_type = ? AND year IS ?
          AND payload_json != '{}' AND tmdb_id IS NULL
        LIMIT 2
        """,
        (normalize_title_key(title), media_type, year),
    ).fetchall()
    if len(matches) != 1:
        return None
    row = matches[0]
    incoming_imdb = candidate_imdb_identity(candidate.get("imdb_id"))
    stored_imdb = candidate_imdb_identity(row["imdb_id"])
    # A legacy row can still carry a stable external identity even when no
    # TMDb ID was stored. Its title/year must not override contradictory IDs.
    if incoming_imdb and stored_imdb and incoming_imdb != stored_imdb:
        return None
    return row


def _state_in_connection(conn: sqlite3.Connection, candidate: dict) -> str:
    if _find_watched_row(conn, candidate) is not None:
        return STATE_WATCHED
    actions = action_repository.load_candidate_state_actions(candidate, conn=conn)
    if action_repository.ACTION_HIDDEN in actions:
        return STATE_HIDDEN
    if action_repository.ACTION_WATCHLIST in actions:
        return STATE_WATCHLIST
    return STATE_AVAILABLE


def get_title_state(candidate: dict, *, path: str | Path | None = None) -> str:
    normalized = normalize_candidate_record(candidate)
    conn = connect(path)
    try:
        apply_migrations(conn)
        return _state_in_connection(conn, normalized)
    finally:
        conn.close()


def get_title_states(candidates: dict[str, dict], *, path: str | Path | None = None) -> dict[str, str]:
    """Read states for a small result page through one storage connection."""
    if not candidates:
        return {}
    conn = connect(path)
    try:
        apply_migrations(conn)
        return {
            key: _state_in_connection(conn, normalize_candidate_record(candidate))
            for key, candidate in candidates.items()
        }
    finally:
        conn.close()


def _clear_candidate_actions(conn: sqlite3.Connection, candidate: dict) -> int:
    return action_repository.remove_candidate_actions(
        candidate,
        (action_repository.ACTION_WATCHLIST, action_repository.ACTION_HIDDEN),
        conn=conn,
    )


def _set_action_state(candidate: dict, action: str, *, path: str | Path | None = None) -> dict:
    normalized = normalize_candidate_record(candidate)
    conn = connect(path)
    try:
        apply_migrations(conn)
        with conn:
            conn.execute("BEGIN IMMEDIATE")
            if _find_watched_row(conn, normalized) is not None:
                _clear_candidate_actions(conn, normalized)
                state = STATE_WATCHED
            else:
                action_repository.set_candidate_action(normalized, action, conn=conn)
                state = action
        return {"ok": True, "identity": candidate_action_identity_key(normalized), "state": state}
    finally:
        conn.close()


def add_to_watchlist(candidate: dict, *, path: str | Path | None = None) -> dict:
    return _set_action_state(candidate, action_repository.ACTION_WATCHLIST, path=path)


def hide_candidate(candidate: dict, *, path: str | Path | None = None) -> dict:
    return _set_action_state(candidate, action_repository.ACTION_HIDDEN, path=path)


def restore_candidate(candidate: dict, *, path: str | Path | None = None) -> dict:
    normalized = normalize_candidate_record(candidate)
    conn = connect(path)
    try:
        apply_migrations(conn)
        with conn:
            conn.execute("BEGIN IMMEDIATE")
            _clear_candidate_actions(conn, normalized)
            impression_repository.forget_impressions([normalized], conn=conn)
            state = _state_in_connection(conn, normalized)
        return {"ok": True, "identity": candidate_action_identity_key(normalized), "state": state}
    finally:
        conn.close()


def remove_from_watchlist(candidate: dict, *, path: str | Path | None = None) -> dict:
    normalized = normalize_candidate_record(candidate)
    conn = connect(path)
    try:
        apply_migrations(conn)
        with conn:
            conn.execute("BEGIN IMMEDIATE")
            action_repository.remove_candidate_actions(
                normalized,
                (action_repository.ACTION_WATCHLIST,),
                conn=conn,
            )
            state = _state_in_connection(conn, normalized)
        return {"ok": True, "identity": candidate_action_identity_key(normalized), "state": state}
    finally:
        conn.close()


def remove_from_watched(candidate: dict, *, path: str | Path | None = None) -> dict:
    """Remove a watched payload so the title becomes recommendation-eligible again."""
    normalized = normalize_candidate_record(candidate)
    conn = connect(path)
    try:
        apply_migrations(conn)
        with conn:
            row = _find_watched_row(conn, normalized, allow_legacy=False)
            if row is not None:
                delete_watched(str(row["dataset_key"]), conn=conn)
            _clear_candidate_actions(conn, normalized)
            state = _state_in_connection(conn, normalized)
        return {"ok": True, "identity": candidate_state_identity_key(normalized), "state": state}
    finally:
        conn.close()


def mark_watched(
    candidate: dict,
    optional_user_score: int | None = None,
    *,
    path: str | Path | None = None,
) -> dict:
    normalized_score = normalize_user_rating(optional_user_score)
    if optional_user_score is not None and normalized_score is None:
        raise ValueError("user_score must be an integer from 1 to 3")
    normalized = normalize_candidate_record(candidate)
    transfer = build_candidate_transfer_payload(normalized)
    payload = build_movie_record_from_defaults(transfer["defaults"], normalized_score)
    meta_payload = transfer.get("meta_payload")
    conn = connect(path)
    try:
        apply_migrations(conn)
        with conn:
            # Lock before reading/allocating dataset keys so a simultaneous mark
            # cannot choose and then overwrite the same key.
            conn.execute("BEGIN IMMEDIATE")
            tmdb_id = _candidate_tmdb_id(normalized)
            existing = _find_watched_row(conn, normalized)
            if existing is None and tmdb_id is not None:
                # A previously removed title can still have metadata at its key.
                existing = conn.execute(
                    """
                    SELECT * FROM watched_records
                    WHERE media_type = ? AND tmdb_id = ? AND payload_json = '{}'
                    ORDER BY dataset_key LIMIT 1
                    """,
                    (normalize_media_type(normalized.get("media_type")), tmdb_id),
                ).fetchone()
            if existing is not None:
                dataset_key = str(existing["dataset_key"])
                existing_payload = loads_json(existing["payload_json"], {})
                if (tmdb_id is not None and tmdb_id > 0
                        and existing["tmdb_id"] == tmdb_id
                        and isinstance(existing_payload, dict) and existing_payload):
                    # A stale card may be submitted after another caller marked
                    # the same title. Keep the durable record and its edits.
                    # A deliberate score can change just that field.
                    if normalized_score is not None:
                        update_watched_user_score(dataset_key, normalized_score, conn=conn)
                    _clear_candidate_actions(conn, normalized)
                    return {
                        "ok": True,
                        "identity": candidate_state_identity_key(normalized),
                        "dataset_key": dataset_key,
                        "state": STATE_WATCHED,
                    }
                if optional_user_score is None and isinstance(existing_payload, dict):
                    existing_main_info = existing_payload.get("main_info")
                    if isinstance(existing_main_info, dict):
                        payload["main_info"]["user_score"] = existing_main_info.get("user_score")
                existing_meta = loads_json(existing["meta_json"], None)
                if not isinstance(meta_payload, dict) and isinstance(existing_meta, dict):
                    meta_payload = existing_meta
            else:
                title = str(payload.get("main_info", {}).get("title") or normalized.get("title") or "")
                year = payload.get("main_info", {}).get("year")
                media_type = payload.get("main_info", {}).get("media_type")
                # A second title lookup would bypass the known-ID and
                # ambiguity checks. Even metadata-only keys stay occupied.
                occupied = {row["dataset_key"]: None for row in
                            conn.execute("SELECT dataset_key FROM watched_records")}
                dataset_key = build_dataset_record_key(
                    occupied, title, year=year, media_type=media_type,
                )
            upsert_watched_row(
                conn,
                dataset_key=dataset_key,
                payload=payload,
                meta=meta_payload if isinstance(meta_payload, dict) else None,
            )
            _clear_candidate_actions(conn, normalized)
        return {
            "ok": True,
            "identity": candidate_state_identity_key(normalized),
            "dataset_key": dataset_key,
            "state": STATE_WATCHED,
        }
    finally:
        conn.close()


class ReviewedWatchedConflict(ValueError):
    def __init__(self, dataset_key: str, reason: str, message: str):
        super().__init__(message)
        self.dataset_key = dataset_key
        self.reason = reason


@dataclass(frozen=True)
class WatchedAddWriteResult:
    dataset_key: str
    payload: dict
    meta: dict


def _remove_exact_watched_from_candidate_pool(conn: sqlite3.Connection, media_type: str, tmdb_id: int | None) -> None:
    """Remove only an exact typed pool identity within the watched write transaction."""
    if tmdb_id is None or tmdb_id <= 0:
        return
    identity = (media_type, tmdb_id)
    pool_keys = conn.execute(
        "SELECT pool_key FROM candidate_records WHERE media_type = ? AND tmdb_id = ?", identity
    ).fetchall()
    if not pool_keys:
        return
    conn.executemany("DELETE FROM candidate_fts WHERE pool_key = ?", pool_keys)
    conn.execute("DELETE FROM candidate_records WHERE media_type = ? AND tmdb_id = ?", identity)


def save_watched_dataset_transition(
    data: dict,
    meta: dict,
    candidate: dict | None,
    *,
    path: str | Path | None = None,
) -> WatchedAddWriteResult:
    """Add one watched row; only an explicit candidate may transition actions."""
    if len(data) != 1 or not set(meta).issubset(data):
        raise ValueError("Reviewed transfer requires exactly one record and its own meta.")
    proposed_key, payload = next(iter(data.items()))
    meta_payload = dict(meta.get(proposed_key) or {})
    normalized = normalize_candidate_record(candidate) if candidate is not None else None
    incoming = extract_watched_record(proposed_key, payload, meta=meta_payload)
    candidate_id = _candidate_tmdb_id(normalized) if normalized is not None else None
    if candidate_id is not None:
        if (incoming.tmdb_id not in (None, candidate_id)
            or normalize_media_type(normalized.get("media_type")) != incoming.media_type):
            raise ReviewedWatchedConflict(
                proposed_key, "invalid_payload", "Идентификатор записи не совпадает с выбранным кандидатом.",
            )
        meta_payload["tmdb_id"] = candidate_id
    tmdb_id = candidate_id if candidate_id is not None else incoming.tmdb_id

    conn = connect(path)
    try:
        apply_migrations(conn)
        with conn:
            conn.execute("BEGIN IMMEDIATE")
            matching_id = conn.execute(
                """
                SELECT dataset_key, payload_json, meta_json FROM watched_records
                WHERE media_type = ? AND tmdb_id = ?
                ORDER BY (payload_json != '{}') DESC, dataset_key LIMIT 1
                """,
                (incoming.media_type, tmdb_id),
            ).fetchone()
            if matching_id and matching_id["payload_json"] != "{}":
                raise ReviewedWatchedConflict(
                    str(matching_id["dataset_key"]), "duplicate_tmdb_identity",
                    "This TMDb title is already in the watched collection.",
                )
            unresolved = conn.execute(
                """
                SELECT dataset_key FROM watched_records
                WHERE title_normalized = ? AND media_type = ? AND payload_json != '{}'
                  AND (year IS ? OR year IS NULL OR ? IS NULL)
                  AND (tmdb_id IS NULL OR ? IS NULL)
                LIMIT 1
                """,
                (incoming.title_normalized, incoming.media_type, incoming.year, incoming.year, tmdb_id),
            ).fetchone()
            if unresolved:
                raise ReviewedWatchedConflict(
                    str(unresolved["dataset_key"]), "duplicate_title",
                    "Ошибка добавления! Такой объект уже добавлен",
                )
            match = matching_id
            if match is None and tmdb_id is None:
                # An ID-less add may reuse only an unambiguous, equally ID-less
                # metadata row. Never inherit a known homonym's metadata/ID.
                rows = conn.execute(
                    """
                    SELECT dataset_key, meta_json FROM watched_records
                    WHERE title_normalized = ? AND media_type = ? AND year IS ?
                      AND tmdb_id IS NULL AND payload_json = '{}' AND meta_json IS NOT NULL
                    LIMIT 2
                    """,
                    (incoming.title_normalized, incoming.media_type, incoming.year),
                ).fetchall()
                match = rows[0] if len(rows) == 1 else None
            if match is not None:
                dataset_key = str(match["dataset_key"])
                old_meta = loads_json(match["meta_json"], {})
                if isinstance(old_meta, dict):
                    old_raw = old_meta.get("raw_scores", old_meta.get("raw"))
                    fresh_raw = meta_payload.get("raw_scores")
                    if isinstance(old_raw, dict) and isinstance(fresh_raw, dict):
                        usable_old = {key: value for key, value in old_raw.items()
                                      if valid.is_valid_raw_meta({key: value})}
                        raw = normalize_raw_scores(dict(usable_old, **fresh_raw))
                        meta_payload["raw_scores"] = raw
                        payload = dict(payload, raw_scores=raw,
                                       computed_scores=build_computed_scores(raw, payload["main_info"]))
                    meta_payload = dict(old_meta, **meta_payload)
            else:
                occupied = {row["dataset_key"]: None for row in conn.execute("SELECT dataset_key FROM watched_records")}
                dataset_key = build_dataset_record_key(
                    occupied, incoming.title, year=incoming.year, media_type=incoming.media_type,
                )
            upsert_watched_row(conn, dataset_key=dataset_key, payload=payload, meta=meta_payload)
            _remove_exact_watched_from_candidate_pool(conn, incoming.media_type, tmdb_id)
            if normalized is not None:
                _clear_candidate_actions(conn, normalized)
        return WatchedAddWriteResult(dataset_key, payload, meta_payload)
    finally:
        conn.close()

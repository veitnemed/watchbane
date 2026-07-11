"""Transactional user-state transitions for candidate titles."""

from __future__ import annotations

from pathlib import Path
import sqlite3

from candidates.models.keys import candidate_state_identity_key
from candidates.models.schema import coerce_candidate_number, normalize_candidate_record
from dataset.add_flow.save import build_movie_record_from_defaults
from dataset.models.identity import (
    build_dataset_record_key,
    find_dataset_title,
    normalize_title_key,
)
from dataset.models.media_type import normalize_media_type
from dataset.transfer.candidate import build_candidate_transfer_payload
from storage.sqlite import action_repository
from storage.sqlite.connection import connect
from storage.sqlite.json_codec import loads_json
from storage.sqlite.migrations import apply_migrations
from storage.sqlite.watched_meta import save_meta_dict
from storage.sqlite.watched_read import load_dataset_dict
from storage.sqlite.watched_write import delete_watched, save_dataset_dict, upsert_watched_row


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
    stored = action_repository.load_candidate_actions_dict(action, path=path)
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


def _find_watched_row(conn: sqlite3.Connection, candidate: dict):
    media_type = normalize_media_type(candidate.get("media_type"))
    tmdb_id = _candidate_tmdb_id(candidate)
    if tmdb_id is not None:
        row = conn.execute(
            "SELECT * FROM watched_records WHERE media_type = ? AND tmdb_id = ? AND payload_json != '{}' LIMIT 1",
            (media_type, tmdb_id),
        ).fetchone()
        if row is not None:
            return row

    title = str(candidate.get("title") or candidate.get("name") or "").strip()
    year = _candidate_year(candidate)
    if year is None:
        return conn.execute(
            """
            SELECT * FROM watched_records
            WHERE title_normalized = ? AND media_type = ? AND year IS NULL AND payload_json != '{}'
            LIMIT 1
            """,
            (normalize_title_key(title), media_type),
        ).fetchone()
    return conn.execute(
        """
        SELECT * FROM watched_records
        WHERE title_normalized = ? AND media_type = ? AND year = ? AND payload_json != '{}'
        LIMIT 1
        """,
        (normalize_title_key(title), media_type, year),
    ).fetchone()


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
            if _find_watched_row(conn, normalized) is not None:
                _clear_candidate_actions(conn, normalized)
                state = STATE_WATCHED
            else:
                _clear_candidate_actions(conn, normalized)
                result = action_repository.add_candidate_action(
                    action,
                    normalized,
                    conn=conn,
                    identity_key=candidate_state_identity_key(normalized),
                )
                state = action
        return {"ok": True, "identity": candidate_state_identity_key(normalized), "state": state}
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
            _clear_candidate_actions(conn, normalized)
            state = _state_in_connection(conn, normalized)
        return {"ok": True, "identity": candidate_state_identity_key(normalized), "state": state}
    finally:
        conn.close()


def remove_from_watchlist(candidate: dict, *, path: str | Path | None = None) -> dict:
    normalized = normalize_candidate_record(candidate)
    conn = connect(path)
    try:
        apply_migrations(conn)
        with conn:
            action_repository.remove_candidate_actions(
                normalized,
                (action_repository.ACTION_WATCHLIST,),
                conn=conn,
            )
            state = _state_in_connection(conn, normalized)
        return {"ok": True, "identity": candidate_state_identity_key(normalized), "state": state}
    finally:
        conn.close()


def remove_from_watched(candidate: dict, *, path: str | Path | None = None) -> dict:
    """Remove a watched payload so the title becomes recommendation-eligible again."""
    normalized = normalize_candidate_record(candidate)
    conn = connect(path)
    try:
        apply_migrations(conn)
        with conn:
            row = _find_watched_row(conn, normalized)
            if row is not None:
                delete_watched(str(row["dataset_key"]), conn=conn)
            _clear_candidate_actions(conn, normalized)
            state = _state_in_connection(conn, normalized)
        return {"ok": True, "identity": candidate_state_identity_key(normalized), "state": state}
    finally:
        conn.close()


def mark_watched(
    candidate: dict,
    optional_user_score: float | None = None,
    *,
    path: str | Path | None = None,
) -> dict:
    normalized = normalize_candidate_record(candidate)
    transfer = build_candidate_transfer_payload(normalized)
    payload = build_movie_record_from_defaults(transfer["defaults"], optional_user_score)
    meta_payload = transfer.get("meta_payload")
    conn = connect(path)
    try:
        apply_migrations(conn)
        with conn:
            existing = _find_watched_row(conn, normalized)
            if existing is not None:
                dataset_key = str(existing["dataset_key"])
                existing_payload = loads_json(existing["payload_json"], {})
                if optional_user_score is None and isinstance(existing_payload, dict):
                    existing_main_info = existing_payload.get("main_info")
                    if isinstance(existing_main_info, dict):
                        payload["main_info"]["user_score"] = existing_main_info.get("user_score")
                existing_meta = loads_json(existing["meta_json"], None)
                if not isinstance(meta_payload, dict) and isinstance(existing_meta, dict):
                    meta_payload = existing_meta
            else:
                data = load_dataset_dict(conn=conn)
                title = str(payload.get("main_info", {}).get("title") or normalized.get("title") or "")
                year = payload.get("main_info", {}).get("year")
                media_type = payload.get("main_info", {}).get("media_type")
                dataset_key = find_dataset_title(data, title, year=year, media_type=media_type) or (
                    build_dataset_record_key(data, title, year=year, media_type=media_type)
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


def save_watched_dataset_transition(
    data: dict,
    meta: dict,
    candidate: dict,
    *,
    path: str | Path | None = None,
) -> None:
    """Persist the reviewed transfer payload and clear candidate actions atomically."""
    normalized = normalize_candidate_record(candidate)
    conn = connect(path)
    try:
        apply_migrations(conn)
        with conn:
            save_dataset_dict(data, conn=conn)
            save_meta_dict(meta, conn=conn)
            _clear_candidate_actions(conn, normalized)
    finally:
        conn.close()

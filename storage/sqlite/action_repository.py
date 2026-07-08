"""SQLite repository for local candidate actions."""

from __future__ import annotations

from pathlib import Path
import sqlite3

from candidates.models.keys import title_identity_key
from candidates.models.schema import normalize_candidate_record
from storage.sqlite.json_codec import dumps_json, loads_json
from storage.sqlite.session import connection, transaction, utc_now


ACTION_WATCHLIST = "watchlist"
ACTION_HIDDEN = "hidden"


def _now() -> str:
    return utc_now()


def _timestamp_field(action: str) -> str:
    return "added_at" if action == ACTION_WATCHLIST else f"{action}_at"


def build_action_entry(candidate: dict, action: str, *, timestamp: str | None = None) -> dict:
    normalized = normalize_candidate_record(candidate)
    return {
        "candidate": normalized,
        _timestamp_field(action): timestamp or _now(),
    }


def load_candidate_actions_dict(
    action: str,
    *,
    conn: sqlite3.Connection | None = None,
    path: str | Path | None = None,
) -> dict:
    active, owned = connection(conn, path)
    try:
        result = {}
        for row in active.execute(
            """
            SELECT identity_key, candidate_json
            FROM candidate_actions
            WHERE action = ?
            ORDER BY rowid
            """,
            (action,),
        ):
            entry = loads_json(row["candidate_json"], {})
            if isinstance(entry, dict):
                result[row["identity_key"]] = entry
        return result
    finally:
        if owned:
            active.close()


def save_candidate_actions_dict(
    action: str,
    data: dict,
    *,
    conn: sqlite3.Connection | None = None,
    path: str | Path | None = None,
) -> None:
    active, owned = connection(conn, path)
    mapping = data if isinstance(data, dict) else {}
    try:
        with transaction(active, owned):
            active.execute("DELETE FROM candidate_actions WHERE action = ?", (action,))
            for identity, entry in mapping.items():
                if isinstance(entry, dict) is False:
                    continue
                created_at = (
                    entry.get(_timestamp_field(action))
                    or entry.get("created_at")
                    or _now()
                )
                active.execute(
                    """
                    INSERT INTO candidate_actions(
                      identity_key, action, candidate_json, created_at
                    )
                    VALUES (?, ?, ?, ?)
                    """,
                    (str(identity), action, dumps_json(entry), str(created_at)),
                )
    finally:
        if owned:
            active.close()


def add_candidate_action(
    action: str,
    candidate: dict,
    *,
    conn: sqlite3.Connection | None = None,
    path: str | Path | None = None,
) -> dict:
    active, owned = connection(conn, path)
    identity = title_identity_key(candidate)
    entry = build_action_entry(candidate, action)
    try:
        with transaction(active, owned):
            active.execute(
                """
                INSERT INTO candidate_actions(
                  identity_key, action, candidate_json, created_at
                )
                VALUES (?, ?, ?, ?)
                ON CONFLICT(identity_key, action) DO UPDATE SET
                  candidate_json = excluded.candidate_json,
                  created_at = excluded.created_at
                """,
                (identity, action, dumps_json(entry), entry[_timestamp_field(action)]),
            )
            count = active.execute(
                "SELECT COUNT(*) AS count FROM candidate_actions WHERE action = ?",
                (action,),
            ).fetchone()["count"]
        return {"ok": True, "identity": identity, "count": int(count)}
    finally:
        if owned:
            active.close()


def load_action_identities(
    action: str,
    *,
    conn: sqlite3.Connection | None = None,
    path: str | Path | None = None,
) -> set[str]:
    return set(load_candidate_actions_dict(action, conn=conn, path=path).keys())

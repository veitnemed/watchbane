"""SQLite repository for local candidate actions."""

from __future__ import annotations

from pathlib import Path
import sqlite3

from candidates.models.keys import (
    candidate_action_identity_key,
    candidate_legacy_state_keys,
    candidate_typed_state_key,
    title_identity_key,
)
from dataset.models.media_type import normalize_media_type
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
    identity_key: str | None = None,
) -> dict:
    active, owned = connection(conn, path)
    identity = str(identity_key or title_identity_key(candidate))
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


def _action_rows(active, actions=None, typed_identity=None):
    sql = "SELECT identity_key, action, candidate_json, created_at FROM candidate_actions"
    params = []
    clauses = []
    if actions is not None:
        placeholders = ", ".join("?" for _ in actions)
        clauses.append(f"action IN ({placeholders})")
        params.extend(actions)
    if typed_identity is not None:
        # New rows are exact primary-key lookups; scan old aliases, not other
        # canonical actions, for known-ID legacy imports.
        clauses.append("(identity_key = ? OR identity_key NOT LIKE 'tmdb:%')")
        params.append(typed_identity)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    return active.execute(sql + " ORDER BY created_at, rowid", tuple(params))


def _row_value(row):
    entry = loads_json(row["candidate_json"], {})
    candidate = entry.get("candidate") if isinstance(entry, dict) else None
    return entry, candidate if isinstance(candidate, dict) else {}


def _imdb_key(candidate):
    value = str(candidate.get("imdb_id") or "").strip().casefold()
    if value.startswith("tt") and value[2:].isascii() and value[2:].isdecimal():
        return normalize_media_type(candidate.get("media_type")), value
    return None


def _matching_rows(active, candidate, actions=None):
    typed = candidate_typed_state_key(candidate)
    imdb = _imdb_key(candidate) if typed else None
    legacy_keys = candidate_legacy_state_keys(candidate)
    media = normalize_media_type(candidate.get("media_type"))
    for row in _action_rows(active, actions, typed):
        entry, stored = _row_value(row)
        stored_typed = candidate_typed_state_key(stored)
        if typed is not None:
            # An IMDb identity is a safe bridge for an ID-less import; a matching
            # title alone cannot prove that two homonyms are the same work.
            if stored_typed == typed or (stored_typed is None and imdb is not None and _imdb_key(stored) == imdb):
                yield row, entry
        elif (stored_typed is None and row["identity_key"] in legacy_keys
              and normalize_media_type(stored.get("media_type")) == media):
            yield row, entry


def load_effective_candidate_actions_dict(
    action: str,
    *,
    conn: sqlite3.Connection | None = None,
    path: str | Path | None = None,
) -> dict:
    """Project known-ID duplicates as one current state without modifying imported rows."""
    active, owned = connection(conn, path)
    try:
        actions = (ACTION_WATCHLIST, ACTION_HIDDEN) if action in (ACTION_WATCHLIST, ACTION_HIDDEN) else (action,)
        result = {}
        typed = {}
        for row in _action_rows(active, actions):
            entry, candidate = _row_value(row)
            if not isinstance(entry, dict):
                continue
            key = candidate_typed_state_key(candidate)
            if key:
                typed[key] = (row["action"], entry)
            elif row["action"] == action:
                result[row["identity_key"]] = entry
        result.update({key: entry for key, (current, entry) in typed.items() if current == action})
        return result
    finally:
        if owned:
            active.close()


def set_candidate_action(candidate: dict, action: str, *, conn: sqlite3.Connection) -> str:
    """Switch state in the caller's transaction and keep repeat-save metadata."""
    normalized = normalize_candidate_record(candidate)
    identity = candidate_action_identity_key(normalized)
    actions = (ACTION_WATCHLIST, ACTION_HIDDEN)
    matches = list(_matching_rows(conn, normalized, actions))
    current = matches[-1][0]["action"] if matches else None
    same_action = [(row, entry) for row, entry in matches if row["action"] == action] if current == action else []
    if same_action:
        # Preserve the earliest timestamp and the known payload when only an
        # alternate spelling of the same work is saved again.
        created = str(same_action[0][0]["created_at"])
        new_entry = {}
        for _, entry in reversed(same_action):
            previous = entry.get("candidate")
            if isinstance(previous, dict):
                normalized.update({k: v for k, v in previous.items() if v not in (None, "", [], {})})
            new_entry.update(entry)
        if candidate_typed_state_key(candidate) is not None:
            normalized["tmdb_id"] = candidate["tmdb_id"]
        new_entry["candidate"] = normalized
        new_entry[_timestamp_field(action)] = created
    else:
        new_entry = build_action_entry(normalized, action)
        created = new_entry[_timestamp_field(action)]
    _delete_matches(conn, matches)
    conn.execute(
        """
        INSERT INTO candidate_actions(identity_key, action, candidate_json, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (identity, action, dumps_json(new_entry), created),
    )
    return identity


def _delete_matches(active, matches):
    cursor = active.executemany(
        "DELETE FROM candidate_actions WHERE identity_key = ? AND action = ?",
        [(row["identity_key"], row["action"]) for row, _ in matches],
    )
    return max(0, int(cursor.rowcount))


def remove_candidate_actions(
    candidate: dict,
    actions: tuple[str, ...] | list[str] | set[str],
    *,
    conn: sqlite3.Connection | None = None,
    path: str | Path | None = None,
) -> int:
    """Remove only rows proven to describe the same candidate identity."""
    action_values = tuple(dict.fromkeys(str(action) for action in actions if str(action)))
    if not action_values:
        return 0
    active, owned = connection(conn, path)
    try:
        with transaction(active, owned):
            if owned:
                active.execute("BEGIN IMMEDIATE")
            return _delete_matches(active, list(_matching_rows(active, candidate, action_values)))
    finally:
        if owned:
            active.close()


def load_candidate_state_actions(
    candidate: dict,
    *,
    conn: sqlite3.Connection | None = None,
    path: str | Path | None = None,
) -> set[str]:
    """Read one effective saved/hidden state, preferring the latest matching action."""
    active, owned = connection(conn, path)
    try:
        matches = list(_matching_rows(active, candidate, (ACTION_WATCHLIST, ACTION_HIDDEN)))
        if candidate_typed_state_key(candidate) and matches:
            return {str(matches[-1][0]["action"])}
        return {str(row["action"]) for row, _ in matches}
    finally:
        if owned:
            active.close()


def load_action_identities(
    action: str,
    *,
    conn: sqlite3.Connection | None = None,
    path: str | Path | None = None,
) -> set[str]:
    return set(load_effective_candidate_actions_dict(action, conn=conn, path=path).keys())

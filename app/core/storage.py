"""Small JSON lists for local search actions: watchlist and hidden candidates."""

from __future__ import annotations

import json
import os
from datetime import datetime

from candidates.models.keys import title_identity_key
from candidates.models.schema import normalize_candidate_record
from config import constant
from storage.backend import is_sqlite_backend


WATCHLIST_JSON = os.path.join(constant.CANDIDATES_DIR, "watchlist.json")
HIDDEN_JSON = os.path.join(constant.CANDIDATES_DIR, "hidden.json")


def _watchlist_json() -> str:
    return os.path.join(constant.CANDIDATES_DIR, "watchlist.json")


def _hidden_json() -> str:
    return os.path.join(constant.CANDIDATES_DIR, "hidden.json")


def _init_json(path: str) -> None:
    if os.path.exists(path):
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        json.dump({}, file, ensure_ascii=False, indent=4)


def init_search_lists() -> None:
    """Creates local search list JSON files when missing."""
    if is_sqlite_backend():
        from storage.sqlite.migrations import apply_migrations

        apply_migrations()
        return

    _init_json(_watchlist_json())
    _init_json(_hidden_json())


def _load_mapping(path: str) -> dict:
    _init_json(path)
    with open(path, "r", encoding="utf-8-sig") as file:
        data = json.load(file)
    return data if isinstance(data, dict) else {}


def _save_mapping(path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=4)


def _entry(candidate: dict, action: str) -> dict:
    normalized = normalize_candidate_record(candidate)
    return {
        "candidate": normalized,
        f"{action}_at": datetime.now().isoformat(timespec="seconds"),
    }


def add_to_watchlist(candidate: dict) -> dict:
    """Adds a candidate to the local watchlist."""
    if is_sqlite_backend():
        from storage.sqlite.action_repository import ACTION_WATCHLIST, add_candidate_action

        return add_candidate_action(ACTION_WATCHLIST, candidate)

    data = _load_mapping(_watchlist_json())
    identity = title_identity_key(candidate)
    data[identity] = _entry(candidate, "added")
    _save_mapping(_watchlist_json(), data)
    return {"ok": True, "identity": identity, "count": len(data)}


def add_to_hidden(candidate: dict) -> dict:
    """Adds a candidate to the hidden list."""
    if is_sqlite_backend():
        from storage.sqlite.action_repository import ACTION_HIDDEN, add_candidate_action

        return add_candidate_action(ACTION_HIDDEN, candidate)

    data = _load_mapping(_hidden_json())
    identity = title_identity_key(candidate)
    data[identity] = _entry(candidate, "hidden")
    _save_mapping(_hidden_json(), data)
    return {"ok": True, "identity": identity, "count": len(data)}


def load_hidden_identities() -> set[str]:
    if is_sqlite_backend():
        from storage.sqlite.action_repository import ACTION_HIDDEN, load_action_identities

        return load_action_identities(ACTION_HIDDEN)

    return set(_load_mapping(_hidden_json()).keys())


def load_watchlist_identities() -> set[str]:
    if is_sqlite_backend():
        from storage.sqlite.action_repository import ACTION_WATCHLIST, load_action_identities

        return load_action_identities(ACTION_WATCHLIST)

    return set(_load_mapping(_watchlist_json()).keys())


def load_watched_identities() -> set[str]:
    from candidates.pool.watched_cleanup import build_watched_signatures

    return build_watched_signatures()


def load_watched_title_keys() -> set[str]:
    from candidates.pool.dataset_overlap import build_dataset_title_keys

    return build_dataset_title_keys()

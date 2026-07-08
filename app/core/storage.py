"""App-core facade for local search actions and identity filters."""

from __future__ import annotations

from storage import actions as storage_actions


def init_search_lists() -> None:
    """Ensure runtime storage for local search lists exists."""
    storage_actions.init_search_lists()


def add_to_watchlist(candidate: dict) -> dict:
    """Add a candidate to the local watchlist."""
    return storage_actions.add_to_watchlist(candidate)


def add_to_hidden(candidate: dict) -> dict:
    """Add a candidate to the local hidden list."""
    return storage_actions.add_to_hidden(candidate)


def load_hidden_identities() -> set[str]:
    return storage_actions.load_hidden_identities()


def load_watchlist_identities() -> set[str]:
    return storage_actions.load_watchlist_identities()


def load_watched_identities() -> set[str]:
    return storage_actions.load_watched_identities()


def load_watched_title_keys() -> set[str]:
    return storage_actions.load_watched_title_keys()

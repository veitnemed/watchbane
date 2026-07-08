"""Storage facade for local candidate actions and search identities."""

from __future__ import annotations


def init_search_lists() -> None:
    """Ensure runtime storage for local search lists exists."""
    from storage.sqlite.migrations import apply_migrations

    apply_migrations()


def add_to_watchlist(candidate: dict) -> dict:
    """Add a candidate to the local watchlist."""
    from storage.sqlite.action_repository import ACTION_WATCHLIST, add_candidate_action

    return add_candidate_action(ACTION_WATCHLIST, candidate)


def add_to_hidden(candidate: dict) -> dict:
    """Add a candidate to the local hidden list."""
    from storage.sqlite.action_repository import ACTION_HIDDEN, add_candidate_action

    return add_candidate_action(ACTION_HIDDEN, candidate)


def load_hidden_identities() -> set[str]:
    """Load hidden candidate identity keys."""
    from storage.sqlite.action_repository import ACTION_HIDDEN, load_action_identities

    return load_action_identities(ACTION_HIDDEN)


def load_watchlist_identities() -> set[str]:
    """Load watchlist candidate identity keys."""
    from storage.sqlite.action_repository import ACTION_WATCHLIST, load_action_identities

    return load_action_identities(ACTION_WATCHLIST)


def load_watched_identities() -> set[str]:
    """Load watched title identity keys used by candidate filtering."""
    from candidates.pool.watched_cleanup import build_watched_signatures

    return build_watched_signatures()


def load_watched_title_keys() -> set[str]:
    """Load watched normalized title keys used by candidate filtering."""
    from candidates.pool.dataset_overlap import build_dataset_title_keys

    return build_dataset_title_keys()

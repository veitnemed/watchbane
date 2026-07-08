"""SQLite persistence facade for the runtime candidate pool."""

from __future__ import annotations


def init_candidate_pool() -> None:
    """Ensure the candidate pool table exists."""
    from storage.sqlite.migrations import apply_migrations

    apply_migrations()


def load_candidate_pool() -> dict:
    """Load the current runtime candidate pool from SQLite."""
    from storage.sqlite.candidate_repository import load_candidate_pool_dict

    return load_candidate_pool_dict()


def save_candidate_pool(data: dict) -> None:
    """Save the runtime candidate pool to SQLite."""
    from storage.sqlite.candidate_repository import save_candidate_pool_dict

    save_candidate_pool_dict(data)

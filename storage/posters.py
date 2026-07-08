"""Storage facade for runtime poster cache metadata."""

from __future__ import annotations


def load_poster_cache() -> dict:
    """Load poster cache metadata from canonical runtime storage."""
    from storage.sqlite.poster_repository import load_poster_cache_dict

    return load_poster_cache_dict()


def save_poster_cache(cache: dict) -> None:
    """Save poster cache metadata to canonical runtime storage."""
    from storage.sqlite.poster_repository import save_poster_cache_dict

    save_poster_cache_dict(cache)

"""Read facade for watched dataset display models."""

from __future__ import annotations

from copy import deepcopy

from candidates.models.keys import title_identity_key
from common.cards import build_watched_movie_card
from storage import data as storage_data

WatchedEntry = tuple[str, dict, dict]

_poster_cache = None
_lookup_cache = None


def reload_poster_cache() -> dict:
    """Reload poster cache from disk after add/delete/download side effects."""
    global _poster_cache
    try:
        from posters.cache import load_poster_cache

        _poster_cache = load_poster_cache()
    except Exception:
        _poster_cache = {}
    return _poster_cache


def _get_poster_cache() -> dict:
    global _poster_cache
    if _poster_cache is None:
        return reload_poster_cache()
    return _poster_cache


def build_watched_lookup_cache(meta=None, pool_by_identity=None) -> dict:
    """Build lookup map used by watched card descriptions."""
    if meta is None:
        meta = storage_data.load_meta()

    meta_by_title = {}
    for meta_title, meta_obj in meta.items():
        if isinstance(meta_obj, dict):
            meta_by_title[meta_title.strip().casefold()] = meta_obj

    if pool_by_identity is None:
        pool_by_identity = {}
        try:
            from candidates.repositories.pool_repository import load_candidate_pool

            for candidate in load_candidate_pool().values():
                if isinstance(candidate, dict):
                    pool_by_identity.setdefault(title_identity_key(candidate), candidate)
        except Exception:
            pass

    return {
        "meta_by_title": meta_by_title,
        "pool_by_identity": pool_by_identity,
    }


def _get_lookup_cache() -> dict:
    global _lookup_cache
    if _lookup_cache is None:
        _lookup_cache = build_watched_lookup_cache()
    return _lookup_cache


def load_watched_entries(data_language: str = "ru") -> list[WatchedEntry]:
    """Load dataset and return (dataset_key, movie, display_card) tuples."""
    data = storage_data.load_dataset()
    poster_cache = reload_poster_cache()
    lookup_cache = _get_lookup_cache()
    return [
        (
            key,
            movie,
            build_watched_movie_card(
                movie,
                poster_cache=poster_cache,
                lookup_cache=lookup_cache,
                data_language=data_language,
            ),
        )
        for key, movie in data.items()
    ]


def prepare_card_for_display(movie: dict, data_language: str = "ru") -> dict:
    """Build a watched display card without mutating the source movie."""
    original = deepcopy(movie)
    card = build_watched_movie_card(
        movie,
        poster_cache=_get_poster_cache(),
        lookup_cache=_get_lookup_cache(),
        data_language=data_language,
    )
    if movie != original:
        raise RuntimeError("build_watched_movie_card mutated the source movie")
    return card


__all__ = [
    "WatchedEntry",
    "build_watched_lookup_cache",
    "load_watched_entries",
    "prepare_card_for_display",
    "reload_poster_cache",
]

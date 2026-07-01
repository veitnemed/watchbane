"""Watched dataset load and card preparation (no Qt)."""

from __future__ import annotations

from copy import deepcopy

from desktop.shared.detail.types import DetailEntry
from storage import data as storage_data
from web.export import build_export_lookup_cache, build_watched_movie_card

WatchedEntry = DetailEntry

_poster_cache = None
_lookup_cache = None


def reload_poster_cache() -> dict:
    """Reload poster cache from disk (after add/delete or poster download)."""
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


def _get_lookup_cache() -> dict:
    global _lookup_cache
    if _lookup_cache is None:
        _lookup_cache = build_export_lookup_cache()
    return _lookup_cache


def load_watched_entries() -> list[WatchedEntry]:
    """Load dataset and return (dataset_key, movie, card) tuples."""
    data = storage_data.load_dataset()
    poster_cache = reload_poster_cache()
    lookup_cache = _get_lookup_cache()
    return [
        (key, movie, build_watched_movie_card(movie, poster_cache=poster_cache, lookup_cache=lookup_cache))
        for key, movie in data.items()
    ]


def prepare_card_for_display(movie: dict) -> dict:
    """Build a card dict for GUI display without mutating the source movie."""
    original = deepcopy(movie)
    card = build_watched_movie_card(
        movie,
        poster_cache=_get_poster_cache(),
        lookup_cache=_get_lookup_cache(),
    )
    if movie != original:
        raise RuntimeError("build_watched_movie_card mutated the source movie")
    return card


def watched_entry_search_haystack(entry: WatchedEntry) -> str:
    """Precomputed haystack for watched title search."""
    key, _movie, card = entry
    title = str(card.get("title") or key or "").strip().casefold()
    return f"{str(key).casefold()} {title}".strip()


def build_watched_search_index(entries: list[WatchedEntry]):
    """Build reusable search index for watched list filtering."""
    from desktop.shared.widgets.list_search import SearchIndex, SearchIndexItem

    items = [
        SearchIndexItem(
            item=entry,
            haystack=watched_entry_search_haystack(entry),
            selection_key=entry[0],
        )
        for entry in entries
    ]
    return SearchIndex(items)

"""Watched dataset load and card preparation (no Qt)."""

from __future__ import annotations

from common.cards import build_watched_movie_card
from dataset.models.media_type import MEDIA_TYPE_MOVIE, normalize_media_type
from dataset.read_models import watched as watched_read_model
from dataset.read_models.watched import (
    WatchedEntry,
    prepare_card_for_display,
    reload_poster_cache,
    sync_poster_for_display,
)

storage_data = watched_read_model.storage_data


def build_export_lookup_cache(meta=None, pool_by_identity=None) -> dict:
    """Compatibility alias for older desktop loader tests and callers."""
    return watched_read_model.build_watched_lookup_cache(
        meta=meta,
        pool_by_identity=pool_by_identity,
    )


def load_watched_entries(data_language: str = "ru") -> list[WatchedEntry]:
    """Load dataset and return (dataset_key, movie, display_card) tuples."""
    data = storage_data.load_dataset()
    poster_cache = reload_poster_cache()
    lookup_cache = build_export_lookup_cache()
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


def watched_entry_search_haystack(entry: WatchedEntry) -> str:
    """Precomputed haystack for watched title search."""
    key, movie, card = entry
    parts = [
        key,
        card.get("title"),
    ]
    if isinstance(movie, dict):
        main_info = movie.get("main_info") if isinstance(movie.get("main_info"), dict) else {}
        localized = movie.get("localized") if isinstance(movie.get("localized"), dict) else {}
        parts.extend([
            main_info.get("title"),
            main_info.get("media_type"),
            movie.get("title"),
            movie.get("name"),
            movie.get("media_type"),
            movie.get("original_title"),
            movie.get("original_name"),
            movie.get("enName"),
            movie.get("alternative_title"),
            movie.get("alternativeName"),
        ])
        for language in ("ru", "en"):
            block = localized.get(language)
            if isinstance(block, dict):
                parts.append(block.get("title"))
    media_type = normalize_media_type(card.get("media_type"))
    if media_type == MEDIA_TYPE_MOVIE:
        parts.extend(["movie", "film", "фильм", "фильмы"])
    else:
        parts.extend(["tv", "series", "сериал", "сериалы"])
    return " ".join(str(part).strip() for part in parts if part not in (None, "")).casefold()


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

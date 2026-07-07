"""Watched dataset load and card preparation (no Qt)."""

from __future__ import annotations

from dataset.read_models.watched import (
    WatchedEntry,
    load_watched_entries,
    prepare_card_for_display,
    reload_poster_cache,
    sync_poster_for_display,
)


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
            movie.get("title"),
            movie.get("name"),
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

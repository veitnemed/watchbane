"""Watched dataset load and card preparation (no Qt)."""

from __future__ import annotations

from dataset.read_models.watched import (
    WatchedEntry,
    load_watched_entries,
    prepare_card_for_display,
    reload_poster_cache,
)


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

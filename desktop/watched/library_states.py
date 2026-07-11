"""Adapters from persisted candidate actions to library detail entries."""

from __future__ import annotations

from pathlib import Path

from candidates import title_state_service
from desktop.candidates.presenters import build_candidate_readonly_detail_entry
from desktop.watched.model import WatchedEntry


SECTION_WATCHED = "watched"
SECTION_SAVED = title_state_service.STATE_WATCHLIST
SECTION_HIDDEN = title_state_service.STATE_HIDDEN
LIBRARY_SECTIONS = (SECTION_WATCHED, SECTION_SAVED, SECTION_HIDDEN)


def load_action_library_entries(
    action: str,
    *,
    data_language: str = "ru",
    path: str | Path | None = None,
) -> tuple[list[WatchedEntry], dict[str, dict]]:
    """Return display entries and their candidate payloads for one action state."""
    entries: list[WatchedEntry] = []
    candidates_by_key: dict[str, dict] = {}
    for candidate in title_state_service.load_action_candidates(action, path=path):
        entry = build_candidate_readonly_detail_entry(candidate, data_language=data_language)
        entries.append(entry)
        candidates_by_key[entry[0]] = candidate
    return entries, candidates_by_key

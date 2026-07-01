"""Shared filter/sort state between desktop Filters and Candidates tabs."""

from __future__ import annotations

from typing import Callable

from candidates import service as candidate_service

DEFAULT_SORT_MODE = "kp_score"

DEFAULT_BROWSE_FILTERS = {
    "criteria_name": None,
    "source": None,
    "country": [],
    "year_min": None,
    "year_max": None,
    "include_genres": [],
    "exclude_genres": [],
    "min_kp_score": None,
    "min_kp_votes": None,
    "min_imdb_score": None,
    "min_imdb_votes": None,
    "only_complete": False,
    "only_unwatched": True,
    "hide_hidden": False,
}


class CandidateSearchSession:
    """Runtime candidate search state shared across desktop tabs."""

    def __init__(self, service=None) -> None:
        self.service = service or candidate_service
        self.filters: dict | None = None
        self.filtered_candidates: list[dict] = []
        self.filtered_count: int = 0
        self.hidden_duplicates: int = 0
        self.sort_mode: str = DEFAULT_SORT_MODE
        self._sorted_candidates: list[dict] = []
        self._listeners: list[Callable[[], None]] = []

    def add_listener(self, callback: Callable[[], None]) -> None:
        if callback not in self._listeners:
            self._listeners.append(callback)

    def _notify_listeners(self) -> None:
        for callback in self._listeners:
            callback()

    def _clear_sorted_cache(self) -> None:
        self._sorted_candidates = []
        self.hidden_duplicates = 0

    def _rebuild_sorted_cache(self) -> None:
        if not self.filtered_candidates:
            self._clear_sorted_cache()
            return
        sort_view = self.service.sort_search_candidates(
            self.filtered_candidates,
            self.sort_mode,
        )
        self.hidden_duplicates = int(sort_view.get("hidden_duplicates") or 0)
        self._sorted_candidates = list(sort_view.get("candidates") or [])

    @property
    def has_results(self) -> bool:
        return self.filters is not None

    def apply_filters(self, filters: dict) -> dict:
        """Filter saved pool candidates without sorting."""
        overview = self.service.get_search_overview_view()
        if overview.get("is_empty"):
            self.filters = None
            self.filtered_candidates = []
            self.filtered_count = 0
            self._clear_sorted_cache()
            result = {
                "ok": False,
                "is_empty_pool": True,
                "filtered_count": 0,
                "message": "Общий candidate pool пуст.",
            }
            self._notify_listeners()
            return result

        search_view = self.service.search_candidate_pool(overview["candidates"], filters)
        self.filters = dict(filters)
        self.filtered_candidates = list(search_view.get("candidates") or [])
        self.filtered_count = int(search_view.get("filtered_count") or 0)
        self._rebuild_sorted_cache()
        result = {
            "ok": True,
            "is_empty_pool": False,
            "filtered_count": self.filtered_count,
            "message": f"После фильтра: {self.filtered_count}",
        }
        self._notify_listeners()
        return result

    def set_sort_mode(self, sort_mode: str) -> None:
        if sort_mode in self.service.SEARCH_SORT_MODES:
            self.sort_mode = sort_mode
            self._rebuild_sorted_cache()
            self._notify_listeners()

    def sorted_candidates(self) -> list[dict]:
        """Return all filtered candidates sorted by the active sort mode."""
        return list(self._sorted_candidates)

    def sorted_total_count(self) -> int:
        return len(self._sorted_candidates)

    def reload_from_pool(self) -> None:
        """Re-apply the last filter after pool mutation, or notify dependent views."""
        if self.filters is not None:
            self.apply_filters(self.filters)
        else:
            self._notify_listeners()

    def remove_candidate(self, candidate: dict) -> None:
        """Remove one candidate from current in-memory search results and notify views."""
        from desktop.candidates.presenters import candidate_detail_identity

        target_identity = candidate_detail_identity(candidate)
        self.filtered_candidates = [
            item
            for item in self.filtered_candidates
            if candidate_detail_identity(item) != target_identity
        ]
        self.filtered_count = len(self.filtered_candidates)
        self._rebuild_sorted_cache()
        self._notify_listeners()

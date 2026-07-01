"""Shared filter/sort state between desktop Filters and Candidates tabs."""

from __future__ import annotations

from typing import Callable

from candidates import service as candidate_service
from desktop.candidates.workers.search_worker import CandidateSearchWorker

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
        self.is_loading: bool = False
        self.last_error: str | None = None
        self._overview_cache: dict | None = None
        self._sorted_candidates: list[dict] = []
        self._listeners: list[Callable[[], None]] = []
        self._loading_listeners: list[Callable[[], None]] = []
        self._request_id = 0
        self._workers: list[CandidateSearchWorker] = []

    def add_listener(self, callback: Callable[[], None]) -> None:
        if callback not in self._listeners:
            self._listeners.append(callback)

    def add_loading_listener(self, callback: Callable[[], None]) -> None:
        if callback not in self._loading_listeners:
            self._loading_listeners.append(callback)

    def _notify_listeners(self) -> None:
        for callback in self._listeners:
            callback()

    def _notify_loading_listeners(self) -> None:
        for callback in self._loading_listeners:
            callback()

    def _set_loading(self, value: bool) -> None:
        if self.is_loading == value:
            return
        self.is_loading = value
        self._notify_loading_listeners()

    def invalidate_pool_cache(self) -> None:
        self._overview_cache = None

    def _get_overview(self) -> dict:
        if self._overview_cache is None:
            self._overview_cache = self.service.get_search_overview_view()
        return self._overview_cache

    def pool_stats(self) -> dict:
        overview = self._overview_cache or {}
        stats = overview.get("stats")
        if isinstance(stats, dict):
            return stats
        return {}

    def overview(self) -> dict:
        return self._get_overview()

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

    def _apply_search_result(self, filters: dict, result: dict) -> dict:
        if result.get("overview") is not None:
            self._overview_cache = result.get("overview")
        if result.get("is_empty_pool"):
            self.filters = None
            self.filtered_candidates = []
            self.filtered_count = 0
            self._clear_sorted_cache()
            applied = {
                "ok": False,
                "is_empty_pool": True,
                "filtered_count": 0,
                "message": result.get("message") or "Общий candidate pool пуст.",
            }
            self._notify_listeners()
            return applied

        if result.get("ok") is False:
            self.last_error = result.get("error") or result.get("message") or "Ошибка фильтрации."
            applied = {
                "ok": False,
                "is_empty_pool": False,
                "filtered_count": 0,
                "message": self.last_error,
                "error": self.last_error,
            }
            self._notify_listeners()
            return applied

        self.last_error = None
        self.filters = dict(filters)
        self.filtered_candidates = list(result.get("filtered_candidates") or result.get("candidates") or [])
        self.filtered_count = int(result.get("filtered_count") or len(self.filtered_candidates))
        self.hidden_duplicates = int(result.get("hidden_duplicates") or 0)
        self._sorted_candidates = list(result.get("candidates") or [])
        applied = {
            "ok": True,
            "is_empty_pool": False,
            "filtered_count": self.filtered_count,
            "message": result.get("message") or f"После фильтра: {self.filtered_count}",
        }
        self._notify_listeners()
        return applied

    def apply_filters(self, filters: dict) -> dict:
        """Filter saved pool candidates without sorting."""
        overview = self._get_overview()
        if overview.get("is_empty"):
            return self._apply_search_result(filters, {
                "ok": False,
                "is_empty_pool": True,
                "filtered_count": 0,
                "message": "Общий candidate pool пуст.",
                "overview": overview,
                "candidates": [],
                "hidden_duplicates": 0,
            })

        search_view = self.service.search_candidate_pool(overview["candidates"], filters)
        filtered_candidates = list(search_view.get("candidates") or [])
        sort_view = self.service.sort_search_candidates(filtered_candidates, self.sort_mode)
        return self._apply_search_result(filters, {
            "ok": True,
            "is_empty_pool": False,
            "filtered_count": int(search_view.get("filtered_count") or len(filtered_candidates)),
            "message": f"После фильтра: {int(search_view.get('filtered_count') or len(filtered_candidates))}",
            "overview": overview,
            "filtered_candidates": filtered_candidates,
            "candidates": list(sort_view.get("candidates") or []),
            "hidden_duplicates": int(sort_view.get("hidden_duplicates") or 0),
        })

    def apply_filters_async(self, filters: dict, *, parent=None) -> int:
        """Filter candidates in a worker and ignore stale results."""
        self._request_id += 1
        request_id = self._request_id
        self.last_error = None
        self._set_loading(True)
        worker = CandidateSearchWorker(
            request_id=request_id,
            service=self.service,
            filters=filters,
            sort_mode=self.sort_mode,
            overview=self._overview_cache,
            parent=parent,
        )
        worker.completed.connect(lambda rid, result: self._on_async_result(rid, dict(filters), result))
        worker.finished.connect(lambda worker=worker: self._remove_worker(worker))
        worker.finished.connect(worker.deleteLater)
        self._workers.append(worker)
        worker.start()
        return request_id

    def _remove_worker(self, worker: CandidateSearchWorker) -> None:
        self._workers = [item for item in self._workers if item is not worker]

    def _on_async_result(self, request_id: int, filters: dict, result: dict) -> None:
        if request_id != self._request_id:
            return
        self._set_loading(False)
        self._apply_search_result(filters, result)

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

    def reload_from_pool(self, *, force: bool = False) -> None:
        """Re-apply the last filter after pool mutation, or notify dependent views."""
        if force:
            self.invalidate_pool_cache()
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
        if self._overview_cache is not None:
            cached_candidates = [
                item
                for item in self._overview_cache.get("candidates") or []
                if candidate_detail_identity(item) != target_identity
            ]
            self._overview_cache = {**self._overview_cache, "candidates": cached_candidates}
        self._rebuild_sorted_cache()
        self._notify_listeners()

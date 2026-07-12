"""Shared filter/sort state between desktop Filters and Candidates tabs."""

from __future__ import annotations

import uuid
from time import perf_counter
from typing import Callable

from app.use_cases import candidate_search
from candidates.preferences import RecommendationVector
from desktop.candidates.workers.search_worker import CandidateSearchWorker
from diagnostics.gui_event_log import log_event

DEFAULT_SORT_MODE = "final_score"

DEFAULT_BROWSE_FILTERS = {
    "criteria_name": None,
    "source": None,
    "country": [],
    "media_type": None,
    "year_min": None,
    "year_max": None,
    "include_genres": [],
    "exclude_genres": [],
    "min_tmdb_score": None,
    "min_tmdb_votes": None,
    "only_complete": False,
    "only_unwatched": True,
    "hide_hidden": False,
}


class CandidateSearchSession:
    """Runtime candidate search state shared across desktop tabs."""

    def __init__(self, service=None) -> None:
        self.service = service or candidate_search
        self.filters: dict | None = None
        self.filtered_candidates: list[dict] = []
        self.filtered_count: int = 0
        self.hidden_duplicates: int = 0
        self.sort_mode: str = DEFAULT_SORT_MODE
        self.recommendation_vector: dict = RecommendationVector().to_dict()
        self.variation_seed: int = 0
        self.is_loading: bool = False
        self.last_error: str | None = None
        self._overview_cache: dict | None = None
        self._sorted_candidates: list[dict] = []
        self._listeners: list[Callable[[], None]] = []
        self._loading_listeners: list[Callable[[], None]] = []
        self._request_id = 0
        self._workers: list[CandidateSearchWorker] = []
        self._request_started_at: dict[int, float] = {}
        self._request_search_id: dict[int, str] = {}
        self._current_search_id: str | None = None
        self._last_search_context: dict | None = None
        self._sort_mode_before_search: str | None = None

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

    def last_search_context(self) -> dict | None:
        """Metadata of the last finalized filter apply (for query logging)."""
        return dict(self._last_search_context) if self._last_search_context is not None else None

    def _record_search_context(
        self,
        *,
        search_id: str | None,
        filters: dict,
        applied: dict,
        latency_ms: float | None,
        text_query: str | None = None,
    ) -> None:
        self._current_search_id = search_id
        self._last_search_context = {
            "search_id": search_id,
            "filters": dict(filters or {}),
            "text_query": str(text_query or ""),
            "sort_mode": self.sort_mode,
            "filtered_count": int(applied.get("filtered_count") or 0),
            "ok": bool(applied.get("ok")),
            "is_empty_pool": bool(applied.get("is_empty_pool")),
            "latency_ms": latency_ms,
        }

    def _search_pool(self, candidates: list, filters: dict, *, text_query: str | None = None) -> dict:
        normalized_query = str(text_query or "").strip()
        if normalized_query and hasattr(self.service, "search_candidate_pool_text"):
            return self.service.search_candidate_pool_text(
                candidates,
                filters,
                text_query=normalized_query,
            )
        return self.service.search_candidate_pool(candidates, filters)

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

    def apply_filters(self, filters: dict, *, text_query: str | None = None) -> dict:
        """Filter saved pool candidates without sorting."""
        search_id = uuid.uuid4().hex
        started = perf_counter()
        overview = self._get_overview()
        if overview.get("is_empty"):
            applied = self._apply_search_result(filters, {
                "ok": False,
                "is_empty_pool": True,
                "filtered_count": 0,
                "message": "Общий candidate pool пуст.",
                "overview": overview,
                "candidates": [],
                "hidden_duplicates": 0,
            })
            self._record_search_context(
                search_id=search_id,
                filters=filters,
                applied=applied,
                latency_ms=round((perf_counter() - started) * 1000, 1),
                text_query=text_query,
            )
            return applied

        search_view = self._search_pool(overview["candidates"], filters, text_query=text_query)
        filtered_candidates = list(search_view.get("candidates") or [])
        sort_view = self.service.sort_search_candidates(filtered_candidates, self.sort_mode)
        applied = self._apply_search_result(filters, {
            "ok": True,
            "is_empty_pool": False,
            "filtered_count": int(search_view.get("filtered_count") or len(filtered_candidates)),
            "message": f"После фильтра: {int(search_view.get('filtered_count') or len(filtered_candidates))}",
            "overview": overview,
            "filtered_candidates": filtered_candidates,
            "candidates": list(sort_view.get("candidates") or []),
            "hidden_duplicates": int(sort_view.get("hidden_duplicates") or 0),
        })
        self._record_search_context(
            search_id=search_id,
            filters=filters,
            applied=applied,
            latency_ms=round((perf_counter() - started) * 1000, 1),
            text_query=text_query,
        )
        return applied

    def apply_filters_async(
        self,
        filters: dict,
        *,
        text_query: str | None = None,
        parent=None,
    ) -> int:
        """Filter candidates in a worker and ignore stale results."""
        self._request_id += 1
        request_id = self._request_id
        self.last_error = None
        self._set_loading(True)
        self._request_started_at[request_id] = perf_counter()
        self._request_search_id[request_id] = uuid.uuid4().hex
        log_event(
            "candidates.search.async.begin",
            request_id=request_id,
            has_cached_overview=self._overview_cache is not None,
            cached_overview_empty=bool((self._overview_cache or {}).get("is_empty")),
            sort_mode=self.sort_mode,
            has_text_query=bool(str(text_query or "").strip()),
        )
        worker = CandidateSearchWorker(
            request_id=request_id,
            service=self.service,
            filters=filters,
            sort_mode=self.sort_mode,
            overview=self._overview_cache,
            text_query=text_query,
            parent=parent,
        )
        worker.completed.connect(
            lambda rid, result: self._on_async_result(rid, dict(filters), result, text_query=text_query)
        )
        worker.finished.connect(lambda worker=worker: self._remove_worker(worker))
        worker.finished.connect(worker.deleteLater)
        self._workers.append(worker)
        worker.start()
        return request_id

    def _remove_worker(self, worker: CandidateSearchWorker) -> None:
        self._workers = [item for item in self._workers if item is not worker]

    def _on_async_result(
        self,
        request_id: int,
        filters: dict,
        result: dict,
        *,
        text_query: str | None = None,
    ) -> None:
        search_id = self._request_search_id.pop(request_id, None)
        if request_id != self._request_id:
            self._request_started_at.pop(request_id, None)
            return
        started = self._request_started_at.pop(request_id, None)
        self._set_loading(False)
        applied = self._apply_search_result(filters, result)
        elapsed_ms = None if started is None else round((perf_counter() - started) * 1000, 1)
        worker_latency = result.get("latency_ms")
        self._record_search_context(
            search_id=search_id,
            filters=filters,
            applied=applied,
            latency_ms=worker_latency if worker_latency is not None else elapsed_ms,
            text_query=text_query,
        )
        log_event(
            "candidates.search.async.end",
            request_id=request_id,
            ok=applied.get("ok"),
            is_empty_pool=applied.get("is_empty_pool"),
            filtered_count=applied.get("filtered_count"),
            elapsed_ms=elapsed_ms,
            error=applied.get("error"),
        )

    def set_sort_mode(self, sort_mode: str) -> None:
        if sort_mode in self.service.SEARCH_SORT_MODES:
            self.sort_mode = sort_mode
            self._rebuild_sorted_cache()
            if self._last_search_context is not None:
                self._current_search_id = uuid.uuid4().hex
                self._last_search_context = {
                    **self._last_search_context,
                    "search_id": self._current_search_id,
                    "sort_mode": sort_mode,
                    "latency_ms": None,
                }
            self._notify_listeners()

    def set_recommendation_vector(self, vector: RecommendationVector | dict) -> bool:
        normalized = (
            vector.normalized() if isinstance(vector, RecommendationVector)
            else RecommendationVector.from_dict(vector)
        ).to_dict()
        if normalized == self.recommendation_vector:
            return False
        self.recommendation_vector = normalized
        self._notify_listeners()
        return True

    def next_recommendation_variation(self) -> int:
        self.variation_seed += 1
        self._notify_listeners()
        return self.variation_seed

    def maybe_auto_sort_for_text_query(self, text_query: str | None) -> bool:
        """Switch to relevance while typing; restore when query is cleared."""
        normalized = str(text_query or "").strip()
        if normalized:
            if self._sort_mode_before_search is None and self.sort_mode != "relevance":
                self._sort_mode_before_search = self.sort_mode
                self.set_sort_mode("relevance")
                return True
            return False
        if self._sort_mode_before_search is None:
            return False
        restore_mode = self._sort_mode_before_search
        self._sort_mode_before_search = None
        self.set_sort_mode(restore_mode)
        return True

    def sorted_candidates(self) -> list[dict]:
        """Return all filtered candidates sorted by the active sort mode."""
        return list(self._sorted_candidates)

    def sorted_total_count(self) -> int:
        return len(self._sorted_candidates)

    def reload_from_pool(self, *, force: bool = False) -> dict:
        """Re-apply the last filter after pool mutation, or notify dependent views."""
        local_count_before = int(self.filtered_count or 0)
        if force:
            self.invalidate_pool_cache()
        if self.filters is not None:
            text_query = None
            if self._last_search_context is not None:
                text_query = self._last_search_context.get("text_query")
            applied = self.apply_filters(dict(self.filters), text_query=text_query)
            return {
                **applied,
                "reapplied": True,
                "local_count_before": local_count_before,
                "visible_count": int(self.filtered_count or 0),
            }
        else:
            self._notify_listeners()
            return {
                "ok": True,
                "reapplied": False,
                "filtered_count": int(self.filtered_count or 0),
                "local_count_before": local_count_before,
                "visible_count": int(self.filtered_count or 0),
            }

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

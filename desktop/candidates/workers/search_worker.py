"""Background worker for desktop candidate filtering."""

from __future__ import annotations

from time import perf_counter

from PyQt6.QtCore import QThread, pyqtSignal


class CandidateSearchWorker(QThread):
    """Load/filter/sort candidate pool without blocking the GUI thread."""

    completed = pyqtSignal(int, dict)

    def __init__(
        self,
        *,
        request_id: int,
        service,
        filters: dict,
        sort_mode: str,
        overview: dict | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._request_id = int(request_id)
        self._service = service
        self._filters = dict(filters or {})
        self._sort_mode = str(sort_mode)
        self._overview = overview

    def run(self) -> None:
        started = perf_counter()
        try:
            overview = self._overview or self._service.get_search_overview_view()
            if overview.get("is_empty"):
                self.completed.emit(
                    self._request_id,
                    {
                        "ok": False,
                        "is_empty_pool": True,
                        "filtered_count": 0,
                        "message": "Общий candidate pool пуст.",
                        "overview": overview,
                        "candidates": [],
                        "hidden_duplicates": 0,
                        "latency_ms": round((perf_counter() - started) * 1000, 1),
                    },
                )
                return

            search_view = self._service.search_candidate_pool(
                overview.get("candidates") or [],
                self._filters,
            )
            filtered_candidates = list(search_view.get("candidates") or [])
            sort_view = self._service.sort_search_candidates(filtered_candidates, self._sort_mode)
            sorted_candidates = list(sort_view.get("candidates") or [])
            filtered_count = int(search_view.get("filtered_count") or len(filtered_candidates))
            self.completed.emit(
                self._request_id,
                {
                    "ok": True,
                    "is_empty_pool": False,
                    "filtered_count": filtered_count,
                    "message": f"После фильтра: {filtered_count}",
                    "overview": overview,
                    "candidates": sorted_candidates,
                    "filtered_candidates": filtered_candidates,
                    "hidden_duplicates": int(sort_view.get("hidden_duplicates") or 0),
                    "latency_ms": round((perf_counter() - started) * 1000, 1),
                },
            )
        except Exception as error:
            self.completed.emit(
                self._request_id,
                {
                    "ok": False,
                    "is_empty_pool": False,
                    "filtered_count": 0,
                    "message": str(error),
                    "error": str(error),
                    "candidates": [],
                    "hidden_duplicates": 0,
                    "latency_ms": round((perf_counter() - started) * 1000, 1),
                },
            )

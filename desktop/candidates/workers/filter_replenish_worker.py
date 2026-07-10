"""Background worker for filter-driven candidate replenish."""

from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal

from candidates import service as candidate_service
from diagnostics.gui_event_log import log_event, log_exception


class FilterReplenishWorker(QThread):
    """Run filter-driven pool replenish off the UI thread."""

    progress = pyqtSignal(object)
    finished_with_result = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, intent: dict, *, service=None, parent=None) -> None:
        super().__init__(parent)
        self._intent = dict(intent or {})
        self._service = service or candidate_service
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        log_event("candidates.filter_replenish.worker.begin", intent=self._intent)
        try:
            result = self._service.replenish_candidate_pool_for_filters(
                self._intent,
                progress_callback=self.progress.emit,
                cancel_checker=lambda: self._cancelled,
                dry_run=False,
            )
        except Exception as error:  # noqa: BLE001 - surface safely to UI
            log_exception("candidates.filter_replenish.worker.error", error)
            self.failed.emit(str(error))
            return
        log_event(
            "candidates.filter_replenish.worker.end",
            ok=result.get("ok"),
            blocked=result.get("blocked"),
            created_count=result.get("created_count"),
            saved_count=result.get("saved_count"),
            api_requests=result.get("api_requests"),
        )
        self.finished_with_result.emit(result)

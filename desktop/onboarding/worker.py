"""Background worker for deterministic onboarding candidate autofill."""

from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal

from candidates import service as candidate_service
from diagnostics.gui_event_log import log_event, log_exception


class OnboardingAutofillWorker(QThread):
    """Build the starter candidate pool off the UI thread."""

    progress = pyqtSignal(object)
    finished_with_result = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, profile: dict, *, strategy: str | None = None, parent=None) -> None:
        super().__init__(parent)
        self._profile = dict(profile)
        self._strategy = strategy
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        log_event("onboarding.autofill.worker.begin", profile=self._profile)
        try:
            result = candidate_service.build_onboarding_candidate_pool(
                self._profile,
                progress_callback=self.progress.emit,
                cancel_checker=lambda: self._cancelled,
                strategy=self._strategy,
            )
        except Exception as error:  # noqa: BLE001 - surface to wizard
            log_exception("onboarding.autofill.worker.error", error)
            self.failed.emit(str(error))
            return
        log_event(
            "onboarding.autofill.worker.end",
            created_count=result.get("created_count"),
            api_requests=result.get("api_requests"),
            cancelled=result.get("cancelled"),
            planned_counts=result.get("planned_counts"),
            actual_counts=result.get("actual_counts"),
            source_stats=result.get("source_stats"),
            request_stats=result.get("request_stats"),
            strategy=result.get("strategy"),
            warning=result.get("warning"),
        )
        self.finished_with_result.emit(result)

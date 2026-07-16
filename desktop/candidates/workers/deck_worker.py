"""Generation-safe background recommendation deck builder."""

from __future__ import annotations

from time import perf_counter

from PyQt6.QtCore import QThread, pyqtSignal

from diagnostics.gui_event_log import log_exception


class RecommendationDeckWorker(QThread):
    """Build or restore one local deck without blocking the Qt event loop."""

    completed = pyqtSignal(int, object, float)
    failed = pyqtSignal(int, str, float)

    def __init__(
        self,
        *,
        generation: int,
        service,
        preferences: dict,
        now,
        vector: dict,
        variation_seed: int,
        force_new: bool,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._generation = int(generation)
        self._service = service
        self._preferences = dict(preferences or {})
        self._now = now
        self._vector = dict(vector or {})
        self._variation_seed = int(variation_seed or 0)
        self._force_new = bool(force_new)

    def run(self) -> None:
        if self.isInterruptionRequested():
            return
        started = perf_counter()
        try:
            try:
                deck = self._service.refresh_deck(
                    self._preferences,
                    self._now,
                    vector=self._vector,
                    variation_seed=self._variation_seed,
                    force_new=self._force_new,
                )
            except TypeError as error:
                if "unexpected keyword argument" not in str(error):
                    raise
                deck = self._service.refresh_deck(
                    self._preferences,
                    self._now,
                    force_new=self._force_new,
                )
        except Exception as error:  # noqa: BLE001 - safely report worker failures
            elapsed_ms = (perf_counter() - started) * 1000.0
            log_exception(
                "recommendations.deck.worker.error",
                error,
                generation=self._generation,
                elapsed_ms=round(elapsed_ms, 1),
            )
            self.failed.emit(self._generation, str(error), elapsed_ms)
            return
        if self.isInterruptionRequested():
            return
        self.completed.emit(
            self._generation,
            deck if isinstance(deck, dict) else {},
            (perf_counter() - started) * 1000.0,
        )

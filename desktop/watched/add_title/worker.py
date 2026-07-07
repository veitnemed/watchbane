"""Background worker for add-title resolve in desktop GUI."""

from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal

from dataset import service
from diagnostics.gui_event_log import log_event, log_exception


class AddTitleResolveWorker(QThread):
    """Resolve title metadata off the UI thread."""

    progress = pyqtSignal(int, int, str)
    finished_with_result = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, title: str, country: str, parent=None, *, data_language: str = "ru") -> None:
        super().__init__(parent)
        self._title = title
        self._country = country
        self._data_language = data_language

    def run(self) -> None:
        log_event("add_title.worker.run.begin", title=self._title, country=self._country)
        try:
            bundle = service.resolve_title_for_add(
                self._title,
                self._country,
                on_progress=self._on_progress,
                data_language=self._data_language,
            )
        except Exception as error:  # noqa: BLE001 - surface to dialog
            log_exception("add_title.worker.run.error", error, title=self._title, country=self._country)
            self.failed.emit(str(error))
            return
        log_event("add_title.worker.run.end", title=self._title, country=self._country, found=bundle.found)
        self.finished_with_result.emit(bundle)

    def _on_progress(self, current: int, total: int, message: str) -> None:
        self.progress.emit(current, total, message)

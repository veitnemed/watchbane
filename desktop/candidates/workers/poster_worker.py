"""Background worker for candidate poster preview download in desktop GUI."""

from __future__ import annotations

from copy import deepcopy

from PyQt6.QtCore import QThread, pyqtSignal

from posters.download_images import download_poster_url_for_preview


class CandidatePosterDownloadWorker(QThread):
    """Download one candidate poster URL into preview cache off the UI thread."""

    finished_with_path = pyqtSignal(str)
    failed = pyqtSignal()

    def __init__(self, poster_url: str, parent=None) -> None:
        super().__init__(parent)
        self._poster_url = poster_url

    def run(self) -> None:
        local_path = download_poster_url_for_preview(self._poster_url)
        if local_path not in (None, ""):
            self.finished_with_path.emit(str(local_path))
            return
        self.failed.emit()


class CandidateLocalizedPosterWorker(QThread):
    """Fetch localized poster metadata off the UI thread."""

    finished_with_candidate = pyqtSignal(str, object, bool)
    failed = pyqtSignal(str)

    def __init__(self, identity: str, candidate: dict, data_language: str, parent=None) -> None:
        super().__init__(parent)
        self._identity = str(identity or "")
        self._candidate = deepcopy(candidate)
        self._data_language = str(data_language or "ru")

    def run(self) -> None:
        if self.isInterruptionRequested():
            return
        try:
            from candidates.pool.localized_posters import ensure_candidate_localized_poster

            updated_candidate, changed = ensure_candidate_localized_poster(
                self._candidate,
                data_language=self._data_language,
            )
        except Exception:
            if self.isInterruptionRequested():
                return
            self.failed.emit(self._identity)
            return

        if self.isInterruptionRequested():
            return
        self.finished_with_candidate.emit(
            self._identity,
            updated_candidate if isinstance(updated_candidate, dict) else self._candidate,
            bool(changed),
        )

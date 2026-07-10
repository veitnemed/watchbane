"""Background workers for the TMDb startup gate."""

from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal

from apis import tmdb_api
from apis.tmdb_connectivity import check_tmdb_network_available, evaluate_tmdb_startup_readiness


class TmdbNetworkProbeWorker(QThread):
    """Probe TMDb DNS and HTTPS reachability without a token."""

    completed = pyqtSignal(dict)

    def run(self) -> None:
        self.completed.emit(check_tmdb_network_available())


class TmdbStartupValidateWorker(QThread):
    """Validate a bearer token and persist it on success."""

    completed = pyqtSignal(dict)

    def __init__(self, token: str, *, parent=None) -> None:
        super().__init__(parent)
        self._token = str(token or "").strip()

    def run(self) -> None:
        readiness = evaluate_tmdb_startup_readiness(self._token)
        if readiness.get("ready") is True:
            try:
                tmdb_api.save_tmdb_bearer_token(self._token)
            except Exception as error:
                self.completed.emit(
                    {
                        "ready": False,
                        "error": "save_failed",
                        "details": str(error),
                    }
                )
                return
        self.completed.emit(readiness)

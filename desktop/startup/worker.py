"""Background workers for the TMDb startup gate."""

from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal

from apis import tmdb_api
from apis.tmdb_connectivity import check_tmdb_network_available, evaluate_tmdb_startup_readiness
from diagnostics.gui_event_log import log_exception


class TmdbNetworkProbeWorker(QThread):
    """Probe TMDb DNS and HTTPS reachability without a token."""

    completed = pyqtSignal(dict)

    def run(self) -> None:
        try:
            result = check_tmdb_network_available()
        except Exception as error:  # noqa: BLE001 - never strand the startup gate
            log_exception("startup.tmdb_network_probe.error", error)
            result = {
                "ok": False,
                "error": "network_unreachable",
                "details": str(error),
            }
        self.completed.emit(result)


class TmdbStartupValidateWorker(QThread):
    """Validate a bearer token and persist it on success."""

    completed = pyqtSignal(dict)

    def __init__(self, token: str, *, parent=None) -> None:
        super().__init__(parent)
        self._token = str(token or "").strip()

    def run(self) -> None:
        try:
            readiness = evaluate_tmdb_startup_readiness(self._token)
        except Exception as error:  # noqa: BLE001 - invalid input must stay inside the form
            log_exception("startup.tmdb_token_validation.error", error)
            self.completed.emit(
                {
                    "ready": False,
                    "error": "validation_failed",
                    "details": str(error),
                }
            )
            return
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

"""Background worker for candidate pool maintenance actions."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

from candidates import service as candidate_service
from diagnostics.gui_event_log import log_event, log_exception

ACTION_DEDUPE = "dedupe"
ACTION_PURGE_WATCHED = "purge_watched"
ACTION_CLEAR = "clear"
ACTION_IMPORT_JSON = "import_json"
ACTION_TMDB_BUILD = "tmdb_build"


class PoolMaintenanceWorker(QThread):
    """Run pool write operations off the UI thread."""

    finished_with_result = pyqtSignal(str, object)
    failed = pyqtSignal(str, str)

    def __init__(
        self,
        action: str,
        *,
        import_path: str | Path | None = None,
        build_kwargs: dict | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._action = action
        self._import_path = import_path
        self._build_kwargs = dict(build_kwargs or {})

    def run(self) -> None:
        log_event("pool.ops.worker.begin", action=self._action)
        try:
            result = self._execute()
        except Exception as error:  # noqa: BLE001 - surface to settings panel
            log_exception("pool.ops.worker.error", error, action=self._action)
            self.failed.emit(self._action, str(error))
            return
        log_event("pool.ops.worker.end", action=self._action, ok=bool(result.get("ok", True)))
        self.finished_with_result.emit(self._action, result)

    def _execute(self) -> dict:
        if self._action == ACTION_DEDUPE:
            return {
                "ok": True,
                "result": candidate_service.clean_common_pool_duplicates(),
            }
        if self._action == ACTION_PURGE_WATCHED:
            return {
                "ok": True,
                "result": candidate_service.purge_pool_dataset_title_matches(),
            }
        if self._action == ACTION_CLEAR:
            return {
                "ok": True,
                "result": candidate_service.clear_common_candidate_pool(),
            }
        if self._action == ACTION_IMPORT_JSON:
            import_path = Path(self._import_path or "")
            import_result = candidate_service.import_tmdb_result_to_pool(import_path)
            return {
                "ok": bool(import_result.get("ok")),
                "error": import_result.get("error"),
                "result": import_result,
            }
        if self._action == ACTION_TMDB_BUILD:
            build_result = candidate_service.build_and_save_tmdb_candidate_pool(
                is_test_run=False,
                **self._build_kwargs,
            )
            if build_result.get("ok") is False:
                return {
                    "ok": False,
                    "error": build_result.get("error") or "build failed",
                    "build_result": build_result,
                }
            json_path = build_result.get("json_path")
            criteria_name = build_result.get("criteria_name")
            import_result = candidate_service.import_tmdb_result_to_pool(
                json_path,
                criteria_name=criteria_name,
            )
            return {
                "ok": bool(import_result.get("ok")),
                "error": import_result.get("error"),
                "build_result": build_result,
                "import_result": import_result,
            }
        raise ValueError(f"unsupported pool maintenance action: {self._action}")

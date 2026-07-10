"""Pool maintenance controls for the desktop settings tab."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from candidates import service as candidate_service
from desktop.i18n import tr
from desktop.settings.pool_clear_dialog import PoolClearDialog
from desktop.settings.pool_ops_worker import (
    ACTION_CLEAR,
    ACTION_DEDUPE,
    ACTION_IMPORT_JSON,
    ACTION_PURGE_WATCHED,
    ACTION_TMDB_BUILD,
    PoolMaintenanceWorker,
)
from desktop.settings.tmdb_build_dialog import TmdbBuildDialog
from desktop.theme import TRANSPARENT_STYLE
from desktop.theme.scaling import layout_px

StatusCallback = Callable[[str, int], None]
WorkerFactory = Callable[..., PoolMaintenanceWorker]


class PoolOpsPanel(QWidget):
    """Read-only pool stats and maintenance actions."""

    poolChanged = pyqtSignal()

    def __init__(
        self,
        parent=None,
        *,
        on_status_message: StatusCallback | None = None,
        worker_factory: WorkerFactory | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("poolOpsPanel")
        self._on_status_message = on_status_message
        self._worker_factory = worker_factory or PoolMaintenanceWorker
        self._worker: PoolMaintenanceWorker | None = None
        self._progress_dialog: QProgressDialog | None = None
        self._stats_line_labels: list[QLabel] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(layout_px(10))

        section = QFrame()
        section.setObjectName("poolOpsSection")
        section_layout = QVBoxLayout(section)
        section_layout.setContentsMargins(
            layout_px(16),
            layout_px(14),
            layout_px(16),
            layout_px(14),
        )
        section_layout.setSpacing(layout_px(10))

        title = QLabel(tr("settings.pool.ops.title"))
        title.setObjectName("poolOpsTitle")
        section_layout.addWidget(title)

        self._summary_label = QLabel()
        self._summary_label.setObjectName("poolOpsStatsSummary")
        self._summary_label.setWordWrap(True)
        section_layout.addWidget(self._summary_label)

        self._warning_label = QLabel()
        self._warning_label.setObjectName("poolOpsStatsWarning")
        self._warning_label.setWordWrap(True)
        self._warning_label.hide()
        section_layout.addWidget(self._warning_label)

        self._stats_container = QWidget()
        self._stats_container.setObjectName("poolOpsStatsContainer")
        self._stats_container.setStyleSheet(TRANSPARENT_STYLE)
        self._stats_layout = QVBoxLayout(self._stats_container)
        self._stats_layout.setContentsMargins(0, 0, 0, 0)
        self._stats_layout.setSpacing(layout_px(4))
        section_layout.addWidget(self._stats_container)

        buttons_row = QHBoxLayout()
        buttons_row.setSpacing(layout_px(8))

        self._dedupe_button = self._make_action_button(
            "poolOpsDedupeButton",
            tr("settings.pool.ops.dedupe"),
            self._on_dedupe_clicked,
        )
        self._purge_button = self._make_action_button(
            "poolOpsPurgeButton",
            tr("settings.pool.ops.purge_watched"),
            self._on_purge_clicked,
        )
        self._clear_button = self._make_action_button(
            "poolOpsClearButton",
            tr("settings.pool.ops.clear"),
            self._on_clear_clicked,
        )
        buttons_row.addWidget(self._dedupe_button)
        buttons_row.addWidget(self._purge_button)
        buttons_row.addWidget(self._clear_button)
        section_layout.addLayout(buttons_row)

        import_build_row = QHBoxLayout()
        import_build_row.setSpacing(layout_px(8))
        self._import_button = self._make_action_button(
            "poolOpsImportButton",
            tr("settings.pool.ops.import_json"),
            self._on_import_clicked,
        )
        self._build_button = self._make_action_button(
            "poolOpsBuildButton",
            tr("settings.pool.ops.build"),
            self._on_build_clicked,
        )
        import_build_row.addWidget(self._import_button)
        import_build_row.addWidget(self._build_button)
        section_layout.addLayout(import_build_row)

        root.addWidget(section)
        self.refresh_stats()

    def _make_action_button(self, object_name: str, text: str, handler) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName(object_name)
        button.clicked.connect(handler)
        return button

    def refresh_stats(self) -> None:
        stats_view = candidate_service.get_pool_stats_view()
        stats = stats_view.get("stats") or {}
        self._summary_label.setText(stats_view.get("summary") or tr("settings.pool.ops.stats.empty"))

        duplicate_entries = int(stats.get("duplicate_entries") or 0)
        similar_duplicate_total = int(stats.get("similar_duplicate_total") or 0)
        cross_year_duplicate_total = int(stats.get("cross_year_duplicate_total") or 0)
        if duplicate_entries > 0 or similar_duplicate_total > 0 or cross_year_duplicate_total > 0:
            self._warning_label.setText(tr("settings.pool.ops.stats.duplicates_warning"))
            self._warning_label.show()
        else:
            self._warning_label.hide()

        for label in self._stats_line_labels:
            label.deleteLater()
        self._stats_line_labels.clear()

        for line in stats_view.get("lines") or []:
            label = QLabel(str(line))
            label.setObjectName("poolOpsStatsLine")
            label.setWordWrap(True)
            self._stats_layout.addWidget(label)
            self._stats_line_labels.append(label)

        self._set_busy(False)

    def _on_dedupe_clicked(self) -> None:
        stats_view = candidate_service.get_pool_stats_view()
        stats = stats_view.get("stats") or {}
        unique_total = int(stats.get("unique_total") or stats.get("storage_total") or 0)
        if unique_total == 0:
            self._show_status(tr("settings.pool.ops.dedupe.empty"), 5000)
            return

        duplicate_entries = int(stats.get("duplicate_entries") or 0)
        similar_duplicate_total = int(stats.get("similar_duplicate_total") or 0)
        cross_year_duplicate_total = int(stats.get("cross_year_duplicate_total") or 0)
        if duplicate_entries == 0 and similar_duplicate_total == 0 and cross_year_duplicate_total == 0:
            self._show_status(tr("settings.pool.ops.dedupe.nothing"), 5000)
            return

        answer = QMessageBox.question(
            self,
            tr("settings.pool.ops.dedupe.confirm.title"),
            tr("settings.pool.ops.dedupe.confirm.text"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._start_worker(ACTION_DEDUPE)

    def _on_purge_clicked(self) -> None:
        preview = candidate_service.get_pool_dataset_title_matches_view()
        if preview.get("is_empty"):
            self._show_status(tr("settings.pool.ops.purge.empty"), 5000)
            return

        match_count = int(preview.get("match_count") or 0)
        answer = QMessageBox.question(
            self,
            tr("settings.pool.ops.purge.confirm.title"),
            tr("settings.pool.ops.purge.confirm.text", count=match_count),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._start_worker(ACTION_PURGE_WATCHED)

    def _on_clear_clicked(self) -> None:
        stats_view = candidate_service.get_pool_stats_view()
        stats = stats_view.get("stats") or {}
        unique_total = int(stats.get("unique_total") or stats.get("storage_total") or 0)
        if unique_total == 0:
            self._show_status(tr("settings.pool.ops.clear.empty"), 5000)
            return

        dialog = PoolClearDialog(unique_total, parent=self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        self._start_worker(ACTION_CLEAR)

    def _on_import_clicked(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        path, _selected_filter = QFileDialog.getOpenFileName(
            self,
            tr("settings.pool.ops.import.dialog.title"),
            "",
            tr("settings.pool.ops.import.dialog.filter"),
        )
        if not path:
            return
        self._start_worker(ACTION_IMPORT_JSON, import_path=path)

    def _on_build_clicked(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        dialog = TmdbBuildDialog(parent=self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        self._start_worker(ACTION_TMDB_BUILD, build_kwargs=dialog.build_kwargs())

    def _start_worker(
        self,
        action: str,
        *,
        import_path: str | Path | None = None,
        build_kwargs: dict | None = None,
    ) -> None:
        if self._worker is not None and self._worker.isRunning():
            return

        self._set_busy(True)
        self._show_progress(action)
        worker = self._worker_factory(
            action,
            import_path=import_path,
            build_kwargs=build_kwargs,
            parent=self,
        )
        worker.finished_with_result.connect(self._on_worker_finished)
        worker.failed.connect(self._on_worker_failed)
        worker.finished.connect(worker.deleteLater)
        self._worker = worker
        worker.start()

    def _show_progress(self, action: str) -> None:
        if self._progress_dialog is not None:
            self._progress_dialog.close()
        title = tr("settings.pool.ops.progress.title")
        if action == ACTION_TMDB_BUILD:
            message = tr("settings.pool.ops.progress.build")
        elif action == ACTION_IMPORT_JSON:
            message = tr("settings.pool.ops.progress.import")
        else:
            message = tr("settings.pool.ops.progress.maintenance")
        dialog = QProgressDialog(message, "", 0, 0, self)
        dialog.setWindowTitle(title)
        dialog.setWindowModality(Qt.WindowModality.WindowModal)
        dialog.setMinimumDuration(0)
        dialog.setCancelButton(None)
        dialog.setAutoClose(False)
        dialog.setAutoReset(False)
        dialog.show()
        self._progress_dialog = dialog

    def _hide_progress(self) -> None:
        if self._progress_dialog is not None:
            self._progress_dialog.close()
            self._progress_dialog = None

    def _on_worker_finished(self, action: str, payload: dict) -> None:
        self._hide_progress()
        self._worker = None
        self.refresh_stats()

        if payload.get("ok") is False:
            error = payload.get("error") or tr("settings.pool.ops.error.generic")
            self._show_status(tr("settings.pool.ops.error.action", error=error), 8000)
            return

        self.poolChanged.emit()
        self._show_status(self._success_message(action, payload), 8000)

    def _on_worker_failed(self, action: str, message: str) -> None:
        del action
        self._hide_progress()
        self._worker = None
        self._set_busy(False)
        self._show_status(tr("settings.pool.ops.error.action", error=message), 8000)

    def _success_message(self, action: str, payload: dict) -> str:
        result = payload.get("result") or {}
        if action == ACTION_DEDUPE:
            removed_total = int(result.get("removed_total") or 0)
            return tr("settings.pool.ops.dedupe.done", count=removed_total)
        if action == ACTION_PURGE_WATCHED:
            removed = int(result.get("removed_dataset_title_matches") or 0)
            return tr("settings.pool.ops.purge.done", count=removed)
        if action == ACTION_CLEAR:
            cleared = int(result.get("cleared") or 0)
            return tr("settings.pool.ops.clear.done", count=cleared)
        if action == ACTION_IMPORT_JSON:
            stats = result.get("stats") or {}
            added = int(stats.get("added") or 0)
            updated = int(stats.get("updated") or 0)
            return tr("settings.pool.ops.import.done", added=added, updated=updated)
        if action == ACTION_TMDB_BUILD:
            import_result = payload.get("import_result") or {}
            stats = import_result.get("stats") or {}
            added = int(stats.get("added") or 0)
            updated = int(stats.get("updated") or 0)
            return tr("settings.pool.ops.build.done", added=added, updated=updated)
        return tr("settings.pool.ops.done")

    def _set_busy(self, busy: bool) -> None:
        for button in (
            self._dedupe_button,
            self._purge_button,
            self._clear_button,
            self._import_button,
            self._build_button,
        ):
            button.setEnabled(not busy)

    def _show_status(self, message: str, timeout_ms: int) -> None:
        if self._on_status_message is not None:
            self._on_status_message(message, timeout_ms)

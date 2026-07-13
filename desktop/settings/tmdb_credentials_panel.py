"""TMDb credential lifecycle controls for the Settings tab."""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from apis import tmdb_api
from desktop.i18n import tr
from desktop.startup.worker import TmdbStartupValidateWorker
from desktop.theme.scaling import layout_px


class TmdbCredentialsPanel(QWidget):
    """Replace or remove local TMDb credentials without exposing their value."""

    credentialsChanged = pyqtSignal(bool)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("tmdbCredentialsPanel")
        self._worker: TmdbStartupValidateWorker | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        section = QFrame()
        section.setObjectName("tmdbCredentialsSection")
        layout = QVBoxLayout(section)
        layout.setContentsMargins(layout_px(16), layout_px(14), layout_px(16), layout_px(14))
        layout.setSpacing(layout_px(10))

        title = QLabel(tr("settings.tmdb.title"))
        title.setObjectName("tmdbCredentialsTitle")
        layout.addWidget(title)
        hint = QLabel(tr("settings.tmdb.hint"))
        hint.setObjectName("tmdbCredentialsHint")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self._token_input = QLineEdit()
        self._token_input.setObjectName("tmdbCredentialInput")
        self._token_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._token_input.setPlaceholderText(tr("settings.tmdb.placeholder"))
        self._token_input.textChanged.connect(self._sync_actions)
        self._token_input.returnPressed.connect(self._save)
        layout.addWidget(self._token_input)

        self._status = QLabel("")
        self._status.setObjectName("tmdbCredentialsStatus")
        self._status.setWordWrap(True)
        layout.addWidget(self._status)

        actions = QHBoxLayout()
        actions.addStretch(1)
        self._delete_button = QPushButton(tr("settings.tmdb.delete"))
        self._delete_button.setObjectName("deleteTmdbCredentialsButton")
        self._save_button = QPushButton(tr("settings.tmdb.save"))
        self._save_button.setObjectName("saveTmdbCredentialsButton")
        self._delete_button.clicked.connect(self._delete)
        self._save_button.clicked.connect(self._save)
        actions.addWidget(self._delete_button)
        actions.addWidget(self._save_button)
        layout.addLayout(actions)
        root.addWidget(section)
        self.refresh_state()

    def refresh_state(self) -> None:
        available = tmdb_api.has_tmdb_credentials()
        self._status.setText(
            tr("settings.tmdb.status.saved")
            if available
            else tr("settings.tmdb.status.missing")
        )
        self._delete_button.setEnabled(available and self._worker is None)
        self._sync_actions()

    def _sync_actions(self) -> None:
        busy = self._worker is not None
        self._token_input.setEnabled(not busy)
        self._save_button.setEnabled(not busy and bool(self._token_input.text().strip()))

    def _save(self) -> None:
        token = self._token_input.text().strip()
        if self._worker is not None or not token:
            return
        self._status.setText(tr("settings.tmdb.status.checking"))
        worker = TmdbStartupValidateWorker(token, parent=self)
        worker.completed.connect(self._on_validation_finished)
        worker.finished.connect(worker.deleteLater)
        self._worker = worker
        self._sync_actions()
        self._delete_button.setEnabled(False)
        worker.start()

    def _on_validation_finished(self, result: dict) -> None:
        self._worker = None
        if result.get("ready") is True:
            self._token_input.clear()
            self._status.setText(tr("settings.tmdb.status.saved"))
            self._delete_button.setEnabled(True)
            self.credentialsChanged.emit(True)
        else:
            error = str(result.get("error") or "invalid_token")
            key = {
                "dns_blocked": "settings.tmdb.error.dns_blocked",
                "network_unreachable": "settings.tmdb.error.offline",
                "save_failed": "settings.tmdb.error.save_failed",
            }.get(error, "settings.tmdb.error.invalid")
            self._status.setText(tr(key))
            self._delete_button.setEnabled(tmdb_api.has_tmdb_credentials())
        self._sync_actions()

    def _delete(self) -> None:
        if self._worker is not None:
            return
        answer = QMessageBox.question(
            self,
            tr("settings.tmdb.delete.confirm.title"),
            tr("settings.tmdb.delete.confirm.text"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        tmdb_api.delete_tmdb_credentials()
        self._token_input.clear()
        self._status.setText(tr("settings.tmdb.status.deleted"))
        self._delete_button.setEnabled(False)
        self.credentialsChanged.emit(False)

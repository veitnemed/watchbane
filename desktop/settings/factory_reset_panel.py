"""Destructive application reset that keeps only TMDb credentials."""

from __future__ import annotations

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.use_cases import profile_management
from desktop.i18n import tr
from desktop.theme.scaling import layout_px


class FactoryResetPanel(QWidget):
    """Schedule a no-backup reset and return to first-launch onboarding."""

    CONFIRMATION_TEXT = "DELETE ALL"

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("factoryResetPanel")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        section = QFrame()
        section.setObjectName("factoryResetSection")
        layout = QVBoxLayout(section)
        layout.setContentsMargins(
            layout_px(16),
            layout_px(14),
            layout_px(16),
            layout_px(14),
        )
        layout.setSpacing(layout_px(10))

        title = QLabel(tr("settings.factory_reset.title"))
        title.setObjectName("factoryResetTitle")
        layout.addWidget(title)

        description = QLabel(tr("settings.factory_reset.description"))
        description.setObjectName("factoryResetDescription")
        description.setWordWrap(True)
        layout.addWidget(description)

        self._reset_button = QPushButton(tr("settings.factory_reset.action"))
        self._reset_button.setObjectName("factoryResetButton")
        self._reset_button.clicked.connect(self._request_reset)
        layout.addWidget(self._reset_button)
        root.addWidget(section)

    def _request_reset(self) -> None:
        answer = QMessageBox.warning(
            self,
            tr("settings.factory_reset.confirm.title"),
            tr("settings.factory_reset.confirm.text"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        confirmation, accepted = QInputDialog.getText(
            self,
            tr("settings.factory_reset.typed.title"),
            tr(
                "settings.factory_reset.typed.text",
                token=self.CONFIRMATION_TEXT,
            ),
        )
        if accepted is False:
            return
        if confirmation.strip() != self.CONFIRMATION_TEXT:
            QMessageBox.warning(
                self,
                tr("settings.factory_reset.typed.invalid.title"),
                tr("settings.factory_reset.typed.invalid.text"),
            )
            return
        try:
            profile_management.request_factory_reset_keep_token()
        except (OSError, ValueError, RuntimeError) as error:
            QMessageBox.critical(
                self,
                tr("settings.factory_reset.error.title"),
                tr("settings.factory_reset.error.text", error=str(error)),
            )
            return

        self._reset_button.setEnabled(False)
        QMessageBox.information(
            self,
            tr("settings.factory_reset.scheduled.title"),
            tr("settings.factory_reset.scheduled.text"),
        )
        QTimer.singleShot(0, QApplication.quit)

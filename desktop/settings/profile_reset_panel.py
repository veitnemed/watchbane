"""Full active-profile reset controls."""

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

from desktop.i18n import get_interface_language, tr
from desktop.theme.scaling import layout_px
from storage import profile_reset, profiles


class ProfileResetPanel(QWidget):
    """Schedule a backed-up reset and restart into profile selection."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("profileResetPanel")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        section = QFrame()
        section.setObjectName("profileResetSection")
        layout = QVBoxLayout(section)
        layout.setContentsMargins(
            layout_px(16),
            layout_px(14),
            layout_px(16),
            layout_px(14),
        )
        layout.setSpacing(layout_px(10))

        title = QLabel(tr("settings.profile.reset.title"))
        title.setObjectName("profileResetTitle")
        layout.addWidget(title)

        self._description = QLabel()
        self._description.setObjectName("profileResetDescription")
        self._description.setWordWrap(True)
        layout.addWidget(self._description)

        self._reset_button = QPushButton(tr("settings.profile.reset.action"))
        self._reset_button.setObjectName("profileResetButton")
        self._reset_button.clicked.connect(self._request_reset)
        layout.addWidget(self._reset_button)
        root.addWidget(section)
        self.refresh_state()

    def refresh_state(self) -> None:
        self._description.setText(
            tr(
                "settings.profile.reset.description",
                profile=profiles.get_active_profile(),
            )
        )

    def _request_reset(self) -> None:
        answer = QMessageBox.warning(
            self,
            tr("settings.profile.reset.confirm.title"),
            tr("settings.profile.reset.confirm.text"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        expected = "RESET" if get_interface_language() == "en" else "СБРОСИТЬ"
        confirmation, accepted = QInputDialog.getText(
            self,
            tr("settings.profile.reset.typed.title"),
            tr("settings.profile.reset.typed.text", token=expected),
        )
        if accepted is False:
            return
        if confirmation.strip() != expected:
            QMessageBox.warning(
                self,
                tr("settings.profile.reset.typed.invalid.title"),
                tr("settings.profile.reset.typed.invalid.text"),
            )
            return
        try:
            profile_reset.request_full_profile_reset()
        except (OSError, ValueError, profiles.ProfileError) as error:
            QMessageBox.critical(
                self,
                tr("settings.profile.reset.error.title"),
                tr("settings.profile.reset.error.text", error=str(error)),
            )
            return

        self._reset_button.setEnabled(False)
        QMessageBox.information(
            self,
            tr("settings.profile.reset.scheduled.title"),
            tr("settings.profile.reset.scheduled.text"),
        )
        QTimer.singleShot(0, QApplication.quit)

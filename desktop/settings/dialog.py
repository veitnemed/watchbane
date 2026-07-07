"""Desktop settings dialog."""

from __future__ import annotations

from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QVBoxLayout

from desktop.i18n import tr
from desktop.settings.ui_scale_control import UI_SCALE_RESTART_MESSAGE, UiScaleControlPanel
from desktop.theme.scaling import layout_px
from desktop.theme.shell_layout import SETTINGS_DIALOG_MIN_WIDTH_PX


class SettingsDialog(QDialog):
    """Small settings dialog for desktop application preferences."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("settings.title"))
        self.setObjectName("settingsDialog")

        root = QVBoxLayout(self)
        root.setContentsMargins(
            layout_px(18),
            layout_px(18),
            layout_px(18),
            layout_px(18),
        )
        root.setSpacing(layout_px(12))

        self._scale_panel = UiScaleControlPanel(self)
        root.addWidget(self._scale_panel)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close_button = buttons.button(QDialogButtonBox.StandardButton.Close)
        close_button.setText(tr("settings.close"))
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self.setMinimumWidth(SETTINGS_DIALOG_MIN_WIDTH_PX)

    @property
    def restart_message(self) -> str:
        return self._scale_panel.restart_message

    @property
    def settingsSaved(self):
        return self._scale_panel.settingsSaved

    def selected_ui_scale(self) -> float:
        return self._scale_panel.selected_ui_scale()

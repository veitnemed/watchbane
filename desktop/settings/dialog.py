"""Desktop settings dialog."""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from desktop.settings.app_settings import APP_UI_SCALE_PRESETS, AppSettings, load_app_settings, save_app_settings

UI_SCALE_RESTART_MESSAGE = "Масштаб интерфейса применится после перезапуска приложения."
UI_SCALE_OPTIONS = tuple((f"{round(value * 100):g}%", value) for value in APP_UI_SCALE_PRESETS)


class SettingsDialog(QDialog):
    """Small settings dialog for desktop application preferences."""

    settingsSaved = pyqtSignal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Настройки")
        self.setObjectName("settingsDialog")
        self._restart_message = ""

        settings = load_app_settings()

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)

        section = QFrame()
        section.setObjectName("settingsInterfaceSection")
        section_layout = QVBoxLayout(section)
        section_layout.setContentsMargins(0, 0, 0, 0)
        section_layout.setSpacing(10)

        title = QLabel("Интерфейс")
        title.setObjectName("settingsSectionTitle")
        section_layout.addWidget(title)

        scale_row = QHBoxLayout()
        scale_row.setContentsMargins(0, 0, 0, 0)
        scale_row.setSpacing(10)

        scale_label = QLabel("Масштаб интерфейса")
        scale_label.setObjectName("uiScaleLabel")
        self._scale_combo = QComboBox()
        self._scale_combo.setObjectName("uiScaleComboBox")
        for label, value in UI_SCALE_OPTIONS:
            self._scale_combo.addItem(label, value)
        self._select_scale(settings.ui_scale)

        scale_row.addWidget(scale_label)
        scale_row.addStretch(1)
        scale_row.addWidget(self._scale_combo)
        section_layout.addLayout(scale_row)

        self._message_label = QLabel("")
        self._message_label.setObjectName("settingsRestartMessage")
        self._message_label.setWordWrap(True)
        self._message_label.setVisible(False)
        section_layout.addWidget(self._message_label)

        root.addWidget(section)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        self._save_button = QPushButton("Сохранить")
        self._save_button.setObjectName("saveSettingsButton")
        self._reset_button = QPushButton("Сбросить 100%")
        self._reset_button.setObjectName("resetUiScaleButton")
        buttons.addButton(self._reset_button, QDialogButtonBox.ButtonRole.ResetRole)
        buttons.addButton(self._save_button, QDialogButtonBox.ButtonRole.AcceptRole)
        cancel_button = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        cancel_button.setText("Отмена")

        self._save_button.clicked.connect(self._save)
        self._reset_button.clicked.connect(self._reset_scale)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self.setMinimumWidth(360)

    @property
    def restart_message(self) -> str:
        return self._restart_message

    def selected_ui_scale(self) -> float:
        value = self._scale_combo.currentData()
        return float(value if value is not None else 1.0)

    def _select_scale(self, value: float) -> None:
        closest_index = 0
        closest_distance = float("inf")
        for index, (_, option_value) in enumerate(UI_SCALE_OPTIONS):
            distance = abs(float(value) - option_value)
            if distance < closest_distance:
                closest_index = index
                closest_distance = distance
        self._scale_combo.setCurrentIndex(closest_index)

    def _reset_scale(self) -> None:
        self._select_scale(1.0)

    def _save(self) -> None:
        save_app_settings(AppSettings(ui_scale=self.selected_ui_scale()))
        self._restart_message = UI_SCALE_RESTART_MESSAGE
        self._message_label.setText(UI_SCALE_RESTART_MESSAGE)
        self._message_label.setVisible(True)
        self.settingsSaved.emit(UI_SCALE_RESTART_MESSAGE)

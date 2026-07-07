"""Shared UI scale slider control for settings tab and dialog."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QSlider, QVBoxLayout, QWidget

from desktop.settings.app_settings import (
    APP_UI_SCALE_DEFAULT,
    APP_UI_SCALE_MAX,
    APP_UI_SCALE_MIN,
    AppSettings,
    load_app_settings,
    normalize_ui_scale,
    save_app_settings,
)
from desktop.theme.scaling import layout_px

UI_SCALE_RESTART_MESSAGE = "Масштаб интерфейса применится после перезапуска приложения."
UI_SCALE_SLIDER_MIN_PERCENT = int(APP_UI_SCALE_MIN * 100)
UI_SCALE_SLIDER_MAX_PERCENT = int(APP_UI_SCALE_MAX * 100)


def format_ui_scale_label(scale: float) -> str:
    return f"{round(normalize_ui_scale(scale) * 100):g}%"


def ui_scale_from_slider_percent(percent: int) -> float:
    return normalize_ui_scale(percent / 100.0)


def slider_percent_from_ui_scale(scale: float) -> int:
    normalized = normalize_ui_scale(scale)
    return max(
        UI_SCALE_SLIDER_MIN_PERCENT,
        min(UI_SCALE_SLIDER_MAX_PERCENT, int(round(normalized * 100))),
    )


class UiScaleControlPanel(QWidget):
    """Slider-based UI scale control with save/reset actions."""

    settingsSaved = pyqtSignal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("uiScaleControlPanel")
        self._restart_message = ""

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(layout_px(10))

        section = QFrame()
        section.setObjectName("settingsInterfaceSection")
        section_layout = QVBoxLayout(section)
        section_layout.setContentsMargins(
            layout_px(16),
            layout_px(14),
            layout_px(16),
            layout_px(14),
        )
        section_layout.setSpacing(layout_px(12))

        title = QLabel("Интерфейс")
        title.setObjectName("settingsSectionTitle")
        section_layout.addWidget(title)

        scale_label = QLabel("Масштаб интерфейса")
        scale_label.setObjectName("uiScaleLabel")
        section_layout.addWidget(scale_label)

        slider_row = QHBoxLayout()
        slider_row.setContentsMargins(0, 0, 0, 0)
        slider_row.setSpacing(layout_px(10))

        self._scale_slider = QSlider(Qt.Orientation.Horizontal)
        self._scale_slider.setObjectName("uiScaleSlider")
        self._scale_slider.setMinimum(UI_SCALE_SLIDER_MIN_PERCENT)
        self._scale_slider.setMaximum(UI_SCALE_SLIDER_MAX_PERCENT)
        self._scale_slider.setSingleStep(1)
        self._scale_slider.setPageStep(5)
        self._scale_slider.valueChanged.connect(self._update_value_label)

        self._value_label = QLabel()
        self._value_label.setObjectName("uiScaleValueLabel")
        self._value_label.setMinimumWidth(layout_px(56))
        self._value_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )

        slider_row.addWidget(self._scale_slider, stretch=1)
        slider_row.addWidget(self._value_label)
        section_layout.addLayout(slider_row)

        self._message_label = QLabel("")
        self._message_label.setObjectName("settingsRestartMessage")
        self._message_label.setWordWrap(True)
        self._message_label.setVisible(False)
        section_layout.addWidget(self._message_label)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(layout_px(10))
        self._reset_button = QPushButton("Сбросить 100%")
        self._reset_button.setObjectName("resetUiScaleButton")
        self._save_button = QPushButton("Сохранить")
        self._save_button.setObjectName("saveSettingsButton")
        actions.addStretch(1)
        actions.addWidget(self._reset_button)
        actions.addWidget(self._save_button)
        section_layout.addLayout(actions)

        root.addWidget(section)

        self._reset_button.clicked.connect(self._reset_scale)
        self._save_button.clicked.connect(self._save)

        self.load_from_settings()

    @property
    def restart_message(self) -> str:
        return self._restart_message

    def selected_ui_scale(self) -> float:
        return ui_scale_from_slider_percent(self._scale_slider.value())

    def load_from_settings(self) -> None:
        self.set_ui_scale(load_app_settings().ui_scale)

    def set_ui_scale(self, scale: float) -> None:
        self._scale_slider.blockSignals(True)
        self._scale_slider.setValue(slider_percent_from_ui_scale(scale))
        self._scale_slider.blockSignals(False)
        self._update_value_label(self._scale_slider.value())

    def _update_value_label(self, percent: int) -> None:
        self._value_label.setText(format_ui_scale_label(ui_scale_from_slider_percent(percent)))

    def _reset_scale(self) -> None:
        self.set_ui_scale(APP_UI_SCALE_DEFAULT)

    def _save(self) -> None:
        save_app_settings(AppSettings(ui_scale=self.selected_ui_scale()))
        self._restart_message = UI_SCALE_RESTART_MESSAGE
        self._message_label.setText(UI_SCALE_RESTART_MESSAGE)
        self._message_label.setVisible(True)
        self.settingsSaved.emit(UI_SCALE_RESTART_MESSAGE)

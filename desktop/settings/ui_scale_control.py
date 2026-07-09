"""Shared UI scale slider control for settings tab and dialog."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QCheckBox, QComboBox, QFrame, QHBoxLayout, QLabel, QPushButton, QSlider, QVBoxLayout, QWidget

from desktop.settings.app_settings import (
    APP_LANGUAGE_SUPPORTED,
    APP_UI_SCALE_DEFAULT,
    APP_UI_SCALE_MAX,
    APP_UI_SCALE_MIN,
    AppSettings,
    load_app_settings,
    normalize_auto_pool_refill,
    normalize_language,
    normalize_ui_scale,
    save_app_settings,
)
from desktop.i18n import TRANSLATIONS, tr
from desktop.theme.scaling import layout_px

UI_SCALE_RESTART_MESSAGE = TRANSLATIONS["ru"]["settings.restart_message"]
UI_SCALE_SLIDER_MIN_PERCENT = int(APP_UI_SCALE_MIN * 100)
UI_SCALE_SLIDER_MAX_PERCENT = int(APP_UI_SCALE_MAX * 100)
LANGUAGE_OPTIONS = (
    ("settings.language.ru", "ru"),
    ("settings.language.en", "en"),
)


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

        title = QLabel(tr("settings.interface.section"))
        title.setObjectName("settingsSectionTitle")
        section_layout.addWidget(title)

        scale_label = QLabel(tr("settings.scale.title"))
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

        language_title = QLabel(tr("settings.language.title"))
        language_title.setObjectName("settingsLanguageTitle")
        section_layout.addWidget(language_title)

        interface_language_label = QLabel(tr("settings.language.interface"))
        interface_language_label.setObjectName("interfaceLanguageLabel")
        section_layout.addWidget(interface_language_label)

        self._interface_language_combo = QComboBox()
        self._interface_language_combo.setObjectName("interfaceLanguageCombo")
        self._populate_language_combo(self._interface_language_combo)
        section_layout.addWidget(self._interface_language_combo)

        interface_language_hint = QLabel(tr("settings.language.interface_hint"))
        interface_language_hint.setObjectName("interfaceLanguageHint")
        interface_language_hint.setWordWrap(True)
        section_layout.addWidget(interface_language_hint)

        data_language_label = QLabel(tr("settings.language.data"))
        data_language_label.setObjectName("dataLanguageLabel")
        section_layout.addWidget(data_language_label)

        self._data_language_combo = QComboBox()
        self._data_language_combo.setObjectName("dataLanguageCombo")
        self._populate_language_combo(self._data_language_combo)
        section_layout.addWidget(self._data_language_combo)

        data_language_hint = QLabel(tr("settings.language.data_hint"))
        data_language_hint.setObjectName("dataLanguageHint")
        data_language_hint.setWordWrap(True)
        section_layout.addWidget(data_language_hint)

        pool_title = QLabel(tr("settings.pool.title"))
        pool_title.setObjectName("settingsPoolTitle")
        section_layout.addWidget(pool_title)

        self._auto_refill_checkbox = QCheckBox(tr("settings.pool.auto_refill"))
        self._auto_refill_checkbox.setObjectName("autoPoolRefillCheckbox")
        section_layout.addWidget(self._auto_refill_checkbox)

        auto_refill_hint = QLabel(tr("settings.pool.auto_refill_hint"))
        auto_refill_hint.setObjectName("autoPoolRefillHint")
        auto_refill_hint.setWordWrap(True)
        section_layout.addWidget(auto_refill_hint)

        self._message_label = QLabel("")
        self._message_label.setObjectName("settingsRestartMessage")
        self._message_label.setWordWrap(True)
        self._message_label.setVisible(False)
        section_layout.addWidget(self._message_label)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(layout_px(10))
        self._reset_button = QPushButton(tr("settings.scale.reset_100"))
        self._reset_button.setObjectName("resetUiScaleButton")
        self._save_button = QPushButton(tr("settings.save"))
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

    def selected_interface_language(self) -> str:
        return normalize_language(self._interface_language_combo.currentData())

    def selected_data_language(self) -> str:
        return normalize_language(self._data_language_combo.currentData())

    def selected_auto_pool_refill(self) -> bool:
        return normalize_auto_pool_refill(self._auto_refill_checkbox.isChecked())

    def load_from_settings(self) -> None:
        settings = load_app_settings()
        self.set_ui_scale(settings.ui_scale)
        self._set_language_combo(self._interface_language_combo, settings.interface_language)
        self._set_language_combo(self._data_language_combo, settings.data_language)
        self._auto_refill_checkbox.setChecked(normalize_auto_pool_refill(settings.auto_pool_refill))

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
        previous_settings = load_app_settings()
        next_settings = AppSettings(
            ui_scale=self.selected_ui_scale(),
            interface_language=self.selected_interface_language(),
            data_language=self.selected_data_language(),
            auto_pool_refill=self.selected_auto_pool_refill(),
        )
        message = self._settings_saved_message(previous_settings, next_settings)
        save_app_settings(
            next_settings
        )
        self._restart_message = message
        self._message_label.setText(message)
        self._message_label.setVisible(True)
        self.settingsSaved.emit(message)

    def _settings_saved_message(self, previous: AppSettings, current: AppSettings) -> str:
        interface_changed = (
            normalize_language(previous.interface_language)
            != normalize_language(current.interface_language)
        )
        data_changed = (
            normalize_language(previous.data_language)
            != normalize_language(current.data_language)
        )
        if interface_changed and data_changed:
            return tr("settings.restart_message.both")
        if data_changed:
            return tr("settings.restart_message.data")
        return tr("settings.restart_message")

    def _populate_language_combo(self, combo: QComboBox) -> None:
        for label_key, language in LANGUAGE_OPTIONS:
            if language in APP_LANGUAGE_SUPPORTED:
                combo.addItem(tr(label_key), language)

    def _set_language_combo(self, combo: QComboBox, language: str) -> None:
        normalized = normalize_language(language)
        index = combo.findData(normalized)
        combo.setCurrentIndex(index if index >= 0 else 0)

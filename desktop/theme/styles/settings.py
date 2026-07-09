"""QSS for the settings tab and settings dialog controls."""

from __future__ import annotations

from desktop.theme.tokens import *  # noqa: F403


def build_settings_style() -> str:
    """Return stylesheet for settings surfaces."""
    return f"""
QWidget#settingsTabRoot,
QDialog#settingsDialog {{
    font-size: {font_px(FONT_BASE)}px;
}}
QLabel#settingsTabTitle {{
    background: transparent;
    color: {COLOR_TEXT};
    font-size: {font_px(FONT_TITLE)}px;
    font-weight: 700;
}}
QWidget#uiScaleControlPanel {{
    background: transparent;
}}
QFrame#settingsInterfaceSection {{
    background-color: {COLOR_CARD};
    border: 1px solid {COLOR_BORDER};
    border-radius: {px(RADIUS_CARD)}px;
}}
QLabel#settingsSectionTitle {{
    background: transparent;
    color: {COLOR_TEXT};
    font-size: {font_px(FONT_SECTION)}px;
    font-weight: 700;
}}
QLabel#uiScaleLabel {{
    background: transparent;
    color: {COLOR_TEXT_SECONDARY};
    font-size: {font_px(FONT_BASE)}px;
    font-weight: 600;
}}
QLabel#settingsLanguageTitle {{
    background: transparent;
    color: {COLOR_TEXT};
    font-size: {font_px(FONT_SECTION)}px;
    font-weight: 700;
    margin-top: {px(6)}px;
}}
QLabel#interfaceLanguageLabel,
QLabel#dataLanguageLabel {{
    background: transparent;
    color: {COLOR_TEXT_SECONDARY};
    font-size: {font_px(FONT_BASE)}px;
    font-weight: 600;
}}
QLabel#interfaceLanguageHint,
QLabel#dataLanguageHint,
QLabel#autoPoolRefillHint,
QLabel#ftsSearchHint {{
    background: transparent;
    color: {COLOR_TEXT_SECONDARY};
    font-size: {font_px(FONT_SMALL)}px;
}}
QLabel#settingsPoolTitle {{
    background: transparent;
    color: {COLOR_TEXT};
    font-size: {font_px(FONT_SECTION)}px;
    font-weight: 700;
    margin-top: {px(6)}px;
}}
QCheckBox#autoPoolRefillCheckbox,
QCheckBox#ftsSearchCheckbox {{
    background: transparent;
    color: {COLOR_TEXT_SECONDARY};
    font-size: {font_px(FONT_BASE)}px;
    font-weight: 600;
    spacing: {px(8)}px;
    min-height: {px(28)}px;
    padding: 0;
}}
QCheckBox#autoPoolRefillCheckbox::indicator,
QCheckBox#ftsSearchCheckbox::indicator {{
    width: {px(18)}px;
    height: {px(18)}px;
}}
QComboBox#interfaceLanguageCombo,
QComboBox#dataLanguageCombo {{
    background-color: {COLOR_CARD_ALT};
    border: 1px solid {COLOR_BORDER};
    border-radius: {px(RADIUS_BUTTON_SMALL)}px;
    color: {COLOR_TEXT};
    font-size: {font_px(FONT_BASE)}px;
    padding: {px(6)}px {px(10)}px;
    min-height: {px(28)}px;
}}
QComboBox#interfaceLanguageCombo:hover,
QComboBox#dataLanguageCombo:hover {{
    border-color: {COLOR_BORDER_HOVER};
}}
QLabel#uiScaleValueLabel {{
    background: transparent;
    color: {COLOR_TEXT};
    font-size: {font_px(FONT_BASE + 1)}px;
    font-weight: 700;
}}
QLabel#settingsRestartMessage {{
    background: transparent;
    color: {COLOR_TEXT_SECONDARY};
    font-size: {font_px(FONT_SMALL)}px;
}}
QPushButton#resetUiScaleButton,
QPushButton#saveSettingsButton {{
    background-color: {COLOR_CARD_ALT};
    border: 1px solid {COLOR_BORDER};
    border-radius: {px(RADIUS_BUTTON_SMALL)}px;
    color: {COLOR_TEXT};
    font-size: {font_px(FONT_BASE)}px;
    font-weight: 600;
    padding: {px(6)}px {px(12)}px;
    min-height: {px(28)}px;
}}
QPushButton#resetUiScaleButton:hover,
QPushButton#saveSettingsButton:hover {{
    background-color: {COLOR_CONTROL_HOVER};
    border-color: {COLOR_BORDER_HOVER};
}}
"""

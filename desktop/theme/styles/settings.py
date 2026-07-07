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

"""QSS for the TMDb startup gate."""

from __future__ import annotations

from desktop.theme.tokens import *  # noqa: F403


def build_startup_gate_style() -> str:
    return f"""
QWidget#startupGateRoot {{
    background-color: {COLOR_BG};
}}
QFrame#startupGateCard {{
    background-color: {COLOR_CARD};
    border: 1px solid {COLOR_BORDER};
    border-radius: {px(RADIUS_CARD)}px;
    max-width: {px(660)}px;
}}
QLabel#startupGateTitle,
QLabel#startupGateSubtitle,
QLabel#startupGateTokenLabel,
QLabel#startupGateHint,
QLabel#startupGateError {{
    background: transparent;
    border: none;
}}
QLabel#startupGateTitle {{
    color: {COLOR_TEXT};
    font-size: {font_px(FONT_DIALOG_TITLE)}px;
    font-weight: 600;
}}
QLabel#startupGateSubtitle {{
    color: {COLOR_TEXT_SECONDARY};
    font-size: {font_px(FONT_BASE)}px;
}}
QLabel#startupGateNetworkStatus {{
    color: {COLOR_TEXT_SOFT};
    background-color: {COLOR_CARD_ALT};
    border: 1px solid {COLOR_BORDER};
    border-radius: {px(RADIUS_INPUT)}px;
    padding: {px(9)}px {px(14)}px;
}}
QLabel#startupGateTokenLabel {{
    color: {COLOR_TEXT};
    font-size: {font_px(FONT_BASE)}px;
}}
QLabel#startupGateHint {{
    color: {COLOR_TEXT_MUTED};
}}
QLabel#startupGateError {{
    color: {COLOR_TEXT_SECONDARY};
}}
QLineEdit#startupTokenInput {{
    background-color: {COLOR_SURFACE};
    border: 1px solid {COLOR_BORDER};
    border-radius: {px(RADIUS_INPUT)}px;
    padding: {px(INPUT_PADDING_Y + 1)}px {px(INPUT_PADDING_X)}px;
    color: {COLOR_TEXT};
    font-size: {font_px(FONT_BASE)}px;
    selection-background-color: {COLOR_ACCENT_SOFT};
}}
QLineEdit#startupTokenInput:focus {{
    border: 1px solid {COLOR_ACCENT};
}}
QPushButton#startupPrimaryButton {{
    background-color: {COLOR_ACCENT};
    color: {COLOR_TEXT_INVERTED};
    border: none;
    border-radius: {px(RADIUS_BUTTON)}px;
    padding: {px(9)}px {px(24)}px;
    font-size: {font_px(FONT_BASE)}px;
    font-weight: 600;
}}
QPushButton#startupPrimaryButton:hover:enabled {{
    background-color: {COLOR_ACCENT_HOVER};
}}
QPushButton#startupPrimaryButton:disabled {{
    background-color: {COLOR_CARD_ELEVATED};
    color: {COLOR_TEXT_MUTED};
}}
"""

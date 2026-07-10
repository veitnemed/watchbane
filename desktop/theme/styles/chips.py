"""QSS for genre/country chip selectors and expand toggles."""

from __future__ import annotations

from desktop.theme.tokens import *  # noqa: F403


def build_chip_selector_style() -> str:
    """Return stylesheet for collapsible chip selectors."""
    return f"""
QPushButton#genreFilterChip {{
    background-color: {COLOR_CARD_ALT};
    border: 1px solid {COLOR_BORDER};
    border-radius: {px(RADIUS_CHIP)}px;
    color: {COLOR_TEXT_CHIP};
    font-size: {font_px(FONT_BASE)}px;
    font-weight: 500;
    padding: {px(7)}px {px(12)}px;
    min-height: {px(34)}px;
}}
QPushButton#genreFilterChip:hover {{
    background-color: {COLOR_HOVER};
    border-color: {COLOR_BORDER_HOVER};
}}
QPushButton#genreFilterChip:checked {{
    background-color: {COLOR_ACCENT_SOFT};
    border-color: {COLOR_ACCENT};
    color: {COLOR_ACCENT_HOVER};
}}
QPushButton#genreFilterChip:disabled {{
    background-color: {COLOR_CARD};
    border-color: {COLOR_DIVIDER};
    color: {COLOR_TEXT_MUTED};
}}
QPushButton#genreChipClear {{
    background: transparent;
    border: none;
    color: {COLOR_TEXT_MUTED};
    font-size: {font_px(FONT_BASE)}px;
    padding: {px(4)}px {px(6)}px;
    min-height: {px(28)}px;
}}
QPushButton#genreChipClear:hover {{
    color: {COLOR_TEXT_SECONDARY};
}}
QLabel#genreChipCount {{
    background: transparent;
    color: {COLOR_TEXT_MUTED};
    font-size: {font_px(FONT_BASE)}px;
}}
QWidget#genreChipHost {{
    background: transparent;
    padding-top: {px(2)}px;
}}
QPushButton#countryFilterChip {{
    background-color: {COLOR_CARD_ALT};
    border: 1px solid {COLOR_BORDER};
    border-radius: {px(RADIUS_CHIP)}px;
    color: {COLOR_TEXT_CHIP};
    font-size: {font_px(FONT_BASE)}px;
    font-weight: 500;
    padding: {px(7)}px {px(12)}px;
    min-height: {px(34)}px;
}}
QPushButton#countryFilterChip:hover {{
    background-color: {COLOR_HOVER};
    border-color: {COLOR_BORDER_HOVER};
}}
QPushButton#countryFilterChip:checked {{
    background-color: {COLOR_ACCENT_SOFT};
    border-color: {COLOR_ACCENT};
    color: {COLOR_ACCENT_HOVER};
}}
QPushButton#countryFilterChip:disabled {{
    background-color: {COLOR_CARD};
    border-color: {COLOR_DIVIDER};
    color: {COLOR_TEXT_MUTED};
}}
QPushButton#countryChipClear {{
    background: transparent;
    border: none;
    color: {COLOR_TEXT_SECONDARY};
    font-size: {font_px(FONT_SMALL)}px;
    padding: 0 {px(4)}px;
}}
QPushButton#countryChipClear:hover {{
    color: {COLOR_TEXT};
}}
QLabel#countryChipCount {{
    background: transparent;
    color: {COLOR_TEXT_SECONDARY};
    font-size: {font_px(FONT_SMALL)}px;
}}
QWidget#countryChipHost {{
    background: transparent;
    padding-top: {px(2)}px;
}}
QPushButton#chipExpandToggle {{
    background: transparent;
    border: none;
    color: {COLOR_TEXT_SECONDARY};
    font-size: {font_px(FONT_SMALL)}px;
    padding: 0 {px(4)}px;
    text-align: left;
}}
QPushButton#chipExpandToggle:hover {{
    color: {COLOR_TEXT};
}}
"""

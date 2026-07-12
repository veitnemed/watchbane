"""QSS for reusable desktop controls."""

from desktop.theme.scaling import font_px, layout_px
from desktop.theme.tokens import (
    COLOR_ACCENT,
    COLOR_ACCENT_SOFT,
    COLOR_BORDER,
    COLOR_CARD,
    COLOR_CONTROL_HOVER,
    COLOR_FOCUS_BORDER,
    COLOR_TEXT,
    COLOR_TEXT_SECONDARY,
    FONT_BASE,
    FONT_TINY,
)


def build_user_rating_selector_style() -> str:
    return f"""
QWidget#userRatingSelector {{ background: transparent; }}
QPushButton#userRatingButton {{
    background-color: {COLOR_CARD};
    border: 1px solid {COLOR_BORDER};
    border-radius: {layout_px(6)}px;
    color: {COLOR_TEXT_SECONDARY};
    font-size: {font_px(FONT_TINY)}px;
    padding: {layout_px(6)}px {layout_px(7)}px;
    min-height: {layout_px(40)}px;
}}
QWidget[candidatePanel="true"] QPushButton#userRatingButton {{
    font-size: {font_px(FONT_TINY - 1)}px;
    min-height: {layout_px(32)}px;
    padding-left: {layout_px(4)}px;
    padding-right: {layout_px(4)}px;
}}
QPushButton#userRatingButton:hover {{
    background-color: {COLOR_CONTROL_HOVER};
    color: {COLOR_TEXT};
}}
QPushButton#userRatingButton:checked {{
    background-color: {COLOR_ACCENT_SOFT};
    border: 2px solid {COLOR_ACCENT};
    color: {COLOR_TEXT};
    font-weight: 700;
}}
QPushButton#userRatingButton:focus {{ border-color: {COLOR_FOCUS_BORDER}; }}
QPushButton#userRatingButton:disabled {{ color: {COLOR_BORDER}; }}
"""

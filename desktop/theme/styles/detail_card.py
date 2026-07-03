"""QSS builders for detail card and poster widgets."""

from __future__ import annotations

from desktop.theme.tokens import *  # noqa: F403

def build_detail_card_style() -> str:
    """Return the watched detail card stylesheet."""
    return f"""
QFrame#detailCard {{
    background-color: {COLOR_CARD};
    border: 1px solid {COLOR_BORDER};
    border-radius: {RADIUS_CARD_LARGE}px;
}}
QLabel#detailTitle {{
    background: transparent;
    color: {COLOR_TEXT};
    font-size: {FONT_TITLE_LARGE}px;
    font-weight: 700;
    padding: 0 0 {SPACING_XSMALL}px 0;
}}
QWidget#detailPosterActions {{
    background: transparent;
}}
QPushButton#candidateMarkWatchedButton,
QPushButton#candidateHideButton {{
    background-color: {COLOR_CARD};
    border: 1px solid {COLOR_BORDER};
    border-radius: 18px;
    padding: 0;
    min-width: 36px;
    max-width: 36px;
    min-height: 36px;
    max-height: 36px;
}}
QPushButton#candidateMarkWatchedButton:hover,
QPushButton#candidateHideButton:hover {{
    border-color: {COLOR_ACCENT};
    background-color: {COLOR_CARD_ALT};
}}
QPushButton#candidateMarkWatchedButton:disabled,
QPushButton#candidateHideButton:disabled {{
    border-color: {COLOR_BORDER};
    background-color: {COLOR_CARD};
}}
QLabel#genrePill {{
    background-color: {COLOR_CARD_ALT};
    border: 1px solid {COLOR_BORDER};
    border-radius: {RADIUS_CHIP}px;
    padding: 7px 12px;
    color: {COLOR_TEXT_CHIP};
    font-size: {FONT_BASE}px;
}}
QWidget#mainInfoSection {{
    background: transparent;
}}
QFrame#mainInfoDivider {{
    background-color: {COLOR_BORDER};
    min-height: 1px;
    max-height: 1px;
    border: none;
}}
QLabel#mainInfoTitle {{
    background: transparent;
    color: {COLOR_TEXT};
    font-size: {FONT_SECTION}px;
    font-weight: 700;
    padding: {SPACING_SMALL}px 0 2px 0;
}}
QLabel#mainInfoLabel {{
    background: transparent;
    color: {COLOR_TEXT_SECONDARY};
    font-size: {FONT_SMALL}px;
    padding: 1px 0;
}}
QLabel#mainInfoValue {{
    background: transparent;
    color: {COLOR_TEXT};
    font-size: {FONT_BASE}px;
    font-weight: 600;
    padding: 1px 0;
}}
QFrame#overviewBlock {{
    background: transparent;
    border: none;
}}
QFrame#overviewDivider {{
    background-color: {COLOR_BORDER};
    min-height: 1px;
    max-height: 1px;
    border: none;
}}
QLabel#overviewTitle {{
    background: transparent;
    color: {COLOR_TEXT};
    font-size: {FONT_OVERVIEW_TITLE}px;
    font-weight: 700;
    padding: 0;
}}
QLabel#overviewText {{
    background: transparent;
    color: {COLOR_TEXT_SECONDARY};
    font-size: {FONT_OVERVIEW_TEXT}px;
    line-height: {OVERVIEW_TEXT_LINE_HEIGHT}%;
}}
"""


def build_poster_placeholder_style() -> str:
    """Return the poster placeholder stylesheet."""
    return (
        f"background-color: {COLOR_CARD}; border: 1px solid {COLOR_BORDER}; "
        f"border-radius: {RADIUS_CARD}px; color: {COLOR_TEXT_MUTED};"
    )


def build_poster_image_style() -> str:
    """Return the poster image stylesheet."""
    return f"background: transparent; border-radius: {RADIUS_CARD}px;"


def build_bar_track_style() -> str:
    """Return the fallback analytics bar track stylesheet."""
    return f"background-color: {COLOR_CARD_ALT}; border-radius: {RADIUS_BAR}px;"


def build_bar_fill_style() -> str:
    """Return the fallback analytics bar fill stylesheet."""
    return f"background-color: {COLOR_ACCENT}; border-radius: {RADIUS_BAR}px;"

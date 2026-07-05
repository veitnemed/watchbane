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
QFrame#detailHeroCard {{
    background-color: qlineargradient(
        x1: 0, y1: 0, x2: 1, y2: 1,
        stop: 0 {COLOR_DETAIL_HERO_BG_TOP},
        stop: 0.62 {COLOR_DETAIL_HERO_BG_BOTTOM},
        stop: 1 #070a10
    );
    border: 1px solid {COLOR_DETAIL_HERO_BORDER};
    border-radius: {DETAIL_HERO_CARD_RADIUS}px;
}}
QFrame#detailPosterShell {{
    background-color: #0b1017;
    border: 1px solid {COLOR_DETAIL_HERO_BORDER};
    border-radius: {DETAIL_POSTER_RADIUS}px;
}}
QLabel#detailUserScoreBadge {{
    background-color: #05070b;
    border: 1px solid {COLOR_DETAIL_GOLD};
    border-radius: {DETAIL_USER_SCORE_BADGE_RADIUS}px;
    color: {COLOR_DETAIL_GOLD};
    font-size: {FONT_BASE}px;
    font-weight: 700;
    padding: 0 {DETAIL_USER_SCORE_BADGE_PADDING_X}px;
    min-height: {DETAIL_USER_SCORE_BADGE_HEIGHT}px;
    min-width: {DETAIL_USER_SCORE_BADGE_MIN_WIDTH}px;
}}
QLabel#detailTitle {{
    background: transparent;
    color: {COLOR_DETAIL_WARM_TEXT};
    font-family: "{DETAIL_TITLE_FONT_FAMILY}", "{DETAIL_TITLE_FONT_FALLBACK}";
    font-size: {DETAIL_TITLE_FONT_SIZE - 2}px;
    font-weight: 600;
    padding: 0 0 {SPACING_SMALL}px 0;
}}
QWidget#detailPosterActions {{
    background: transparent;
}}
QPushButton#candidateMarkWatchedButton,
QPushButton#candidateHideButton {{
    background-color: rgba(12, 17, 24, 190);
    border: 1px solid {COLOR_DETAIL_HERO_BORDER};
    border-radius: 18px;
    padding: 0;
    min-width: 36px;
    max-width: 36px;
    min-height: 36px;
    max-height: 36px;
}}
QPushButton#candidateMarkWatchedButton:hover,
QPushButton#candidateHideButton:hover {{
    border-color: {COLOR_DETAIL_GOLD};
    background-color: rgba(33, 42, 53, 210);
}}
QPushButton#candidateMarkWatchedButton:disabled,
QPushButton#candidateHideButton:disabled {{
    border-color: {COLOR_DETAIL_HERO_BORDER};
    background-color: rgba(12, 17, 24, 150);
}}
QLabel#genrePill {{
    background-color: rgba(255, 255, 255, 0.055);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: {DETAIL_CHIP_RADIUS}px;
    padding: 0 12px;
    color: #d7dde6;
    font-size: {FONT_BASE}px;
}}
QWidget#mainInfoSection,
QWidget#detailMainInfoSection {{
    background: transparent;
}}
QFrame#mainInfoPanel,
QFrame#detailMainInfoPanel {{
    background-color: {COLOR_DETAIL_GLASS};
    border: 1px solid {COLOR_DETAIL_HERO_BORDER_SOFT};
    border-radius: {DETAIL_MAIN_INFO_PANEL_RADIUS}px;
}}
QFrame#mainInfoDivider,
QFrame#detailMainInfoHeaderDivider {{
    background-color: rgba(214, 189, 141, 0.28);
    min-height: 1px;
    max-height: 1px;
    border: none;
}}
QLabel#mainInfoTitle,
QLabel#detailMainInfoHeader {{
    background: transparent;
    color: {COLOR_DETAIL_GOLD_SOFT};
    font-size: {FONT_SMALL}px;
    font-weight: 700;
    letter-spacing: 1px;
    padding: 0;
}}
QLabel#mainInfoLabel,
QLabel#detailMainInfoLabel {{
    background: transparent;
    color: #aab3c0;
    font-size: {FONT_SMALL}px;
    padding: 0;
}}
QLabel#mainInfoValue,
QLabel#detailMainInfoValue {{
    background: transparent;
    color: {COLOR_DETAIL_WARM_TEXT};
    font-size: {FONT_BASE}px;
    font-weight: 600;
    padding: 0;
}}
QFrame#overviewBlock,
QFrame#detailOverviewSection {{
    background: transparent;
    border: none;
}}
QFrame#overviewDivider,
QFrame#detailOverviewDivider {{
    background-color: rgba(214, 189, 141, 0.22);
    min-height: 1px;
    max-height: 1px;
    border: none;
}}
QLabel#overviewTitle,
QLabel#detailOverviewHeader {{
    background: transparent;
    color: {COLOR_DETAIL_GOLD_SOFT};
    font-size: {FONT_OVERVIEW_TITLE}px;
    font-weight: 700;
    letter-spacing: 1px;
    padding: 0;
}}
QLabel#overviewText,
QLabel#detailOverviewText {{
    background: transparent;
    color: #b7bfca;
    font-size: {FONT_OVERVIEW_TEXT}px;
    line-height: {OVERVIEW_TEXT_LINE_HEIGHT}%;
}}
"""


def build_poster_placeholder_style() -> str:
    """Return the poster placeholder stylesheet."""
    return (
        f"background-color: #0b1017; border: 1px solid {COLOR_DETAIL_HERO_BORDER}; "
        f"border-radius: {DETAIL_POSTER_RADIUS}px; color: {COLOR_TEXT_MUTED};"
    )


def build_poster_image_style() -> str:
    """Return the poster image stylesheet."""
    return f"background: transparent; border-radius: {DETAIL_POSTER_RADIUS}px;"


def build_bar_track_style() -> str:
    """Return the fallback analytics bar track stylesheet."""
    return f"background-color: {COLOR_CARD_ALT}; border-radius: {RADIUS_BAR}px;"


def build_bar_fill_style() -> str:
    """Return the fallback analytics bar fill stylesheet."""
    return f"background-color: {COLOR_ACCENT}; border-radius: {RADIUS_BAR}px;"

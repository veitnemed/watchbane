"""QSS builders for detail card and poster widgets."""

from __future__ import annotations

from desktop.theme.tokens import *  # noqa: F403

def build_detail_card_style() -> str:
    """Return the watched detail card stylesheet."""
    return f"""
QFrame#detailCard {{
    background-color: {COLOR_CARD};
    border: 1px solid {COLOR_BORDER};
    border-radius: {detail_px(RADIUS_CARD_LARGE)}px;
}}
QFrame#detailHeroCard {{
    background-color: qlineargradient(
        x1: 0, y1: 0, x2: 1, y2: 1,
        stop: 0 {COLOR_DETAIL_HERO_BG_TOP},
        stop: 0.62 {COLOR_DETAIL_HERO_BG_BOTTOM},
        stop: 1 {COLOR_DETAIL_HERO_BG_END}
    );
    border: 1px solid {COLOR_DETAIL_HERO_BORDER};
    border-radius: {detail_px(DETAIL_HERO_CARD_RADIUS)}px;
}}
QWidget#detailContentContainer {{
    background: transparent;
}}
QFrame#detailPosterShell {{
    background-color: {COLOR_SCORE_BADGE_BG};
    border: {poster_px(DETAIL_POSTER_BORDER_WIDTH)}px solid {COLOR_BORDER_HOVER};
    border-radius: {poster_px(DETAIL_POSTER_RADIUS)}px;
}}
QLabel#detailUserScoreBadge {{
    background-color: {COLOR_TEXT};
    border: 1px solid {COLOR_TEXT};
    border-radius: {detail_px(DETAIL_USER_SCORE_BADGE_RADIUS)}px;
    color: {COLOR_TEXT_INVERTED};
    font-size: {font_px(DETAIL_USER_SCORE_BADGE_FONT_SIZE)}px;
    font-weight: 700;
    padding: 0 {detail_px(DETAIL_USER_SCORE_BADGE_PADDING_X)}px;
    min-height: {detail_px(DETAIL_USER_SCORE_BADGE_HEIGHT)}px;
    min-width: {detail_px(DETAIL_USER_SCORE_BADGE_MIN_WIDTH)}px;
}}
QFrame#detailHeroCard[mediaType="movie"] {{
    background-color: qlineargradient(
        x1: 0, y1: 0, x2: 1, y2: 1,
        stop: 0 {FILM_SURFACE_1},
        stop: 0.62 {FILM_SURFACE_0},
        stop: 1 {FILM_WINDOW_BG}
    );
    border: 1px solid {FILM_BORDER};
}}
QFrame#detailPosterShell[mediaType="movie"] {{
    background-color: {FILM_SURFACE_0};
    border: {poster_px(DETAIL_POSTER_BORDER_WIDTH)}px solid {FILM_BORDER_STRONG};
}}
QLabel#detailUserScoreBadge[mediaType="movie"] {{
    background-color: {FILM_MOVIE_BADGE_BG};
    border: 1px solid {FILM_MOVIE_BADGE_BORDER};
    color: {FILM_MOVIE_BADGE_TEXT};
}}
QLabel#detailUserScoreBadge[mediaType="tv"] {{
    background-color: {FILM_MOVIE_BADGE_BG};
    border: 1px solid {FILM_SERIES_BADGE_BORDER};
    color: {FILM_SERIES_BADGE_TEXT};
}}
QLabel#detailMediaTypeBadge {{
    background-color: {FILM_MOVIE_BADGE_BG};
    border: 1px solid {FILM_MOVIE_BADGE_BORDER};
    border-radius: {detail_px(15)}px;
    color: {FILM_MOVIE_BADGE_TEXT};
    font-size: {font_px(FONT_SMALL)}px;
    font-weight: 800;
    letter-spacing: 1px;
    padding: {detail_px(5)}px {detail_px(14)}px;
    min-height: {detail_px(28)}px;
}}
QLabel#detailMediaTypeBadge[mediaType="tv"] {{
    background-color: {FILM_SERIES_BADGE_BG};
    border: 1px solid {FILM_SERIES_BADGE_BORDER};
    color: {FILM_SERIES_BADGE_TEXT};
}}
QLabel#detailTitle {{
    background: transparent;
    color: {COLOR_DETAIL_TITLE};
    font-family: "{DETAIL_TITLE_FONT_FAMILY}", {DETAIL_TITLE_FONT_FALLBACK};
    font-size: {font_px(DETAIL_TITLE_FONT_SIZE)}px;
    font-weight: 600;
    padding: 0;
}}
QLabel#detailTitleMeta {{
    background: transparent;
    color: {COLOR_TEXT_SECONDARY};
    font-size: {font_px(FONT_SMALL + 4)}px;
    font-weight: 500;
    padding: 0;
}}
QLabel#detailTitle[mediaType="movie"] {{
    color: {FILM_TEXT};
    font-weight: 700;
}}
QLabel#detailTitleMeta[mediaType="movie"] {{
    color: {FILM_TEXT_SUBTLE};
}}
QFrame#detailScoreSummaryTopDivider,
QFrame#detailScoreSummaryBottomDivider {{
    background-color: {FILM_BORDER};
    min-height: {detail_px(1)}px;
    max-height: {detail_px(1)}px;
    border: none;
}}
QWidget#detailPosterActions {{
    background: transparent;
}}
QPushButton#candidateMarkWatchedButton,
QPushButton#candidateHideButton {{
    background-color: {COLOR_DETAIL_ACTION_BG};
    border: 1px solid {COLOR_DETAIL_HERO_BORDER};
    border-radius: {detail_px(18)}px;
    padding: 0;
    min-width: {detail_px(36)}px;
    max-width: {detail_px(36)}px;
    min-height: {detail_px(36)}px;
    max-height: {detail_px(36)}px;
}}
QPushButton#candidateMarkWatchedButton:hover,
QPushButton#candidateHideButton:hover {{
    border-color: {COLOR_BORDER_ACTIVE};
    background-color: {COLOR_DETAIL_ACTION_BG_HOVER};
}}
QPushButton#candidateMarkWatchedButton:disabled,
QPushButton#candidateHideButton:disabled {{
    border-color: {COLOR_DETAIL_HERO_BORDER};
    background-color: {COLOR_DETAIL_ACTION_BG_DISABLED};
}}
QLabel#genrePill {{
    background-color: {FILM_CHIP_BG};
    border: 1px solid {FILM_CHIP_BORDER};
    border-radius: {detail_px(DETAIL_CHIP_RADIUS)}px;
    padding: 0 {detail_px(DETAIL_CHIP_H_PADDING)}px;
    color: {FILM_CHIP_TEXT};
    font-size: {font_px(DETAIL_CHIP_FONT_SIZE)}px;
    font-weight: 600;
}}
QLabel#detailFinalScoreStarsLabel {{
    background: transparent;
    color: {FILM_TEXT_MUTED};
    font-size: {font_px(FONT_SMALL)}px;
    font-weight: 500;
    padding: 0;
}}
QWidget#mainInfoSection,
QWidget#detailMainInfoSection {{
    background: transparent;
}}
QFrame#mainInfoPanel,
QFrame#detailMainInfoPanel {{
    background-color: {COLOR_DETAIL_GLASS};
    border: 1px solid {COLOR_DETAIL_HERO_BORDER_SOFT};
    border-radius: {detail_px(DETAIL_MAIN_INFO_PANEL_RADIUS)}px;
}}
QFrame#detailMainInfoPanel[mediaType="movie"] {{
    background-color: {FILM_SURFACE_1};
    border: 1px solid {FILM_BORDER};
}}
QFrame#mainInfoDivider,
QFrame#detailMainInfoHeaderDivider {{
    background-color: {COLOR_DETAIL_SECTION_DIVIDER};
    min-height: {detail_px(1)}px;
    max-height: {detail_px(1)}px;
    border: none;
}}
QFrame#detailMainInfoHeaderDivider[mediaType="movie"],
QFrame#detailOverviewDivider[mediaType="movie"] {{
    background-color: {FILM_BORDER};
}}
QLabel#mainInfoTitle,
QLabel#detailMainInfoHeader {{
    background: transparent;
    color: {COLOR_DETAIL_SECTION_HEADER};
    font-size: {font_px(FONT_DETAIL_MAIN_INFO_HEADER)}px;
    font-weight: 700;
    letter-spacing: 1px;
    padding: 0;
}}
QPushButton#detailMainInfoToggleButton {{
    background-color: transparent;
    border: none;
    border-radius: {detail_px(RADIUS_BUTTON_SMALL)}px;
    color: {FILM_TEXT_MUTED};
    font-size: {font_px(FONT_SMALL)}px;
    font-weight: 600;
    padding: {detail_px(2)}px 0;
    min-height: {detail_px(20)}px;
}}
QPushButton#detailMainInfoToggleButton:hover {{
    color: {FILM_TEXT_SUBTLE};
    background-color: transparent;
}}
QLabel#mainInfoLabel,
QLabel#detailMainInfoLabel {{
    background: transparent;
    color: {COLOR_DETAIL_LABEL};
    font-size: {font_px(FONT_DETAIL_MAIN_INFO_LABEL)}px;
    padding: 0;
}}
QLabel#detailMainInfoIcon {{
    background: transparent;
}}
QFrame#detailMainInfoRowDivider {{
    background-color: {FILM_BORDER_WEAK};
    min-height: {detail_px(1)}px;
    max-height: {detail_px(1)}px;
    border: none;
}}
QLabel#mainInfoValue,
QLabel#detailMainInfoValue {{
    background: transparent;
    color: {COLOR_DETAIL_VALUE};
    font-size: {font_px(FONT_DETAIL_MAIN_INFO_VALUE)}px;
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
    background-color: {COLOR_DETAIL_SECTION_DIVIDER};
    min-height: {detail_px(1)}px;
    max-height: {detail_px(1)}px;
    border: none;
}}
QLabel#overviewTitle,
QLabel#detailOverviewHeader {{
    background: transparent;
    color: {COLOR_DETAIL_SECTION_HEADER};
    font-size: {font_px(FONT_OVERVIEW_TITLE)}px;
    font-weight: 700;
    letter-spacing: 1px;
    padding: 0;
}}
QLabel#overviewText,
QLabel#detailOverviewText {{
    background: transparent;
    color: {COLOR_DETAIL_OVERVIEW_TEXT};
    font-size: {font_px(FONT_DETAIL_OVERVIEW_TEXT)}px;
    line-height: {OVERVIEW_TEXT_LINE_HEIGHT}%;
}}
"""


def build_poster_placeholder_style() -> str:
    """Return the poster placeholder stylesheet."""
    return (
        f"background-color: {COLOR_SCORE_BADGE_BG}; border: none; "
        f"border-radius: {poster_px(max(0, DETAIL_POSTER_RADIUS - DETAIL_POSTER_BORDER_WIDTH))}px; "
        f"color: {COLOR_TEXT_MUTED};"
    )


def build_poster_image_style() -> str:
    """Return the poster image stylesheet."""
    return (
        "background: transparent; "
        f"border-radius: {poster_px(max(0, DETAIL_POSTER_RADIUS - DETAIL_POSTER_BORDER_WIDTH))}px;"
    )


def build_bar_track_style() -> str:
    """Return the fallback analytics bar track stylesheet."""
    return f"background-color: {COLOR_CARD_ALT}; border-radius: {detail_px(RADIUS_BAR)}px;"


def build_bar_fill_style() -> str:
    """Return the fallback analytics bar fill stylesheet."""
    return f"background-color: {COLOR_ACCENT}; border-radius: {detail_px(RADIUS_BAR)}px;"

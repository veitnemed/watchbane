"""QSS for the Candidates filters and list tabs."""

from __future__ import annotations

from desktop.theme.tokens import *  # noqa: F403


def build_candidates_shell_style() -> str:
    """Return stylesheet for candidate search filters and list."""
    return f"""
QLineEdit#candidateListSearch {{
    font-size: {font_px(FONT_BASE)}px;
}}
QWidget#candidateSearchSidebar {{
    background: transparent;
}}
QLabel#candidateSearchHeader {{
    background: transparent;
    color: {COLOR_TEXT};
    font-size: {font_px(FONT_SECTION)}px;
    font-weight: 700;
}}
QFrame#candidateFiltersIntro {{
    background-color: {COLOR_CARD};
    border: 1px solid {COLOR_BORDER};
    border-radius: {px(RADIUS_CARD)}px;
}}
QLabel#candidateFiltersIntroLead {{
    background: transparent;
    color: {COLOR_TEXT_SECONDARY};
    font-size: {font_px(FONT_BASE)}px;
    line-height: 1.35;
}}
QLabel#candidateFiltersIntroStats {{
    background: transparent;
    color: {COLOR_TEXT};
    font-size: {font_px(FONT_SECTION)}px;
    font-weight: 600;
}}
QLabel#candidateSearchHint,
QLabel#candidateSearchResultsSummary,
QLabel#candidateSearchDetailPlaceholder,
QLabel#candidateSearchExplanation {{
    background: transparent;
    color: {COLOR_TEXT_SECONDARY};
    font-size: {font_px(FONT_BASE)}px;
}}
QLabel#candidateSearchFieldLabel {{
    color: {COLOR_TEXT};
    font-size: {font_px(FONT_SECTION)}px;
    font-weight: 700;
    padding: {px(8)}px 0 {px(2)}px 0;
}}
QListWidget#candidateListWidget {{
    background-color: {COLOR_CARD};
    border: 1px solid {COLOR_BORDER};
    border-radius: {px(RADIUS_CARD)}px;
    color: {COLOR_TEXT};
    font-size: {font_px(FONT_SMALL)}px;
    padding: {px(8)}px;
    outline: none;
}}
QListWidget#candidateListWidget::item {{
    padding: 0;
    border: none;
    margin: {px(1)}px 0;
    background: transparent;
}}
QListWidget#candidateListWidget::item:selected {{
    background: transparent;
    color: {COLOR_TEXT};
}}
QListWidget#candidateListWidget::item:hover {{
    background: transparent;
}}
QLabel#candidateListCounter {{
    background: transparent;
    color: {COLOR_TEXT_SECONDARY};
    font-size: {font_px(FONT_SMALL)}px;
    font-weight: 600;
    padding: 0 {px(4)}px;
}}
QWidget#candidateSortRow {{
    background: transparent;
}}
QLabel#candidateSortLabel {{
    background: transparent;
    color: {COLOR_TEXT};
    font-size: {font_px(FONT_BASE)}px;
    font-weight: 600;
}}
QComboBox#candidateListSort {{
    background-color: {COLOR_CARD};
    border: 1px solid {COLOR_BORDER};
    border-radius: {px(RADIUS_INPUT)}px;
    color: {COLOR_TEXT};
    font-size: {font_px(FONT_BASE)}px;
    padding: {px(INPUT_PADDING_Y)}px {px(INPUT_PADDING_X)}px;
    min-height: {px(20)}px;
    max-width: {px(160)}px;
}}
QComboBox#candidateListSort:focus {{
    border: 1px solid {COLOR_FOCUS_BORDER};
}}
QComboBox#candidateListSort::drop-down {{
    border: none;
    width: {px(28)}px;
}}
QComboBox#candidateListSort::down-arrow {{
    width: {px(10)}px;
    height: {px(10)}px;
}}
QWidget#candidateFiltersRoot {{
    font-size: {font_px(FONT_BASE)}px;
}}
QPushButton#candidateSearchApplyTopButton {{
    background-color: {COLOR_ADD_BUTTON};
    border: 1px solid {COLOR_ADD_BUTTON_BORDER};
    border-radius: {px(RADIUS_BUTTON_SMALL)}px;
    color: {COLOR_TEXT};
    font-size: {font_px(FONT_SMALL)}px;
    font-weight: 600;
    padding: {px(4)}px {px(12)}px;
    min-height: {px(28)}px;
    max-height: {px(32)}px;
}}
QPushButton#candidateSearchApplyTopButton:hover {{
    background-color: {COLOR_ADD_BUTTON_HOVER};
}}
QPushButton#candidateSearchResetTopButton {{
    background-color: {COLOR_CARD_ALT};
    border: 1px solid {COLOR_BORDER};
    border-radius: {px(RADIUS_BUTTON_SMALL)}px;
    color: {COLOR_TEXT};
    font-size: {font_px(FONT_SMALL)}px;
    font-weight: 600;
    padding: {px(4)}px {px(12)}px;
    min-height: {px(28)}px;
    max-height: {px(32)}px;
}}
QPushButton#candidateSearchResetTopButton:hover {{
    background-color: {COLOR_CONTROL_HOVER};
    border-color: {COLOR_BORDER_HOVER};
}}
QPushButton#candidateSearchButton,
QPushButton#candidateSearchAddWatched {{
    background-color: {COLOR_ADD_BUTTON};
    border: 1px solid {COLOR_ADD_BUTTON_BORDER};
    border-radius: {px(RADIUS_BUTTON)}px;
    color: {COLOR_TEXT};
    font-size: {font_px(FONT_BASE)}px;
    font-weight: 600;
    padding: {px(10)}px {px(16)}px;
    min-height: {px(40)}px;
}}
QPushButton#candidateSearchButton:hover,
QPushButton#candidateSearchAddWatched:hover {{
    background-color: {COLOR_ADD_BUTTON_HOVER};
}}
QPushButton#candidateSearchWatchlist,
QPushButton#candidateSearchHide {{
    background-color: {COLOR_CARD_ALT};
    border: 1px solid {COLOR_BORDER};
    border-radius: {px(RADIUS_BUTTON)}px;
    color: {COLOR_TEXT};
    font-size: {font_px(FONT_SMALL)}px;
    padding: {px(8)}px {px(12)}px;
}}
QPushButton#candidateSearchWatchlist:hover,
QPushButton#candidateSearchHide:hover {{
    background-color: {COLOR_CONTROL_HOVER};
}}
QFrame#candidateSearchDetailCard {{
    background-color: {COLOR_CARD};
    border: 1px solid {COLOR_BORDER};
    border-radius: {px(RADIUS_CARD)}px;
}}
"""

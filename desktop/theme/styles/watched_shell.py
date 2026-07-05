"""QSS for the Watched tab sidebar, filters and list."""

from __future__ import annotations

from desktop.theme.tokens import *  # noqa: F403


def build_watched_shell_style() -> str:
    """Return stylesheet for watched sidebar and filter panel."""
    return f"""
QListWidget#watchedList {{
    padding: {px(8)}px;
}}
QWidget#watchedSidebar {{
    background: transparent;
}}
QLineEdit#watchedSearch {{
    font-size: {font_px(FONT_BASE)}px;
}}
QPushButton#watchedAddTitle {{
    background-color: {COLOR_ADD_BUTTON};
    border: 1px solid {COLOR_ADD_BUTTON_BORDER};
    border-radius: {control_px(RADIUS_BUTTON)}px;
    color: {COLOR_TEXT};
    font-size: {font_px(FONT_SECTION)}px;
    font-weight: 600;
    padding: {control_px(BUTTON_PADDING_Y)}px {control_px(BUTTON_PADDING_X)}px;
    min-height: {control_px(40)}px;
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 {COLOR_ADD_BUTTON_TOP},
        stop:1 {COLOR_ADD_BUTTON}
    );
}}
QPushButton#watchedAddTitle:hover {{
    border-color: {COLOR_ADD_BUTTON_HOVER};
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 {COLOR_ADD_BUTTON_HOVER_TOP},
        stop:1 {COLOR_ADD_BUTTON_HOVER}
    );
}}
QPushButton#watchedFilterToggle {{
    background-color: transparent;
    border: none;
    border-radius: {px(RADIUS_BUTTON_SMALL)}px;
    color: {COLOR_TEXT_SECONDARY};
    font-size: {font_px(FONT_SMALL)}px;
    font-weight: 600;
    padding: {px(6)}px {px(4)}px;
    text-align: left;
}}
QPushButton#watchedFilterToggle:hover {{
    color: {COLOR_TEXT};
    background-color: {COLOR_CARD_ALT};
}}
QPushButton#watchedFilterToggle[watchedFiltersActive="true"] {{
    color: {COLOR_TEXT};
}}
QFrame#watchedFiltersPanel {{
    background-color: {COLOR_CARD};
    border: 1px solid {COLOR_BORDER};
    border-radius: {px(RADIUS_INPUT)}px;
}}
QPushButton#watchedFilterResetAll {{
    background-color: {COLOR_CARD_ALT};
    border: 1px solid {COLOR_BORDER};
    border-radius: {px(RADIUS_BUTTON_SMALL)}px;
    color: {COLOR_TEXT};
    font-size: {font_px(FONT_SMALL)}px;
    font-weight: 600;
    padding: {px(8)}px {px(10)}px;
}}
QPushButton#watchedFilterResetAll:hover {{
    background-color: {COLOR_CONTROL_HOVER};
    border-color: {COLOR_BORDER_HOVER};
}}
QLabel#watchedListCounter {{
    background: transparent;
    color: {COLOR_TEXT_SECONDARY};
    font-size: {font_px(FONT_SMALL)}px;
    font-weight: 600;
    padding: 0 {px(4)}px;
}}
QWidget#watchedSortRow {{
    background: transparent;
}}
QLabel#watchedSortLabel {{
    background: transparent;
    color: {COLOR_TEXT};
    font-size: {font_px(FONT_BASE)}px;
    font-weight: 600;
}}
QComboBox#watchedSort {{
    background-color: {COLOR_CARD};
    border: 1px solid {COLOR_BORDER};
    border-radius: {px(RADIUS_INPUT)}px;
    color: {COLOR_TEXT};
    font-size: {font_px(FONT_BASE)}px;
    padding: {px(INPUT_PADDING_Y)}px {px(INPUT_PADDING_X)}px;
    min-height: {px(20)}px;
}}
QComboBox#watchedSort:focus {{
    border: 1px solid {COLOR_FOCUS_BORDER};
}}
QComboBox#watchedSort::drop-down {{
    border: none;
    width: {px(28)}px;
}}
QComboBox#watchedSort::down-arrow {{
    width: {px(10)}px;
    height: {px(10)}px;
}}
QFrame#watchedScoreFilter,
QFrame#watchedYearFilter,
QFrame#watchedGenreFilter {{
    background-color: transparent;
    border: none;
    border-radius: 0;
}}
QLabel#watchedScoreFilterTitle,
QLabel#watchedYearFilterTitle,
QLabel#watchedGenreFilterTitle {{
    background: transparent;
    color: {COLOR_TEXT_SECONDARY};
    font-size: {font_px(FONT_SMALL)}px;
    font-weight: 600;
}}
QComboBox#watchedGenre {{
    background-color: {COLOR_SURFACE};
    font-size: {font_px(FONT_SMALL)}px;
    padding: {px(5)}px {px(8)}px;
}}
QLabel#watchedScoreFilterLabel,
QLabel#watchedYearFilterLabel {{
    background: transparent;
    color: {COLOR_TEXT_SECONDARY};
    font-size: {font_px(FONT_SMALL)}px;
}}
QLabel#watchedFilterValue {{
    background: transparent;
    color: {COLOR_TEXT};
    font-size: {font_px(FONT_SMALL)}px;
    font-weight: 600;
}}
"""

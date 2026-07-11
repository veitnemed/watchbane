"""QSS for the Watched tab sidebar, filters and list."""

from __future__ import annotations

from desktop.theme.tokens import *  # noqa: F403


def build_watched_shell_style() -> str:
    """Return stylesheet for watched sidebar and filter panel."""
    return f"""
QListWidget#watchedList {{
    padding: {px(8)}px;
}}
QListWidget#watchedList QScrollBar:vertical {{
    background: {FILM_SCROLLBAR_BG};
    width: {px(10)}px;
    margin: {px(SPACING_XSMALL)}px;
}}
QListWidget#watchedList QScrollBar::handle:vertical {{
    background: {FILM_SCROLLBAR_HANDLE};
    border-radius: {px(RADIUS_SCROLLBAR)}px;
    min-height: {px(28)}px;
}}
QListWidget#watchedList QScrollBar::handle:vertical:hover {{
    background: {FILM_SCROLLBAR_HANDLE_HOVER};
}}
QListWidget#watchedList QScrollBar::add-line:vertical,
QListWidget#watchedList QScrollBar::sub-line:vertical {{
    height: 0;
}}
QListWidget#watchedList QScrollBar:horizontal {{
    background: {FILM_SCROLLBAR_BG};
    height: {px(10)}px;
    margin: {px(SPACING_XSMALL)}px;
}}
QListWidget#watchedList QScrollBar::handle:horizontal {{
    background: {FILM_SCROLLBAR_HANDLE};
    border-radius: {px(RADIUS_SCROLLBAR)}px;
    min-width: {px(28)}px;
}}
QListWidget#watchedList QScrollBar::add-line:horizontal,
QListWidget#watchedList QScrollBar::sub-line:horizontal {{
    width: 0;
}}
QWidget#watchedSidebar {{
    background: transparent;
}}
QTabBar#librarySectionTabs {{
    background: transparent;
    border: none;
}}
QTabBar#librarySectionTabs::tab {{
    background-color: {FILM_SURFACE_1};
    border: 1px solid {FILM_BORDER_WEAK};
    color: {FILM_TEXT_SUBTLE};
    font-size: {font_px(FONT_SMALL)}px;
    font-weight: 600;
    min-height: {px(32)}px;
    padding: {px(5)}px {px(6)}px;
}}
QTabBar#librarySectionTabs::tab:first {{
    border-top-left-radius: {px(RADIUS_BUTTON_SMALL)}px;
    border-bottom-left-radius: {px(RADIUS_BUTTON_SMALL)}px;
}}
QTabBar#librarySectionTabs::tab:last {{
    border-top-right-radius: {px(RADIUS_BUTTON_SMALL)}px;
    border-bottom-right-radius: {px(RADIUS_BUTTON_SMALL)}px;
}}
QTabBar#librarySectionTabs::tab:selected {{
    background-color: {FILM_ACCENT_DIM};
    border-color: {FILM_ACCENT};
    color: {FILM_TEXT};
}}
QFrame#libraryStateActionPanel {{
    background-color: {FILM_SURFACE_0};
    border: 1px solid {FILM_BORDER_WEAK};
    border-radius: {px(RADIUS_CARD)}px;
}}
QPushButton#libraryPrimaryActionButton,
QPushButton#librarySecondaryActionButton,
QPushButton#libraryTertiaryActionButton {{
    background-color: {FILM_SURFACE_1};
    border: 1px solid {FILM_BORDER_WEAK};
    border-radius: {px(RADIUS_BUTTON_SMALL)}px;
    color: {FILM_TEXT};
    font-size: {font_px(FONT_SMALL)}px;
    font-weight: 700;
    min-height: {px(34)}px;
    padding: {px(5)}px {px(9)}px;
}}
QPushButton#libraryPrimaryActionButton {{
    background-color: {FILM_ACCENT_DIM};
    border-color: {FILM_ACCENT};
}}
QPushButton#libraryPrimaryActionButton:hover,
QPushButton#librarySecondaryActionButton:hover,
QPushButton#libraryTertiaryActionButton:hover {{
    border-color: {FILM_ACCENT_HOVER};
    background-color: {FILM_SURFACE_2};
}}
QLineEdit#watchedSearch {{
    background-color: {FILM_SURFACE_1};
    border: 1px solid {FILM_BORDER_WEAK};
    color: {FILM_TEXT};
    font-size: {font_px(FONT_SECTION)}px;
    padding: {px(INPUT_PADDING_Y + 1)}px {px(INPUT_PADDING_X + 2)}px;
    min-height: {px(34)}px;
}}
QPushButton#watchedAddTitle {{
    background-color: {FILM_ACCENT_DIM};
    border: 1px solid {FILM_ACCENT};
    border-radius: {control_px(RADIUS_BUTTON)}px;
    color: {COLOR_TEXT};
    font-size: {font_px(FONT_SECTION)}px;
    font-weight: 600;
    padding: {control_px(WATCHED_ADD_TITLE_PADDING_Y)}px {control_px(BUTTON_PADDING_X)}px;
    min-height: {control_px(WATCHED_ADD_TITLE_MIN_HEIGHT)}px;
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 {FILM_BORDER},
        stop:1 {FILM_ACCENT_DIM}
    );
}}
QPushButton#watchedAddTitle:hover {{
    border-color: {FILM_ACCENT_HOVER};
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 {FILM_ACCENT},
        stop:1 {FILM_BORDER}
    );
}}
QPushButton#watchedFilterToggle {{
    background-color: transparent;
    border: none;
    border-radius: {px(RADIUS_BUTTON_SMALL)}px;
    color: {FILM_TEXT_SUBTLE};
    font-size: {font_px(WATCHED_SIDEBAR_LABEL_FONT)}px;
    font-weight: 600;
    padding: {px(6)}px {px(4)}px;
    text-align: left;
}}
QPushButton#watchedFilterToggle:hover {{
    color: {FILM_TEXT};
    background-color: {FILM_SURFACE_1};
}}
QPushButton#watchedFilterToggle[watchedFiltersActive="true"] {{
    color: {FILM_TEXT};
}}
QFrame#watchedFiltersPanel {{
    background-color: {FILM_SURFACE_0};
    border: 1px solid {FILM_BORDER_WEAK};
    border-radius: {px(RADIUS_INPUT)}px;
}}
QPushButton#watchedFilterResetAll {{
    background-color: {FILM_SURFACE_1};
    border: 1px solid {FILM_BORDER_WEAK};
    border-radius: {px(RADIUS_BUTTON_SMALL)}px;
    color: {FILM_TEXT};
    font-size: {font_px(FONT_SECTION)}px;
    font-weight: 600;
    padding: {px(9)}px {px(12)}px;
    min-height: {px(36)}px;
}}
QPushButton#watchedFilterResetAll:hover {{
    background-color: {FILM_SURFACE_2};
    border-color: {FILM_BORDER};
}}
QLabel#watchedListCounter {{
    background: transparent;
    color: {FILM_TEXT_SUBTLE};
    font-size: {font_px(WATCHED_SIDEBAR_LABEL_FONT)}px;
    font-weight: 600;
    padding: 0 {px(4)}px;
}}
QWidget#watchedSortRow {{
    background: transparent;
}}
QLabel#watchedSortLabel {{
    background: transparent;
    color: {FILM_TEXT};
    font-size: {font_px(WATCHED_SIDEBAR_LABEL_FONT)}px;
    font-weight: 600;
}}
QComboBox#watchedSort {{
    background-color: {FILM_SURFACE_1};
    border: 1px solid {FILM_BORDER_WEAK};
    border-radius: {px(RADIUS_INPUT)}px;
    color: {FILM_TEXT};
    font-size: {font_px(FONT_SECTION)}px;
    padding: {px(INPUT_PADDING_Y + 1)}px {px(INPUT_PADDING_X + 2)}px;
    min-height: {px(34)}px;
}}
QComboBox#watchedSort:focus {{
    border: 1px solid {FILM_ACCENT};
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
QFrame#watchedMediaTypeFilter,
QFrame#watchedGenreFilter {{
    background-color: {FILM_SURFACE_1};
    border: 1px solid {FILM_BORDER_WEAK};
    border-radius: {px(RADIUS_BUTTON)}px;
}}
QLabel#watchedScoreFilterTitle,
QLabel#watchedYearFilterTitle,
QLabel#watchedMediaTypeFilterTitle,
QLabel#watchedGenreFilterTitle {{
    background: transparent;
    color: {FILM_TEXT};
    font-size: {font_px(FONT_SECTION)}px;
    font-weight: 700;
}}
QComboBox#watchedGenre {{
    background-color: {FILM_SURFACE_0};
    border: 1px solid {FILM_BORDER_WEAK};
    border-radius: {px(RADIUS_INPUT)}px;
    color: {FILM_TEXT};
    font-size: {font_px(FONT_SECTION)}px;
    padding: {px(7)}px {px(10)}px;
    min-height: {px(36)}px;
}}
QComboBox#watchedGenre:focus {{
    border: 1px solid {FILM_ACCENT};
}}
QLabel#watchedScoreFilterLabel,
QLabel#watchedYearFilterLabel {{
    background: transparent;
    color: {FILM_TEXT_SUBTLE};
    font-size: {font_px(FONT_SECTION)}px;
}}
QLabel#watchedFilterValue {{
    background: transparent;
    color: {FILM_TEXT};
    font-size: {font_px(FONT_SECTION)}px;
    font-weight: 600;
}}
QPushButton#watchedUserRatingFilterChip {{
    background-color: {FILM_SURFACE_0};
    border: 1px solid {FILM_BORDER_WEAK};
    border-radius: {px(6)}px;
    color: {FILM_TEXT_SUBTLE};
    font-size: {font_px(FONT_BASE)}px;
    padding: {px(6)}px {px(8)}px;
    min-height: {px(32)}px;
}}
QPushButton#watchedUserRatingFilterChip:hover {{
    border-color: {FILM_BORDER};
    color: {FILM_TEXT};
}}
QPushButton#watchedUserRatingFilterChip:checked {{
    background-color: {FILM_ACCENT_DIM};
    border-color: {FILM_ACCENT};
    color: {FILM_TEXT};
    font-weight: 700;
}}
"""

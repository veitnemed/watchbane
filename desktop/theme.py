"""Shared visual style tokens for the PyQt desktop GUI."""

from __future__ import annotations


# Colors
COLOR_BG = "#0f0f10"
COLOR_SURFACE = "#111113"
COLOR_CARD = "#171719"
COLOR_CARD_ALT = "#1c1c1f"
COLOR_BORDER = "#2a2a2e"
COLOR_BORDER_HOVER = "#3f3f46"
COLOR_HOVER = "#202024"
COLOR_CONTROL_HOVER = "#27272a"

COLOR_TEXT = "#f4f4f5"
COLOR_TEXT_SECONDARY = "#a1a1aa"
COLOR_TEXT_MUTED = "#71717a"
COLOR_TEXT_SOFT = "#d4d4d8"
COLOR_TEXT_CHIP = "#c7c7ce"

COLOR_ACCENT = "#10a37f"
COLOR_ACCENT_HOVER = "#13b98f"
COLOR_ACCENT_SOFT = "#1f3f36"
COLOR_ACCENT_PLOT_HOVER = "#35caa5"

COLOR_ADD_BUTTON = "#1f4d3d"
COLOR_ADD_BUTTON_BORDER = "#1a4234"
COLOR_ADD_BUTTON_TOP = "#2a6b55"
COLOR_ADD_BUTTON_HOVER = "#266552"
COLOR_ADD_BUTTON_HOVER_TOP = "#327a62"

COLOR_DELETE_BUTTON = "#7a3f3f"
COLOR_DELETE_BUTTON_HOVER = "#8f4a4a"

COLOR_IMDB_ACCENT = "#8b949e"
COLOR_KP_ACCENT = "#87978f"


# Typography
FONT_FAMILY = "Segoe UI"
FONT_FAMILY_FALLBACK = "Arial, sans-serif"
FONT_FAMILY_QSS = f'"{FONT_FAMILY}", {FONT_FAMILY_FALLBACK}'

FONT_APP = 13
FONT_BASE = 14
FONT_SMALL = 13
FONT_TINY = 12
FONT_SECTION = 16
FONT_TITLE = 24
FONT_TITLE_LARGE = 26
FONT_DIALOG_TITLE = 18
FONT_KPI_VALUE = 26
FONT_DENSE_SCORE = 22
FONT_OVERVIEW_TITLE = 20
FONT_OVERVIEW_TEXT = 16
FONT_RATING_VALUE_POINT = 16
FONT_RATING_LABEL_POINT = 8


# Radius
RADIUS_CARD = 16
RADIUS_CARD_LARGE = 18
RADIUS_CHIP = 12
RADIUS_INPUT = 12
RADIUS_BUTTON = 12
RADIUS_BUTTON_SMALL = 8
RADIUS_LIST_ITEM = 10
RADIUS_SCROLLBAR = 5
RADIUS_BAR = 6


# Spacing / padding
SPACING_XSMALL = 2
SPACING_SMALL = 6
SPACING_MEDIUM = 10
SPACING_LARGE = 14
SPACING_XLARGE = 16
SPACING_XXLARGE = 22

ROOT_MARGIN = 14
SECTION_PADDING = 10
CARD_PADDING = 22
OVERVIEW_SECTION_TOP_SPACING = 36
OVERVIEW_TITLE_DIVIDER_SPACING = 12
OVERVIEW_DIVIDER_TEXT_SPACING = 12
OVERVIEW_TEXT_LINE_HEIGHT = 155
INPUT_PADDING_Y = 8
INPUT_PADDING_X = 10
BUTTON_PADDING_Y = 8
BUTTON_PADDING_X = 14


TRANSPARENT_STYLE = "background: transparent;"


def build_app_style() -> str:
    """Return the main desktop application stylesheet."""
    return f"""
QMainWindow, QWidget {{
    background-color: {COLOR_BG};
    color: {COLOR_TEXT};
    font-family: {FONT_FAMILY_QSS};
    font-size: {FONT_APP}px;
}}
QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox {{
    background-color: {COLOR_CARD};
    border: 1px solid {COLOR_BORDER};
    border-radius: {RADIUS_INPUT}px;
    padding: {INPUT_PADDING_Y}px {INPUT_PADDING_X}px;
    color: {COLOR_TEXT};
    selection-background-color: {COLOR_ACCENT};
}}
QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus, QSpinBox:focus {{
    border: 1px solid {COLOR_ACCENT};
}}
QDoubleSpinBox::up-button,
QDoubleSpinBox::down-button,
QSpinBox::up-button,
QSpinBox::down-button {{
    background-color: {COLOR_CARD_ALT};
    border: none;
    width: 16px;
}}
QDoubleSpinBox::up-button:hover,
QDoubleSpinBox::down-button:hover,
QSpinBox::up-button:hover,
QSpinBox::down-button:hover {{
    background-color: {COLOR_CONTROL_HOVER};
}}
QComboBox::drop-down {{
    border: none;
    width: 24px;
}}
QComboBox QAbstractItemView {{
    background-color: {COLOR_CARD};
    border: 1px solid {COLOR_BORDER};
    color: {COLOR_TEXT};
    selection-background-color: {COLOR_ACCENT_SOFT};
}}
QListWidget {{
    background-color: {COLOR_CARD};
    border: 1px solid {COLOR_BORDER};
    border-radius: {RADIUS_CARD}px;
    padding: {SPACING_SMALL}px;
    outline: none;
}}
QListWidget#watchedList {{
    padding: 8px;
}}
QListWidget::item {{
    padding: 0;
    border: none;
    color: {COLOR_TEXT_SOFT};
    margin: 1px 0;
    background: transparent;
}}
QListWidget::item:selected {{
    background: transparent;
    color: {COLOR_TEXT};
}}
QListWidget::item:selected:!active {{
    background: transparent;
    color: {COLOR_TEXT};
}}
QListWidget::item:hover {{
    background: transparent;
}}
QWidget#watchedSidebar {{
    background: transparent;
}}
QLineEdit#watchedSearch {{
    font-size: {FONT_BASE}px;
}}
QPushButton#watchedAddTitle {{
    background-color: {COLOR_ADD_BUTTON};
    border: 1px solid {COLOR_ADD_BUTTON_BORDER};
    border-radius: {RADIUS_BUTTON}px;
    color: {COLOR_TEXT};
    font-size: {FONT_BASE}px;
    font-weight: 600;
    padding: 12px 14px;
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
    border-radius: {RADIUS_BUTTON_SMALL}px;
    color: {COLOR_TEXT_SECONDARY};
    font-size: {FONT_SMALL}px;
    font-weight: 600;
    padding: 6px 4px;
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
    border-radius: {RADIUS_INPUT}px;
}}
QPushButton#watchedFilterResetAll {{
    background-color: {COLOR_CARD_ALT};
    border: 1px solid {COLOR_BORDER};
    border-radius: {RADIUS_BUTTON_SMALL}px;
    color: {COLOR_TEXT};
    font-size: {FONT_SMALL}px;
    font-weight: 600;
    padding: 8px 10px;
}}
QPushButton#watchedFilterResetAll:hover {{
    background-color: {COLOR_CONTROL_HOVER};
    border-color: {COLOR_BORDER_HOVER};
}}
QLabel#watchedListCounter {{
    background: transparent;
    color: {COLOR_TEXT_SECONDARY};
    font-size: {FONT_SMALL}px;
    font-weight: 600;
    padding: 0 4px;
}}
QWidget#watchedSortRow {{
    background: transparent;
}}
QLabel#watchedSortLabel {{
    background: transparent;
    color: {COLOR_TEXT};
    font-size: {FONT_BASE}px;
    font-weight: 600;
}}
QComboBox#watchedSort {{
    background-color: {COLOR_CARD};
    border: 1px solid {COLOR_BORDER};
    border-radius: {RADIUS_INPUT}px;
    color: {COLOR_TEXT};
    font-size: {FONT_BASE}px;
    padding: {INPUT_PADDING_Y}px {INPUT_PADDING_X}px;
    min-height: 20px;
}}
QComboBox#watchedSort:focus {{
    border: 1px solid {COLOR_ACCENT};
}}
QComboBox#watchedSort::drop-down {{
    border: none;
    width: 28px;
}}
QComboBox#watchedSort::down-arrow {{
    width: 10px;
    height: 10px;
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
    font-size: {FONT_SMALL}px;
    font-weight: 600;
}}
QComboBox#watchedGenre {{
    background-color: {COLOR_SURFACE};
    font-size: {FONT_SMALL}px;
    padding: 5px 8px;
}}
QLabel#watchedScoreFilterLabel,
QLabel#watchedYearFilterLabel {{
    background: transparent;
    color: {COLOR_TEXT_SECONDARY};
    font-size: {FONT_SMALL}px;
}}
QLabel#watchedFilterValue {{
    background: transparent;
    color: {COLOR_TEXT};
    font-size: {FONT_SMALL}px;
    font-weight: 600;
}}
QWidget#watchedScoreRange,
QWidget#watchedYearRange {{
    background: transparent;
}}
QScrollArea {{
    border: none;
    background-color: transparent;
}}
QStatusBar {{
    background-color: {COLOR_BG};
    color: {COLOR_TEXT_SECONDARY};
    border-top: 1px solid {COLOR_BORDER};
}}
QMenu {{
    background-color: {COLOR_CARD};
    border: 1px solid {COLOR_BORDER};
    border-radius: {RADIUS_INPUT}px;
    padding: {SPACING_SMALL}px;
    color: {COLOR_TEXT};
}}
QMenu::item {{
    padding: {BUTTON_PADDING_Y}px {BUTTON_PADDING_X}px;
    border-radius: {RADIUS_BUTTON_SMALL}px;
}}
QMenu::item:selected {{
    background-color: {COLOR_ACCENT_SOFT};
}}
QSplitter::handle {{
    background-color: {COLOR_BG};
}}
QSplitter::handle:hover {{
    background-color: {COLOR_BORDER};
}}
QScrollBar:vertical {{
    background: {COLOR_BG};
    width: 10px;
    margin: {SPACING_XSMALL}px;
}}
QScrollBar::handle:vertical {{
    background: {COLOR_BORDER};
    border-radius: {RADIUS_SCROLLBAR}px;
    min-height: 28px;
}}
QScrollBar::handle:vertical:hover {{
    background: {COLOR_BORDER_HOVER};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    background: {COLOR_BG};
    height: 10px;
    margin: {SPACING_XSMALL}px;
}}
QScrollBar::handle:horizontal {{
    background: {COLOR_BORDER};
    border-radius: {RADIUS_SCROLLBAR}px;
    min-width: 28px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}
QTabWidget::pane {{
    border: none;
}}
QTabBar::tab {{
    background-color: {COLOR_CARD};
    border: 1px solid {COLOR_BORDER};
    border-radius: {RADIUS_INPUT}px;
    color: {COLOR_TEXT_SECONDARY};
    padding: 9px 16px;
    margin-right: {SPACING_SMALL}px;
}}
QTabBar::tab:selected {{
    background-color: {COLOR_CARD_ALT};
    color: {COLOR_TEXT};
    border-color: {COLOR_ACCENT};
}}
QTabBar::tab:hover {{
    background-color: {COLOR_HOVER};
    color: {COLOR_TEXT};
}}
"""


def build_score_edit_dialog_style() -> str:
    """Return the score edit dialog stylesheet."""
    return f"""
QDialog#scoreEditDialog {{
    background-color: {COLOR_BG};
    font-family: {FONT_FAMILY_QSS};
}}
QFrame#scoreEditCard {{
    background-color: {COLOR_CARD};
    border: 1px solid {COLOR_BORDER};
    border-radius: {RADIUS_CARD_LARGE}px;
}}
QLabel#scoreEditTitle {{
    background: transparent;
    color: {COLOR_TEXT};
    font-size: {FONT_DIALOG_TITLE}px;
    font-weight: 700;
}}
QLabel#scoreEditMovieTitle {{
    background: transparent;
    color: {COLOR_TEXT};
    font-size: {FONT_BASE}px;
    font-weight: 600;
}}
QLabel#scoreEditCurrent,
QLabel#scoreEditFieldLabel {{
    background: transparent;
    color: {COLOR_TEXT_SECONDARY};
    font-size: {FONT_TINY}px;
}}
QDoubleSpinBox#scoreEditSpin {{
    background-color: {COLOR_SURFACE};
    border: 1px solid {COLOR_BORDER};
    border-radius: {RADIUS_BUTTON}px;
    color: {COLOR_TEXT};
    font-size: {FONT_DIALOG_TITLE}px;
    font-weight: 600;
    padding: 7px {SPACING_MEDIUM}px;
}}
QDoubleSpinBox#scoreEditSpin:focus {{
    border: 1px solid {COLOR_ACCENT};
}}
QDoubleSpinBox#scoreEditSpin::up-button,
QDoubleSpinBox#scoreEditSpin::down-button {{
    background-color: {COLOR_CARD_ALT};
    border: none;
    width: 22px;
}}
QDoubleSpinBox#scoreEditSpin::up-button:hover,
QDoubleSpinBox#scoreEditSpin::down-button:hover {{
    background-color: {COLOR_CONTROL_HOVER};
}}
QDialogButtonBox {{
    background: transparent;
}}
QPushButton {{
    background-color: {COLOR_CARD_ALT};
    border: 1px solid {COLOR_BORDER};
    border-radius: {RADIUS_BUTTON}px;
    color: {COLOR_TEXT};
    font-size: {FONT_SMALL}px;
    font-weight: 600;
    padding: {BUTTON_PADDING_Y}px {BUTTON_PADDING_X}px;
    min-width: 92px;
}}
QPushButton:hover {{
    background-color: {COLOR_CONTROL_HOVER};
    border-color: {COLOR_BORDER_HOVER};
}}
QPushButton#scoreEditSaveButton {{
    background-color: {COLOR_ACCENT};
    border-color: {COLOR_ACCENT};
    color: {COLOR_TEXT};
}}
QPushButton#scoreEditSaveButton:hover {{
    background-color: {COLOR_ACCENT_HOVER};
    border-color: {COLOR_ACCENT_HOVER};
}}
"""


def build_delete_dialog_style() -> str:
    """Return the watched delete confirmation dialog stylesheet."""
    return f"""
QDialog#deleteRecordDialog {{
    background-color: {COLOR_BG};
    font-family: {FONT_FAMILY_QSS};
}}
QFrame#deleteRecordCard {{
    background-color: {COLOR_CARD};
    border: 1px solid {COLOR_BORDER};
    border-radius: {RADIUS_CARD_LARGE}px;
}}
QLabel#deleteRecordTitle {{
    background: transparent;
    color: {COLOR_TEXT};
    font-size: {FONT_DIALOG_TITLE}px;
    font-weight: 700;
}}
QLabel#deleteRecordWarning {{
    background: transparent;
    color: {COLOR_TEXT_SECONDARY};
    font-size: {FONT_SMALL}px;
}}
QLabel#deleteRecordPreviewLine {{
    background: transparent;
    color: {COLOR_TEXT_SOFT};
    font-size: {FONT_SMALL}px;
}}
QLabel#deleteRecordFieldLabel {{
    background: transparent;
    color: {COLOR_TEXT_SECONDARY};
    font-size: {FONT_TINY}px;
}}
QLineEdit#deleteRecordConfirmInput {{
    background-color: {COLOR_SURFACE};
    border: 1px solid {COLOR_BORDER};
    border-radius: {RADIUS_BUTTON}px;
    color: {COLOR_TEXT};
    font-size: {FONT_BASE}px;
    font-weight: 600;
    padding: 7px {SPACING_MEDIUM}px;
}}
QLineEdit#deleteRecordConfirmInput:focus {{
    border: 1px solid {COLOR_DELETE_BUTTON};
}}
QDialogButtonBox {{
    background: transparent;
}}
QPushButton {{
    background-color: {COLOR_CARD_ALT};
    border: 1px solid {COLOR_BORDER};
    border-radius: {RADIUS_BUTTON}px;
    color: {COLOR_TEXT};
    font-size: {FONT_SMALL}px;
    font-weight: 600;
    padding: {BUTTON_PADDING_Y}px {BUTTON_PADDING_X}px;
    min-width: 92px;
}}
QPushButton:hover {{
    background-color: {COLOR_CONTROL_HOVER};
    border-color: {COLOR_BORDER_HOVER};
}}
QPushButton#deleteRecordConfirmButton {{
    background-color: {COLOR_DELETE_BUTTON};
    border-color: {COLOR_DELETE_BUTTON};
    color: {COLOR_TEXT};
}}
QPushButton#deleteRecordConfirmButton:hover {{
    background-color: {COLOR_DELETE_BUTTON_HOVER};
    border-color: {COLOR_DELETE_BUTTON_HOVER};
}}
QPushButton#deleteRecordConfirmButton:disabled {{
    background-color: {COLOR_CARD_ALT};
    border-color: {COLOR_BORDER};
    color: {COLOR_TEXT_MUTED};
}}
"""


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
QLabel#genrePill {{
    background-color: {COLOR_CARD_ALT};
    border: 1px solid {COLOR_BORDER};
    border-radius: {RADIUS_CHIP}px;
    padding: 7px 12px;
    color: {COLOR_TEXT_CHIP};
    font-size: {FONT_BASE}px;
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


def build_analytics_style(
    *,
    font_base: int = FONT_BASE,
    font_page_title: int = FONT_TITLE,
    font_subtitle: int = FONT_BASE,
    font_section_title: int = FONT_SECTION,
    font_summary_label: int = FONT_SMALL,
    font_summary_value: int = FONT_KPI_VALUE,
    font_insight: int = FONT_BASE,
    font_dense_count: int = FONT_BASE,
    font_dense_score: int = FONT_DENSE_SCORE,
    font_same_score_titles: int = FONT_SMALL,
    font_fallback: int = FONT_BASE,
) -> str:
    """Return the analytics tab stylesheet."""
    return f"""
QWidget#analyticsRoot {{
    background-color: {COLOR_BG};
    color: {COLOR_TEXT};
    font-family: {FONT_FAMILY_QSS};
    font-size: {font_base}px;
}}
QWidget#analyticsBarRow {{
    background: transparent;
}}
QLabel#analyticsTitle {{
    background: transparent;
    color: {COLOR_TEXT};
    font-size: {font_page_title}px;
    font-weight: 700;
}}
QLabel#analyticsSubtitle {{
    background: transparent;
    color: {COLOR_TEXT_SECONDARY};
    font-size: {font_subtitle}px;
}}
QFrame#summaryCard,
QFrame#analyticsSection,
QFrame#insightCard,
QFrame#sameScoreCard {{
    background-color: {COLOR_CARD};
    border: 1px solid {COLOR_BORDER};
    border-radius: {RADIUS_CARD}px;
}}
QLabel#summaryLabel,
QLabel#barLabel,
QLabel#denseLabel,
QLabel#denseTitles {{
    background: transparent;
    color: {COLOR_TEXT_SECONDARY};
    font-size: {font_summary_label}px;
}}
QLabel#insightText {{
    background: transparent;
    color: {COLOR_TEXT_SOFT};
    font-size: {font_insight}px;
}}
QLabel#summaryValue {{
    background: transparent;
    color: {COLOR_TEXT};
    font-size: {font_summary_value}px;
    font-weight: 700;
}}
QLabel#sectionTitle {{
    background: transparent;
    color: {COLOR_TEXT};
    font-size: {font_section_title}px;
    font-weight: 700;
}}
QFrame#barTrack {{
    background-color: {COLOR_CARD_ALT};
    border-radius: {RADIUS_BAR}px;
}}
QFrame#barFill {{
    background-color: {COLOR_ACCENT};
    border-radius: {RADIUS_BAR}px;
}}
QLabel#barCount,
QLabel#denseCount {{
    background: transparent;
    color: {COLOR_TEXT};
    font-size: {font_dense_count}px;
    font-weight: 600;
}}
QLabel#denseScore {{
    background: transparent;
    color: {COLOR_ACCENT};
    font-size: {font_dense_score}px;
    font-weight: 700;
}}
QFrame#denseScoreBadge {{
    background-color: {COLOR_CARD_ALT};
    border: 1px solid {COLOR_BORDER};
    border-radius: {RADIUS_BUTTON}px;
}}
QLabel#sameScoreTitles {{
    background: transparent;
    color: {COLOR_TEXT_SOFT};
    font-size: {font_same_score_titles}px;
}}
QLabel#analyticsFallback {{
    background: transparent;
    color: {COLOR_TEXT_SOFT};
    font-size: {font_fallback}px;
    padding: 8px 2px;
}}
"""

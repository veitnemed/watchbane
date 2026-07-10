"""QSS for shared form controls and range sliders."""

from __future__ import annotations

from desktop.theme.tokens import *  # noqa: F403


def build_form_controls_style() -> str:
    """Return stylesheet for inputs, combos, spinboxes and range sliders."""
    return f"""
QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox {{
    background-color: {FILM_SURFACE_1};
    border: 1px solid {FILM_BORDER_WEAK};
    border-radius: {px(RADIUS_INPUT)}px;
    padding: {px(INPUT_PADDING_Y)}px {px(INPUT_PADDING_X)}px;
    color: {FILM_TEXT};
    font-size: {font_px(FONT_BASE)}px;
    selection-background-color: {FILM_ACCENT_DIM};
}}
QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus, QSpinBox:focus {{
    border: 1px solid {FILM_ACCENT};
}}
QDoubleSpinBox::up-button,
QDoubleSpinBox::down-button,
QSpinBox::up-button,
QSpinBox::down-button {{
    background-color: {FILM_SURFACE_2};
    border: none;
    width: {px(16)}px;
}}
QDoubleSpinBox::up-button:hover,
QDoubleSpinBox::down-button:hover,
QSpinBox::up-button:hover,
QSpinBox::down-button:hover {{
    background-color: {FILM_ACCENT_DIM};
}}
QComboBox::drop-down {{
    border: none;
    width: {px(24)}px;
}}
QComboBox QAbstractItemView {{
    background-color: {FILM_SURFACE_1};
    border: 1px solid {FILM_BORDER_WEAK};
    color: {FILM_TEXT};
    selection-background-color: {FILM_ACCENT_DIM};
}}
QWidget#watchedScoreRange,
QWidget#watchedYearRange,
QWidget#candidateSearchYearRange,
QWidget#candidateSearchKpScoreRange,
QWidget#candidateSearchImdbScoreRange,
QWidget#candidateSearchTmdbScoreRange,
QWidget#candidateSearchKpVotesRange,
QWidget#candidateSearchImdbVotesRange,
QWidget#candidateSearchTmdbVotesRange {{
    background: transparent;
}}
QLabel#candidateSearchYearRangeLabel,
QLabel#candidateSearchFilterValue {{
    background: transparent;
    color: {COLOR_TEXT};
    font-size: {font_px(FONT_BASE + 1)}px;
    font-weight: 600;
}}
QComboBox#candidateSearchCriteria,
QSpinBox#candidateSearchYearMin,
QSpinBox#candidateSearchYearMax,
QSpinBox#candidateSearchTopN {{
    background-color: {COLOR_SURFACE};
    border: 1px solid {COLOR_BORDER};
    border-radius: {px(RADIUS_INPUT)}px;
    color: {COLOR_TEXT};
    font-size: {font_px(FONT_BASE)}px;
    padding: {px(6)}px {px(10)}px;
    min-height: {px(34)}px;
}}
QComboBox#candidateSearchCriteria:focus,
QSpinBox#candidateSearchYearMin:focus,
QSpinBox#candidateSearchYearMax:focus,
QSpinBox#candidateSearchTopN:focus {{
    border: 1px solid {COLOR_FOCUS_BORDER};
}}
QCheckBox#candidateSearchOnlyComplete,
QCheckBox#candidateSearchOnlyUnwatched,
QCheckBox#candidateSearchHideHidden {{
    background: transparent;
    color: {COLOR_TEXT_SECONDARY};
    font-size: {font_px(FONT_BASE)}px;
    spacing: {px(8)}px;
    min-height: {px(29)}px;
}}
QCheckBox#candidateSearchOnlyComplete::indicator,
QCheckBox#candidateSearchOnlyUnwatched::indicator,
QCheckBox#candidateSearchHideHidden::indicator {{
    width: {px(18)}px;
    height: {px(18)}px;
}}
"""

"""QSS builders for dialogs (score edit, delete, add title)."""

from __future__ import annotations

from desktop.theme.tokens import *  # noqa: F403

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
    border-radius: {px(RADIUS_CARD_LARGE)}px;
}}
QLabel#scoreEditTitle {{
    background: transparent;
    color: {COLOR_TEXT};
    font-size: {font_px(FONT_DIALOG_TITLE)}px;
    font-weight: 700;
}}
QLabel#scoreEditMovieTitle {{
    background: transparent;
    color: {COLOR_TEXT};
    font-size: {font_px(FONT_BASE)}px;
    font-weight: 600;
}}
QLabel#scoreEditCurrent,
QLabel#scoreEditFieldLabel {{
    background: transparent;
    color: {COLOR_TEXT_SECONDARY};
    font-size: {font_px(FONT_TINY)}px;
}}
QDialogButtonBox {{
    background: transparent;
}}
QPushButton {{
    background-color: {COLOR_CARD_ALT};
    border: 1px solid {COLOR_BORDER};
    border-radius: {px(RADIUS_BUTTON)}px;
    color: {COLOR_TEXT};
    font-size: {font_px(FONT_SMALL)}px;
    font-weight: 600;
    padding: {px(BUTTON_PADDING_Y)}px {px(BUTTON_PADDING_X)}px;
    min-width: {px(92)}px;
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
    border-radius: {px(RADIUS_CARD_LARGE)}px;
}}
QScrollArea#deleteRecordPreviewScroll,
QWidget#deleteRecordPreviewContent {{
    background: transparent;
    border: none;
}}
QLabel#deleteRecordTitle {{
    background: transparent;
    color: {COLOR_TEXT};
    font-size: {font_px(FONT_DIALOG_TITLE)}px;
    font-weight: 700;
}}
QLabel#deleteRecordWarning {{
    background: transparent;
    color: {COLOR_TEXT_SECONDARY};
    font-size: {font_px(FONT_SMALL)}px;
}}
QLabel#deleteRecordPreviewLine {{
    background: transparent;
    color: {COLOR_TEXT_SOFT};
    font-size: {font_px(FONT_SMALL)}px;
}}
QLabel#deleteRecordFieldLabel {{
    background: transparent;
    color: {COLOR_TEXT_SECONDARY};
    font-size: {font_px(FONT_TINY)}px;
}}
QLineEdit#deleteRecordConfirmInput {{
    background-color: {COLOR_SURFACE};
    border: 1px solid {COLOR_BORDER};
    border-radius: {px(RADIUS_BUTTON)}px;
    color: {COLOR_TEXT};
    font-size: {font_px(FONT_BASE)}px;
    font-weight: 600;
    padding: {px(7)}px {px(SPACING_MEDIUM)}px;
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
    border-radius: {px(RADIUS_BUTTON)}px;
    color: {COLOR_TEXT};
    font-size: {font_px(FONT_SMALL)}px;
    font-weight: 600;
    padding: {px(BUTTON_PADDING_Y)}px {px(BUTTON_PADDING_X)}px;
    min-width: {px(92)}px;
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


def build_add_title_dialog_style() -> str:
    """Return the add-title wizard dialog stylesheet."""
    return f"""
QDialog#addTitleDialog, QDialog#addTitleSearchDialog, QDialog#addTitlePreviewDialog {{
    background-color: {COLOR_BG};
    font-family: {FONT_FAMILY_QSS};
}}
QLabel#addTitleHeader {{
    background: transparent;
    color: {COLOR_TEXT};
    font-size: {font_px(FONT_DIALOG_TITLE)}px;
    font-weight: 700;
}}
QLabel#addTitleSubtitle {{
    background: transparent;
    color: {COLOR_TEXT_SECONDARY};
    font-size: {font_px(FONT_SMALL)}px;
}}
QFrame#addTitleSearchPanel {{
    background-color: {COLOR_CARD};
    border: 1px solid {COLOR_BORDER};
    border-radius: {px(RADIUS_CARD_LARGE)}px;
}}
QLineEdit#addTitleSearchInput, QComboBox#addTitleCountryCombo, QComboBox#addTitleMediaTypeCombo {{
    background-color: {COLOR_SURFACE};
    border: 1px solid {COLOR_BORDER};
    border-radius: {px(RADIUS_BUTTON)}px;
    color: {COLOR_TEXT};
    font-size: {font_px(FONT_BASE)}px;
    padding: {px(7)}px {px(SPACING_MEDIUM)}px;
    min-height: {px(18)}px;
}}
QLineEdit#addTitleSearchInput:focus, QComboBox#addTitleCountryCombo:focus, QComboBox#addTitleMediaTypeCombo:focus {{
    border: 1px solid {COLOR_FOCUS_BORDER};
}}
QPushButton#addTitleSearchButton {{
    background-color: {COLOR_ADD_BUTTON};
    border: 1px solid {COLOR_ADD_BUTTON_BORDER};
    border-top-color: {COLOR_ADD_BUTTON_TOP};
    color: {COLOR_TEXT};
    font-size: {font_px(FONT_BASE)}px;
    font-weight: 600;
    padding: {px(8)}px {px(16)}px;
    border-radius: {px(RADIUS_BUTTON)}px;
}}
QPushButton#addTitleSearchButton:hover {{
    background-color: {COLOR_ADD_BUTTON_HOVER};
    border-color: {COLOR_ADD_BUTTON_HOVER};
    border-top-color: {COLOR_ADD_BUTTON_HOVER_TOP};
}}
QPushButton#addTitleSearchButton:disabled {{
    background-color: {COLOR_CARD_ALT};
    border-color: {COLOR_BORDER};
    color: {COLOR_TEXT_MUTED};
}}
QProgressBar#addTitleProgress {{
    background-color: {COLOR_SURFACE};
    border: 1px solid {COLOR_BORDER};
    border-radius: {px(RADIUS_BUTTON)}px;
    color: {COLOR_TEXT_SOFT};
    font-size: {font_px(FONT_TINY)}px;
    text-align: center;
    min-height: {px(18)}px;
}}
QProgressBar#addTitleProgress::chunk {{
    background-color: {COLOR_ACCENT};
    border-radius: {px(RADIUS_BUTTON)}px;
}}
QLabel#addTitleStatus {{
    background: transparent;
    color: {COLOR_TEXT_SOFT};
    font-size: {font_px(FONT_SMALL)}px;
}}
QLabel#addTitleWarning {{
    background-color: {COLOR_CARD_ALT};
    border: 1px solid {COLOR_BORDER};
    border-radius: {px(RADIUS_BUTTON)}px;
    color: {COLOR_TEXT_SOFT};
    font-size: {font_px(FONT_SMALL)}px;
    padding: {px(8)}px {px(10)}px;
}}
QFrame#addTitlePreviewCard {{
    background-color: {COLOR_CARD};
    border: 1px solid {COLOR_BORDER};
    border-radius: {px(RADIUS_CARD_LARGE)}px;
}}
QScrollArea#addTitlePreviewScroll {{
    background: transparent;
    border: none;
}}
QWidget#addTitleCompactPreviewCard {{
    background: transparent;
}}
QLabel#addTitleCompactTitle {{
    background: transparent;
    color: {COLOR_TEXT};
    font-size: {font_px(24)}px;
    font-weight: 700;
}}
QLabel#addTitleCompactMeta {{
    background: transparent;
    color: {COLOR_TEXT_SECONDARY};
    font-size: {font_px(FONT_BASE)}px;
}}
QLabel#addTitleCompactGenrePill {{
    background-color: {COLOR_SURFACE};
    border: 1px solid {COLOR_BORDER};
    border-radius: {px(15)}px;
    color: {COLOR_TEXT_SOFT};
    font-size: {font_px(FONT_SMALL)}px;
    padding: 0 {px(16)}px;
}}
QLabel#addTitleConfirmHint {{
    background: transparent;
    color: {COLOR_TEXT_SECONDARY};
    font-size: {font_px(FONT_SMALL)}px;
}}
QLabel#addTitleFieldLabel {{
    background: transparent;
    color: {COLOR_TEXT_SECONDARY};
    font-size: {font_px(FONT_SMALL)}px;
}}
QSpinBox#addTitleYearSpin {{
    background-color: {COLOR_SURFACE};
    border: 1px solid {COLOR_BORDER};
    border-radius: {px(RADIUS_BUTTON)}px;
    color: {COLOR_TEXT};
    font-size: {font_px(FONT_BASE)}px;
    padding: {px(4)}px {px(8)}px;
}}
QPushButton#addTitleConfirmButton {{
    background-color: {COLOR_ACCENT};
    border: 1px solid {COLOR_ACCENT};
    color: {COLOR_TEXT};
    font-size: {font_px(FONT_BASE)}px;
    font-weight: 700;
    padding: {px(9)}px {px(18)}px;
    border-radius: {px(RADIUS_BUTTON)}px;
}}
QPushButton#addTitleConfirmButton:hover {{
    background-color: {COLOR_ACCENT_HOVER};
    border-color: {COLOR_ACCENT_HOVER};
}}
QPushButton#addTitleConfirmButton:disabled {{
    background-color: {COLOR_CARD_ALT};
    border-color: {COLOR_BORDER};
    color: {COLOR_TEXT_MUTED};
}}
QPushButton#addTitleSecondaryButton {{
    background-color: {COLOR_CARD_ALT};
    border: 1px solid {COLOR_BORDER};
    color: {COLOR_TEXT_SOFT};
    font-size: {font_px(FONT_BASE)}px;
    padding: {px(8)}px {px(14)}px;
    border-radius: {px(RADIUS_BUTTON)}px;
}}
QPushButton#addTitleSecondaryButton:hover {{
    background-color: {COLOR_CONTROL_HOVER};
    border-color: {COLOR_BORDER_HOVER};
}}
"""

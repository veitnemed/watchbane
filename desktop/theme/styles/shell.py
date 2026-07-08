"""QSS for main window chrome: tabs, scrollbars, status bar, menus."""

from __future__ import annotations

from desktop.theme.shell_layout import MAIN_TAB_PANE_TOP_LIFT_PX
from desktop.theme.tokens import *  # noqa: F403


def build_shell_style() -> str:
    """Return stylesheet for application shell widgets."""
    return f"""
QMainWindow, QWidget {{
    background-color: {FILM_WINDOW_BG};
    color: {FILM_TEXT};
    font-family: {FONT_FAMILY_QSS};
    font-size: {font_px(FONT_APP)}px;
}}
QScrollArea {{
    border: none;
    background-color: transparent;
}}
QStatusBar {{
    background-color: {FILM_WINDOW_BG};
    color: {FILM_TEXT_SUBTLE};
    border-top: 1px solid {FILM_BORDER_WEAK};
}}
QMenu {{
    background-color: {FILM_SURFACE_1};
    border: 1px solid {FILM_BORDER_WEAK};
    border-radius: {px(RADIUS_INPUT)}px;
    padding: {px(SPACING_SMALL)}px;
    color: {FILM_TEXT};
}}
QMenu::item {{
    padding: {px(BUTTON_PADDING_Y)}px {px(BUTTON_PADDING_X)}px;
    border-radius: {px(RADIUS_BUTTON_SMALL)}px;
}}
QMenu::item:selected {{
    background-color: {FILM_ACCENT_DIM};
}}
QSplitter::handle {{
    background-color: {FILM_WINDOW_BG};
}}
QSplitter::handle:hover {{
    background-color: {FILM_BORDER_WEAK};
}}
QScrollBar:vertical {{
    background: {FILM_SCROLLBAR_BG};
    width: {px(10)}px;
    margin: {px(SPACING_XSMALL)}px;
}}
QScrollBar::handle:vertical {{
    background: {FILM_SCROLLBAR_HANDLE};
    border-radius: {px(RADIUS_SCROLLBAR)}px;
    min-height: {px(28)}px;
}}
QScrollBar::handle:vertical:hover {{
    background: {FILM_SCROLLBAR_HANDLE_HOVER};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    background: {FILM_SCROLLBAR_BG};
    height: {px(10)}px;
    margin: {px(SPACING_XSMALL)}px;
}}
QScrollBar::handle:horizontal {{
    background: {FILM_SCROLLBAR_HANDLE};
    border-radius: {px(RADIUS_SCROLLBAR)}px;
    min-width: {px(28)}px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}
QTabWidget::pane {{
    border: none;
}}
QTabWidget#mainTabs::pane {{
    top: -{MAIN_TAB_PANE_TOP_LIFT_PX}px;
}}
QTabBar::tab {{
    background-color: {FILM_SURFACE_1};
    border: 1px solid {FILM_BORDER_WEAK};
    border-radius: {control_px(RADIUS_INPUT)}px;
    color: {FILM_TEXT_SUBTLE};
    font-size: {font_px(FONT_BASE)}px;
    font-weight: 600;
    padding: {control_px(BUTTON_PADDING_Y)}px {control_px(BUTTON_PADDING_X)}px;
    min-height: {control_px(34)}px;
    margin-right: {px(SPACING_SMALL)}px;
}}
QTabBar::tab:selected {{
    background-color: {FILM_ACCENT_DIM};
    color: {FILM_ACCENT_HOVER};
    border-color: {FILM_ACCENT};
}}
QTabBar::tab:hover {{
    background-color: {FILM_SURFACE_2};
    color: {FILM_TEXT};
}}
"""

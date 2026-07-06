"""QSS for main window chrome: tabs, scrollbars, status bar, menus."""

from __future__ import annotations

from desktop.theme.shell_layout import MAIN_TAB_PANE_TOP_LIFT_PX
from desktop.theme.tokens import *  # noqa: F403


def build_shell_style() -> str:
    """Return stylesheet for application shell widgets."""
    return f"""
QMainWindow, QWidget {{
    background-color: {COLOR_BG};
    color: {COLOR_TEXT};
    font-family: {FONT_FAMILY_QSS};
    font-size: {font_px(FONT_APP)}px;
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
    border-radius: {px(RADIUS_INPUT)}px;
    padding: {px(SPACING_SMALL)}px;
    color: {COLOR_TEXT};
}}
QMenu::item {{
    padding: {px(BUTTON_PADDING_Y)}px {px(BUTTON_PADDING_X)}px;
    border-radius: {px(RADIUS_BUTTON_SMALL)}px;
}}
QMenu::item:selected {{
    background-color: {COLOR_SELECTED_BG};
}}
QSplitter::handle {{
    background-color: {COLOR_BG};
}}
QSplitter::handle:hover {{
    background-color: {COLOR_BORDER};
}}
QScrollBar:vertical {{
    background: transparent;
    width: {px(10)}px;
    margin: {px(SPACING_XSMALL)}px;
}}
QScrollBar::handle:vertical {{
    background: {COLOR_BORDER_HOVER};
    border-radius: {px(RADIUS_SCROLLBAR)}px;
    min-height: {px(28)}px;
}}
QScrollBar::handle:vertical:hover {{
    background: {COLOR_ACCENT_SOFT};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: {px(10)}px;
    margin: {px(SPACING_XSMALL)}px;
}}
QScrollBar::handle:horizontal {{
    background: {COLOR_BORDER_HOVER};
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
    background-color: {COLOR_CARD};
    border: 1px solid {COLOR_BORDER};
    border-radius: {control_px(RADIUS_INPUT)}px;
    color: {COLOR_TEXT_SECONDARY};
    font-size: {font_px(FONT_BASE)}px;
    font-weight: 600;
    padding: {control_px(BUTTON_PADDING_Y)}px {control_px(BUTTON_PADDING_X)}px;
    min-height: {control_px(34)}px;
    margin-right: {px(SPACING_SMALL)}px;
}}
QTabBar::tab:selected {{
    background-color: {COLOR_ACCENT_SOFT};
    color: {COLOR_ACCENT_HOVER};
    border-color: {COLOR_BORDER_ACTIVE};
}}
QTabBar::tab:hover {{
    background-color: {COLOR_HOVER};
    color: {COLOR_TEXT};
}}
"""

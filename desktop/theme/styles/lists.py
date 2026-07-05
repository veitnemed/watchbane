"""QSS for shared list widgets."""

from __future__ import annotations

from desktop.theme.tokens import *  # noqa: F403


def build_lists_style() -> str:
    """Return stylesheet for QListWidget list panels."""
    return f"""
QListWidget {{
    background-color: {COLOR_CARD};
    border: 1px solid {COLOR_BORDER};
    border-radius: {px(RADIUS_CARD)}px;
    padding: {px(SPACING_SMALL)}px;
    outline: none;
}}
QListWidget::item {{
    padding: 0;
    border: none;
    color: {COLOR_TEXT_SOFT};
    margin: {px(1)}px 0;
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
"""

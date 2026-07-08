"""QSS for shared list widgets."""

from __future__ import annotations

from desktop.theme.tokens import *  # noqa: F403


def build_lists_style() -> str:
    """Return stylesheet for QListWidget list panels."""
    return f"""
QListWidget {{
    background-color: {FILM_SURFACE_0};
    border: 1px solid {FILM_BORDER_WEAK};
    border-radius: {px(RADIUS_CARD)}px;
    padding: {px(SPACING_SMALL)}px;
    outline: none;
}}
QListWidget::item {{
    padding: 0;
    border: none;
    color: {FILM_TEXT_SUBTLE};
    margin: {px(1)}px 0;
    background: transparent;
}}
QListWidget::item:selected {{
    background: transparent;
    color: {FILM_TEXT};
}}
QListWidget::item:selected:!active {{
    background: transparent;
    color: {FILM_TEXT};
}}
QListWidget::item:hover {{
    background: transparent;
}}
"""

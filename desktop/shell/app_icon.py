"""Application icon helpers for the desktop shell."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtGui import QIcon


APP_ICON_PATH = Path(__file__).resolve().parents[1] / "images" / "logos" / "main_icon.ico"


def build_app_icon() -> QIcon:
    """Return the configured desktop application icon."""
    if not APP_ICON_PATH.exists():
        return QIcon()
    return QIcon(str(APP_ICON_PATH))


def apply_app_icon(app) -> QIcon:
    """Apply the desktop application icon to QApplication-like objects."""
    icon = build_app_icon()
    if not icon.isNull():
        app.setWindowIcon(icon)
    return icon

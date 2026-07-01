"""Desktop application bootstrap and entry point."""

from __future__ import annotations

import sys

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication

from desktop.shell.main_window import WatchedMoviesWindow
from desktop.theme import FONT_FAMILY
from diagnostics.gui_event_log import log_event, log_exception, start_gui_event_log_if_enabled
from storage.runtime import ensure_runtime_data_layout


def _prepare_webengine() -> None:
    """Prepare Qt WebEngine before QApplication is created."""
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True)
    try:
        from PyQt6 import QtWebEngineWidgets  # noqa: F401
    except ImportError:
        pass


def main() -> None:
    _prepare_webengine()
    ensure_runtime_data_layout()
    log_path = start_gui_event_log_if_enabled()
    if log_path is not None:
        log_event("app.bootstrap.runtime_ready", log_path=str(log_path))
    app = QApplication(sys.argv)
    app.setFont(QFont(FONT_FAMILY, 10))
    try:
        window = WatchedMoviesWindow()
        window.show()
        log_event("app.window.shown")
        exit_code = app.exec()
        log_event("app.exit", exit_code=exit_code)
        sys.exit(exit_code)
    except Exception as error:
        log_exception("app.error", error)
        raise

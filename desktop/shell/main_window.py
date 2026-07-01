"""Main window shell: tab bar, status bar and cross-tab coordination."""

from __future__ import annotations

from PyQt6.QtWidgets import QMainWindow, QTabWidget

from desktop.shell.tabs import build_main_tabs
from desktop.theme import build_app_style

DARK_STYLE = build_app_style()


class WatchedMoviesWindow(QMainWindow):
    """Main window shell: tab bar, status bar and cross-tab coordination."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Terminal Movies Learn Desktop")
        self.resize(1180, 720)
        self.setStyleSheet(DARK_STYLE)
        self.statusBar().showMessage("")

        tabs = QTabWidget()
        self.setCentralWidget(tabs)
        self._main_tabs = tabs
        self._tab_registry, self._tabs_context = build_main_tabs(
            tabs,
            self,
            on_status_message=self._show_status_message,
        )

    def _show_status_message(self, message: str, timeout_ms: int) -> None:
        self.statusBar().showMessage(message, timeout_ms)

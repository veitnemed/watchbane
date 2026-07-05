"""Main window shell: tab bar, status bar and cross-tab coordination."""

from __future__ import annotations

from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QApplication, QDialog, QMainWindow, QTabWidget

from desktop.settings import SettingsDialog
from desktop.shell.app_icon import build_app_icon
from desktop.shell.tabs import build_main_tabs
from desktop.theme import build_app_style
from desktop.theme.scaling import scale_px

MAIN_WINDOW_BASE_WIDTH = 1180
MAIN_WINDOW_BASE_HEIGHT = 720
MAIN_WINDOW_SCREEN_MARGIN = 80


def scaled_main_window_size() -> tuple[int, int]:
    """Return initial main window size for the current application UI scale."""
    width = scale_px(MAIN_WINDOW_BASE_WIDTH)
    height = scale_px(MAIN_WINDOW_BASE_HEIGHT)
    screen = QApplication.primaryScreen()
    if screen is None:
        return width, height
    available = screen.availableGeometry()
    safe_margin = scale_px(MAIN_WINDOW_SCREEN_MARGIN)
    return (
        min(width, max(1, available.width() - safe_margin)),
        min(height, max(1, available.height() - safe_margin)),
    )


class WatchedMoviesWindow(QMainWindow):
    """Main window shell: tab bar, status bar and cross-tab coordination."""

    def __init__(self, initial_size: tuple[int, int] | None = None) -> None:
        super().__init__()
        self.setWindowTitle("Watchbane")
        self.setWindowIcon(build_app_icon())
        self.resize(*(initial_size or scaled_main_window_size()))
        self.setStyleSheet(build_app_style())
        self.statusBar().showMessage("")
        self._build_settings_menu()

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

    def _build_settings_menu(self) -> None:
        settings_action = QAction("Настройки", self)
        settings_action.setObjectName("settingsAction")
        settings_action.triggered.connect(self._open_settings_dialog)
        self.menuBar().addAction(settings_action)
        self._settings_action = settings_action

    def _open_settings_dialog(self) -> None:
        dialog = SettingsDialog(self)
        dialog.settingsSaved.connect(lambda message: self._show_status_message(message, 8000))
        result = dialog.exec()
        if result == QDialog.DialogCode.Accepted and dialog.restart_message:
            self._show_status_message(dialog.restart_message, 8000)

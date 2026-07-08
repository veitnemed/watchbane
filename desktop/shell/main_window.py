"""Main window shell: tab bar, status bar and cross-tab coordination."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QMainWindow, QStackedWidget, QTabWidget

from candidates import service as candidate_service
from desktop.onboarding import OnboardingAutofillDialog
from desktop.settings.app_settings import get_persisted_interface_language
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

        root_stack = QStackedWidget()
        root_stack.setObjectName("mainRootStack")
        self.setCentralWidget(root_stack)
        self._root_stack = root_stack

        tabs = QTabWidget()
        tabs.setObjectName("mainTabs")
        root_stack.addWidget(tabs)
        self._main_tabs = tabs
        self._tab_registry, self._tabs_context = build_main_tabs(
            tabs,
            self,
            on_status_message=self._show_status_message,
        )
        self._onboarding_view: OnboardingAutofillDialog | None = None

    def _show_status_message(self, message: str, timeout_ms: int) -> None:
        self.statusBar().showMessage(message, timeout_ms)

    def maybe_show_onboarding_autofill(self) -> None:
        """Show first-run deterministic candidate-pool autofill wizard when needed."""
        if candidate_service.should_show_onboarding_autofill() is False:
            return
        onboarding = OnboardingAutofillDialog(
            ui_language=get_persisted_interface_language(),
            parent=self,
        )
        onboarding.setModal(False)
        onboarding.setWindowFlag(Qt.WindowType.Widget, True)

        def finish_onboarding(_code: int) -> None:
            self._root_stack.setCurrentWidget(self._main_tabs)
            self._tabs_context.focus_candidates()
            self._root_stack.removeWidget(onboarding)
            onboarding.deleteLater()
            self._onboarding_view = None

        onboarding.completed.connect(lambda _result: self._tabs_context.focus_candidates())
        onboarding.finished.connect(finish_onboarding)
        self._onboarding_view = onboarding
        self._root_stack.addWidget(onboarding)
        self._root_stack.setCurrentWidget(onboarding)
        onboarding.show()

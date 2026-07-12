"""Main window shell: tab bar, status bar and cross-tab coordination."""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QApplication, QMainWindow, QStackedWidget, QTabWidget

from candidates import service as candidate_service
from diagnostics.gui_event_log import log_event
from desktop.i18n import tr
from desktop.onboarding import OnboardingAutofillDialog
from desktop.onboarding.worker import PoolReplenishWorker
from desktop.settings.app_settings import get_persisted_interface_language, load_app_settings
from desktop.shell.app_icon import build_app_icon
from desktop.shell.tabs import build_main_tabs
from desktop.startup import TmdbStartupGateView
from desktop.theme import build_app_style
from desktop.theme.scaling import scale_px

MAIN_WINDOW_BASE_WIDTH = 1180
MAIN_WINDOW_BASE_HEIGHT = 720
MAIN_WINDOW_SCREEN_MARGIN = 80
POOL_AUTO_REFILL_CHECK_INTERVAL_MS = 15 * 60 * 1000


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
        self._tmdb_gate_view: TmdbStartupGateView | None = None
        self._tmdb_gate_passed = False
        self._pool_refill_worker: PoolReplenishWorker | None = None
        self._pool_refill_timer = QTimer(self)
        self._pool_refill_timer.setInterval(POOL_AUTO_REFILL_CHECK_INTERVAL_MS)
        self._pool_refill_timer.timeout.connect(self.maybe_start_pool_auto_refill)
        self._pool_refill_timer.start()

    def _show_status_message(self, message: str, timeout_ms: int) -> None:
        self.statusBar().showMessage(message, timeout_ms)

    def _refresh_candidate_pool_views(self) -> None:
        session = self._tabs_context.candidate_session
        reload_from_pool = getattr(session, "reload_from_pool", None)
        if callable(reload_from_pool):
            reload_from_pool(force=True)
        else:
            session.invalidate_pool_cache()
        refresh_filters = getattr(self._tabs_context, "refresh_candidate_filters", None)
        if callable(refresh_filters):
            refresh_filters()

    def maybe_start_pool_auto_refill(self) -> None:
        """Start a quiet background pool top-up when the pool runs low."""
        if self._tmdb_gate_passed is False or self._tmdb_gate_view is not None:
            return
        if self._pool_refill_worker is not None or self._onboarding_view is not None:
            return
        if load_app_settings().auto_pool_refill is False:
            return
        try:
            view = candidate_service.get_pool_replenish_view()
        except Exception:
            return
        if view.get("needs_replenish") is not True:
            return

        worker = PoolReplenishWorker(self)

        def on_refill_finished(result: object) -> None:
            data = result if isinstance(result, dict) else {}
            created = int(data.get("created_count") or 0)
            if created > 0:
                self._refresh_candidate_pool_views()
                self._show_status_message(tr("pool.auto_refill.done").format(count=created), 8000)
            log_event("pool.auto_refill.finished", created_count=created)
            self._pool_refill_worker = None

        def on_refill_failed(message: str) -> None:
            self._show_status_message(tr("pool.auto_refill.failed"), 8000)
            log_event("pool.auto_refill.failed", error=message)
            self._pool_refill_worker = None

        worker.finished_with_result.connect(on_refill_finished)
        worker.failed.connect(on_refill_failed)
        self._pool_refill_worker = worker
        self._show_status_message(tr("pool.auto_refill.started"), 6000)
        log_event("pool.auto_refill.started", pool_size=view.get("pool_size"), missing=view.get("missing"))
        worker.start()

    def maybe_show_onboarding_autofill(self) -> None:
        """Show first-run deterministic candidate-pool autofill wizard when needed."""
        if self._tmdb_gate_passed is False:
            return
        if candidate_service.should_show_onboarding_autofill() is False:
            return
        onboarding = OnboardingAutofillDialog(
            ui_language=get_persisted_interface_language(),
            parent=self,
        )
        onboarding.setModal(False)
        onboarding.setWindowFlag(Qt.WindowType.Widget, True)

        def refresh_candidate_pool_views() -> None:
            self._refresh_candidate_pool_views()

        def mark_candidate_pool_changed(_result: object) -> None:
            refresh_candidate_pool_views()
            log_event("onboarding.view.completed")

        def finish_onboarding(_code: int) -> None:
            refresh_candidate_pool_views()
            self._root_stack.setCurrentWidget(self._main_tabs)
            self._tabs_context.focus_candidates()
            log_event("onboarding.view.finished", result_code=_code)
            self._root_stack.removeWidget(onboarding)
            onboarding.deleteLater()
            self._onboarding_view = None

        onboarding.completed.connect(mark_candidate_pool_changed)
        onboarding.finished.connect(finish_onboarding)
        self._onboarding_view = onboarding
        self._root_stack.addWidget(onboarding)
        self._root_stack.setCurrentWidget(onboarding)
        onboarding.show()
        log_event("onboarding.view.shown")

    def maybe_show_tmdb_startup_gate(self) -> None:
        """Block main UI until TMDb network and credentials are ready."""
        from apis.tmdb_api import reload_tmdb_env
        from apis.tmdb_connectivity import evaluate_tmdb_startup_readiness

        readiness = evaluate_tmdb_startup_readiness()
        if readiness.get("ready") is True:
            self._tmdb_gate_passed = True
            log_event("startup.tmdb_gate.skipped")
            self.maybe_show_onboarding_autofill()
            return

        gate = TmdbStartupGateView(parent=self)
        gate.setWindowFlag(Qt.WindowType.Widget, True)

        def finish_gate() -> None:
            reload_tmdb_env()
            self._tmdb_gate_passed = True
            self._root_stack.setCurrentWidget(self._main_tabs)
            log_event("startup.tmdb_gate.passed")
            self._root_stack.removeWidget(gate)
            gate.deleteLater()
            self._tmdb_gate_view = None
            self.maybe_show_onboarding_autofill()

        gate.passed.connect(finish_gate)
        self._tmdb_gate_view = gate
        self._root_stack.addWidget(gate)
        self._root_stack.setCurrentWidget(gate)
        gate.show()
        log_event("startup.tmdb_gate.shown", error=readiness.get("error"))

"""Main window shell: tab bar, status bar and cross-tab coordination."""

from __future__ import annotations

from time import monotonic

from PyQt6.QtCore import QCoreApplication, QEvent, QRect, QThread, Qt, QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication, QMainWindow, QStackedWidget, QStyle, QTabWidget

from candidates import service as candidate_service
from common.release import APP_NAME, APP_VERSION
from config import app_settings_store
from diagnostics.gui_event_log import log_event
from desktop.i18n import tr
from desktop.onboarding import OnboardingAutofillDialog
from desktop.settings.app_settings import get_persisted_interface_language
from desktop.shell.app_icon import build_app_icon
from desktop.shell.tabs import build_main_tabs
from desktop.startup import TmdbStartupGateView
from desktop.theme import FONT_APP, FONT_FAMILY, build_app_style
from desktop.theme.scaling import font_px, get_ui_scale, scale_px
from desktop.theme.ui_modules import ensure_scaled_main_tab_modules

MAIN_WINDOW_BASE_WIDTH = 1180
MAIN_WINDOW_BASE_HEIGHT = 720
MAIN_WINDOW_SCREEN_MARGIN = 80
WINDOW_GEOMETRY_SETTINGS_KEY = "desktop_main_window_state_v1"
WORKER_SHUTDOWN_TIMEOUT_MS = 12_000
_ORPHANED_THREADS: list[QThread] = []


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
        self.setWindowTitle(f"{APP_NAME} {APP_VERSION}")
        self.setWindowIcon(build_app_icon())
        self._persist_window_geometry = initial_size is None
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
        self._main_tabs_language = get_persisted_interface_language()
        self._main_tabs_ui_scale = get_ui_scale()
        self._tab_registry, self._tabs_context = build_main_tabs(
            tabs,
            self,
            on_status_message=self._show_status_message,
        )
        QTimer.singleShot(0, self._sync_responsive_tabs)
        self._onboarding_view: OnboardingAutofillDialog | None = None
        self._tmdb_gate_view: TmdbStartupGateView | None = None
        self._tmdb_gate_passed = False
        self._tmdb_local_mode = False
        self._tmdb_gate_timer = QTimer(self)
        self._tmdb_gate_timer.setSingleShot(True)
        self._tmdb_gate_timer.timeout.connect(self.maybe_show_tmdb_startup_gate)
        self._restored_geometry_needs_frame_clamp = False
        if self._persist_window_geometry:
            self._restored_geometry_needs_frame_clamp = self._restore_window_geometry()

    def showEvent(self, event) -> None:  # noqa: N802 - Qt override
        super().showEvent(event)
        if self._restored_geometry_needs_frame_clamp:
            self._restored_geometry_needs_frame_clamp = False
            QTimer.singleShot(0, self._clamp_restored_frame_to_screen)

    @staticmethod
    def _screen_for_rect(rect: QRect):
        screens = QApplication.screens()
        if not screens:
            return None
        intersections = [
            rect.intersected(screen.availableGeometry())
            for screen in screens
        ]
        areas = [
            intersection.width() * intersection.height()
            if intersection.isValid()
            else 0
            for intersection in intersections
        ]
        if max(areas, default=0) > 0:
            return screens[areas.index(max(areas))]
        return QApplication.primaryScreen() or screens[0]

    def _clamp_restored_frame_to_screen(self) -> None:
        if self.isVisible() is False or self.isMaximized() or self.isFullScreen():
            return
        frame = self.frameGeometry()
        screen = self._screen_for_rect(frame)
        if screen is None:
            return
        available = screen.availableGeometry()
        overflow_width = max(0, frame.width() - available.width())
        overflow_height = max(0, frame.height() - available.height())
        if overflow_width or overflow_height:
            self.resize(
                max(1, self.width() - overflow_width),
                max(1, self.height() - overflow_height),
            )
            frame = self.frameGeometry()
        target_x = min(
            max(frame.x(), available.left()),
            available.right() - frame.width() + 1,
        )
        target_y = min(
            max(frame.y(), available.top()),
            available.bottom() - frame.height() + 1,
        )
        self.move(
            self.x() + target_x - frame.x(),
            self.y() + target_y - frame.y(),
        )

    def _restore_window_geometry(self) -> bool:
        try:
            payload = app_settings_store.load_sqlite_settings_dict().get(
                WINDOW_GEOMETRY_SETTINGS_KEY
            )
        except Exception as error:
            log_event("app.window.geometry_load_failed", error=str(error))
            return False
        if isinstance(payload, dict) is False:
            return False
        try:
            saved = QRect(
                int(payload["x"]),
                int(payload["y"]),
                int(payload["width"]),
                int(payload["height"]),
            )
        except (KeyError, TypeError, ValueError, OverflowError):
            return False
        if saved.isValid() is False:
            return False

        screen = self._screen_for_rect(saved)
        if screen is not None:
            available = screen.availableGeometry()
            title_bar_height = max(
                0,
                self.style().pixelMetric(QStyle.PixelMetric.PM_TitleBarHeight),
            )
            minimum = self.minimumSizeHint()
            width = min(max(saved.width(), minimum.width()), available.width())
            maximum_height = max(1, available.height() - title_bar_height)
            height = min(max(saved.height(), minimum.height()), maximum_height)
            x = min(max(saved.x(), available.left()), available.right() - width + 1)
            client_top = available.top() + title_bar_height
            y = min(max(saved.y(), client_top), available.bottom() - height + 1)
            saved = QRect(x, y, width, height)

        self.setGeometry(saved)
        if payload.get("maximized") is True:
            self.setWindowState(self.windowState() | Qt.WindowState.WindowMaximized)
        return True

    def _save_window_geometry(self) -> None:
        geometry = (
            self.normalGeometry()
            if self.isMaximized() or self.isMinimized() or self.isFullScreen()
            else self.geometry()
        )
        if geometry.isValid() is False:
            return
        payload = {
            "x": geometry.x(),
            "y": geometry.y(),
            "width": geometry.width(),
            "height": geometry.height(),
            "maximized": self.isMaximized() or self.isFullScreen(),
        }
        try:
            app_settings_store.save_sqlite_settings_dict(
                {WINDOW_GEOMETRY_SETTINGS_KEY: payload}
            )
        except Exception as error:
            log_event("app.window.geometry_save_failed", error=str(error))

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt override
        self._tmdb_gate_timer.stop()
        if self._persist_window_geometry:
            self._save_window_geometry()
        super().closeEvent(event)

    def shutdown_background_workers(self) -> None:
        """Cancel and join child QThreads before the Qt object tree is destroyed."""
        started = monotonic()
        self._tmdb_gate_timer.stop()
        registry = getattr(self, "_tab_registry", None)
        for spec in getattr(registry, "_specs", {}).values():
            prepare = getattr(spec.view, "prepare_for_shutdown", None)
            if callable(prepare):
                prepare()

        thread_objects = list(self.findChildren(QThread))
        workers = [worker for worker in thread_objects if worker.isRunning()]
        if workers:
            log_event("app.worker_shutdown.begin", worker_count=len(workers))
            for worker in workers:
                cancel = getattr(worker, "cancel", None)
                if callable(cancel):
                    try:
                        cancel()
                    except Exception as error:
                        log_event(
                            "app.worker_shutdown.cancel_failed",
                            worker=worker.metaObject().className(),
                            error=str(error),
                        )
                worker.requestInterruption()

            deadline = monotonic() + WORKER_SHUTDOWN_TIMEOUT_MS / 1000.0
            timed_out: list[QThread] = []
            for worker in workers:
                remaining_ms = max(0, int((deadline - monotonic()) * 1000))
                if remaining_ms <= 0 or worker.wait(remaining_ms) is False:
                    timed_out.append(worker)
            for worker in timed_out:
                try:
                    worker.setParent(None)
                except RuntimeError:
                    continue
                if worker not in _ORPHANED_THREADS:
                    _ORPHANED_THREADS.append(worker)
                worker.finished.connect(
                    lambda worker=worker: _ORPHANED_THREADS.remove(worker)
                    if worker in _ORPHANED_THREADS
                    else None
                )
                log_event(
                    "app.worker_shutdown.timeout",
                    worker=worker.metaObject().className(),
                )
            log_event(
                "app.worker_shutdown.end",
                worker_count=len(workers),
                timed_out_count=len(timed_out),
                elapsed_ms=round((monotonic() - started) * 1000, 1),
            )

        # QThread.finished callbacks (including deleteLater) can still be queued when
        # QApplication.exec() has returned. Drain them before Python/Qt teardown.
        app = QApplication.instance()
        if app is not None and thread_objects:
            app.processEvents()
            for worker in thread_objects:
                try:
                    QCoreApplication.sendPostedEvents(
                        worker,
                        QEvent.Type.DeferredDelete,
                    )
                except RuntimeError:
                    # The queued finished callback already deleted this worker.
                    continue
            app.processEvents()
        log_event(
            "app.shutdown.complete",
            elapsed_ms=round((monotonic() - started) * 1000, 1),
        )

    def schedule_tmdb_startup_gate(self, delay_ms: int = 250) -> None:
        """Schedule the startup probe on a window-owned timer that shutdown can cancel."""
        self._tmdb_gate_timer.start(max(0, int(delay_ms)))

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt override
        super().resizeEvent(event)
        self._sync_responsive_tabs(self.width())

    def _sync_responsive_tabs(self, available_width: int | None = None) -> None:
        tabs_context = getattr(self, "_tabs_context", None)
        if tabs_context is None:
            return
        width = self.width() if available_width is None else available_width
        for view_name in ("watched_tab_view", "candidate_list_view"):
            view = getattr(tabs_context, view_name, None)
            update_layout = getattr(view, "_update_responsive_layout", None)
            if callable(update_layout):
                update_layout(width)

    def _rebuild_main_tabs_if_settings_changed(self) -> bool:
        """Recreate main tabs after onboarding changes language or UI scale."""
        language = get_persisted_interface_language()
        ui_scale = get_ui_scale()
        language_changed = language != self._main_tabs_language
        scale_changed = ui_scale != self._main_tabs_ui_scale
        if language_changed is False and scale_changed is False:
            return False

        if scale_changed:
            ensure_scaled_main_tab_modules()
            app = QApplication.instance()
            if app is not None:
                app.setFont(QFont(FONT_FAMILY, font_px(FONT_APP)))
            self.setStyleSheet(build_app_style())

        tabs = QTabWidget()
        tabs.setObjectName("mainTabs")
        self._root_stack.addWidget(tabs)
        try:
            tab_registry, tabs_context = build_main_tabs(
                tabs,
                self,
                on_status_message=self._show_status_message,
            )
        except Exception:
            self._root_stack.removeWidget(tabs)
            tabs.deleteLater()
            raise

        old_tabs = self._main_tabs
        self._main_tabs = tabs
        self._main_tabs_language = language
        self._main_tabs_ui_scale = ui_scale
        self._tab_registry = tab_registry
        self._tabs_context = tabs_context
        if self._root_stack.currentWidget() is old_tabs:
            self._root_stack.setCurrentWidget(tabs)
        old_tabs.hide()
        self._root_stack.removeWidget(old_tabs)
        old_tabs.deleteLater()
        self.statusBar().clearMessage()
        QTimer.singleShot(0, self._sync_responsive_tabs)
        return True

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

    def maybe_show_onboarding_autofill(self) -> bool:
        """Show first-run deterministic candidate-pool autofill wizard when needed."""
        if self._tmdb_gate_passed is False:
            return False
        if candidate_service.should_show_onboarding_autofill() is False:
            return False
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
            self._rebuild_main_tabs_if_settings_changed()
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
        return True

    def maybe_show_tmdb_startup_gate(self) -> None:
        """Block main UI until TMDb network and credentials are ready."""
        from app.use_cases.tmdb_title_add import reload_tmdb_runtime

        delayed_gate = True
        try:
            gate = TmdbStartupGateView(parent=self, autostart=False)
        except TypeError:
            # Compatibility for lightweight injected/test gates.
            delayed_gate = False
            gate = TmdbStartupGateView(parent=self)
        gate.setWindowFlag(Qt.WindowType.Widget, True)

        def close_gate(*, reload_runtime: bool, start_onboarding: bool) -> None:
            if reload_runtime:
                reload_tmdb_runtime()
            self._tmdb_gate_passed = True
            self._root_stack.setCurrentWidget(self._main_tabs)
            self._root_stack.removeWidget(gate)
            gate.deleteLater()
            self._tmdb_gate_view = None
            onboarding_started = start_onboarding and self.maybe_show_onboarding_autofill()
            if onboarding_started is False:
                # C1-01: land on Recommendations when startup skips onboarding.
                focus_candidates = getattr(self._tabs_context, "focus_candidates", None)
                if callable(focus_candidates):
                    focus_candidates()
                else:
                    activate_current = getattr(self._tab_registry, "activate_current", None)
                    if callable(activate_current):
                        activate_current()

        def finish_gate() -> None:
            log_event("startup.tmdb_gate.passed")
            self._tmdb_local_mode = False
            close_gate(reload_runtime=True, start_onboarding=True)

        def continue_locally() -> None:
            log_event("startup.tmdb_gate.local_mode")
            self._tmdb_local_mode = True
            close_gate(reload_runtime=False, start_onboarding=False)

        def show_gate() -> None:
            if self._tmdb_gate_view is not gate:
                return
            self._root_stack.setCurrentWidget(gate)
            gate.show()
            log_event("startup.tmdb_gate.shown")

        gate.passed.connect(finish_gate)
        local_mode_signal = getattr(gate, "localModeRequested", None)
        if local_mode_signal is not None:
            local_mode_signal.connect(continue_locally)
        attention_signal = getattr(gate, "attentionRequired", None)
        if attention_signal is not None:
            attention_signal.connect(show_gate)
        self._tmdb_gate_view = gate
        self._root_stack.addWidget(gate)
        if delayed_gate and attention_signal is not None:
            gate.start_readiness_probe()
        else:
            show_gate()

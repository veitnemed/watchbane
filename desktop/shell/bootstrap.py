"""Desktop application bootstrap and entry point."""

from __future__ import annotations

from dataclasses import asdict
import os
import sys

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication

from desktop.settings import APP_UI_SCALE_ENV, AppSettings, get_persisted_ui_scale, load_app_settings
from desktop.shell.app_icon import apply_app_icon
from desktop.theme import FONT_FAMILY
from desktop.theme.scaling import (
    font_px,
    get_channel_scale,
    get_ui_scale,
    set_ui_scale,
)
from desktop.theme.ui_tuning import get_scale_tuning
from diagnostics.gui_event_log import log_event, log_exception, start_gui_event_log_if_enabled
from storage.runtime import ensure_runtime_data_layout


def _prepare_webengine() -> None:
    """Prepare Qt WebEngine before QApplication is created."""
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True)
    try:
        from PyQt6 import QtWebEngineWidgets  # noqa: F401
    except ImportError:
        pass


def _geometry_diagnostics(geometry) -> dict[str, int] | None:
    if geometry is None:
        return None
    return {
        "x": geometry.x(),
        "y": geometry.y(),
        "width": geometry.width(),
        "height": geometry.height(),
    }


def log_startup_scale_diagnostics(
    app: QApplication,
    *,
    persisted_settings: AppSettings,
    active_ui_scale: float,
    requested_initial_size: tuple[int, int],
) -> None:
    """Log lightweight scale/DPI diagnostics for GUI sessions."""
    font = app.font()
    screen = app.primaryScreen()
    logical_dpi = None
    device_pixel_ratio = None
    available_geometry = None
    if screen is not None:
        logical_dpi = screen.logicalDotsPerInch()
        device_pixel_ratio = screen.devicePixelRatio()
        available_geometry = _geometry_diagnostics(screen.availableGeometry())

    log_event(
        "app.ui_scale.diagnostics",
        persisted_ui_scale=persisted_settings.ui_scale,
        persisted_scale_settings=asdict(persisted_settings),
        active_process_ui_scale=active_ui_scale,
        active_ui_scale=get_ui_scale(),
        scale_tuning=get_scale_tuning(),
        effective_scales={
            channel: get_channel_scale(channel)
            for channel in ("ui", "font", "layout", "control", "list", "detail", "poster")
        },
        scale_env_overrides={"ui_scale": APP_UI_SCALE_ENV}
        if os.environ.get(APP_UI_SCALE_ENV) not in (None, "")
        else {},
        app_font_family=font.family(),
        app_font_point_size=font.pointSize(),
        primary_screen_logical_dpi=logical_dpi,
        primary_screen_device_pixel_ratio=device_pixel_ratio,
        primary_screen_available_geometry=available_geometry,
        requested_initial_window_size={
            "width": requested_initial_size[0],
            "height": requested_initial_size[1],
        },
    )


def main() -> None:
    _prepare_webengine()
    ensure_runtime_data_layout()
    persisted_settings = load_app_settings()
    active_ui_scale = get_persisted_ui_scale()
    set_ui_scale(active_ui_scale)
    log_path = start_gui_event_log_if_enabled()
    if log_path is not None:
        log_event("app.bootstrap.runtime_ready", log_path=str(log_path))
    app = QApplication(sys.argv)
    apply_app_icon(app)
    app.setFont(QFont(FONT_FAMILY, font_px(10)))
    try:
        from desktop.shell.main_window import WatchedMoviesWindow, scaled_main_window_size

        requested_initial_size = scaled_main_window_size()
        log_startup_scale_diagnostics(
            app,
            persisted_settings=persisted_settings,
            active_ui_scale=active_ui_scale,
            requested_initial_size=requested_initial_size,
        )
        window = WatchedMoviesWindow(initial_size=requested_initial_size)
        window.show()
        log_event("app.window.shown")
        exit_code = app.exec()
        log_event("app.exit", exit_code=exit_code)
        sys.exit(exit_code)
    except Exception as error:
        log_exception("app.error", error)
        raise

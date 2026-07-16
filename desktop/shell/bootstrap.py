"""Desktop application bootstrap and entry point."""

from __future__ import annotations

from dataclasses import asdict
import os
import sys

from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication

from common.release import APP_DISPLAY_NAME, APP_NAME, APP_VERSION
from desktop.settings import APP_UI_SCALE_ENV, AppSettings, get_persisted_ui_scale, load_app_settings
from desktop.storage_errors import is_storage_write_error, storage_write_error_message
from desktop.shell.app_icon import apply_app_icon
from desktop.theme import FONT_APP, FONT_FAMILY
from desktop.theme.scaling import (
    font_px,
    get_channel_scale,
    get_ui_scale,
    set_ui_scale,
)
from desktop.theme.ui_tuning import get_scale_tuning
from diagnostics.gui_event_log import log_event, log_exception, start_gui_event_log_if_enabled
from storage.runtime import ensure_runtime_data_layout


def _show_database_recovery_dialog(error) -> None:
    """Offer an explicit, validated restore without ever opening the main UI."""
    from pathlib import Path
    import sqlite3

    from PyQt6.QtWidgets import QFileDialog, QMessageBox

    from app.use_cases.sqlite_recovery import (
        format_startup_database_error,
        restore_selected_startup_backup,
    )
    from config import constant

    dialog = QMessageBox()
    dialog.setIcon(QMessageBox.Icon.Critical)
    dialog.setWindowTitle("Watchbane — база данных")
    dialog.setText(format_startup_database_error(error))
    restore_button = dialog.addButton(
        "Выбрать резервную копию…",
        QMessageBox.ButtonRole.ActionRole,
    )
    dialog.addButton("Закрыть", QMessageBox.ButtonRole.RejectRole)
    dialog.exec()
    if dialog.clickedButton() is not restore_button:
        return

    selected, _filter = QFileDialog.getOpenFileName(
        None,
        "Выберите резервную копию Watchbane",
        str(Path(constant.BACKUP_DIR)),
        "SQLite backup (*.sqlite3 *.sqlite *.db)",
    )
    if not selected:
        return
    answer = QMessageBox.question(
        None,
        "Подтвердите восстановление",
        "Выбранная копия будет проверена, затем заменит текущую базу. "
        "Повреждённый файл уже сохранён для диагностики. Продолжить?",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No,
    )
    if answer != QMessageBox.StandardButton.Yes:
        return
    try:
        restore_selected_startup_backup(selected, error)
    except (OSError, ValueError, sqlite3.DatabaseError) as restore_error:
        QMessageBox.critical(
            None,
            "Восстановление не выполнено",
            "Резервная копия не прошла проверку или недоступна. "
            "Текущая база не заменена.\n\n"
            f"Причина: {restore_error}",
        )
        return
    QMessageBox.information(
        None,
        "Восстановление завершено",
        "Резервная копия восстановлена. Перезапустите Watchbane.",
    )


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
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_DISPLAY_NAME)
    app.setApplicationVersion(APP_VERSION)
    from desktop.shell.single_instance import SingleInstanceGuard, show_already_running_warning

    try:
        instance_guard = SingleInstanceGuard()
    except Exception as error:
        if is_storage_write_error(error):
            from PyQt6.QtWidgets import QMessageBox

            QMessageBox.warning(None, "Watchbane", storage_write_error_message())
            return
        if getattr(sys, "frozen", False):
            from PyQt6.QtWidgets import QMessageBox

            QMessageBox.critical(
                None,
                "Watchbane",
                "Не удалось запустить Watchbane из-за внутренней ошибки. "
                "Перезапустите приложение; подробности сохранены в диагностике, если она включена.",
            )
            return
        raise
    if instance_guard.acquire() is False:
        show_already_running_warning()
        return

    try:
        dev_reset = None
        profile_reset_result = None
        try:
            from storage.runtime import apply_dev_startup_reset_from_env
            from storage import profile_reset

            profile_reset_result = profile_reset.process_pending_profile_reset()
            if profile_reset.profile_selection_required():
                from desktop.startup.profile_selector import ProfileSelectionDialog
                from storage import profiles

                selector = ProfileSelectionDialog()
                if selector.exec() != selector.DialogCode.Accepted:
                    return
                selected_profile = selector.selected_profile
                if selected_profile in (None, ""):
                    return
                profiles.set_active_profile(selected_profile)
                profile_reset.clear_profile_selection_required()
            dev_reset = apply_dev_startup_reset_from_env()
        except Exception as error:
            log_exception("app.dev_startup_reset.error", error)
            raise
        ensure_runtime_data_layout()
        persisted_settings = load_app_settings()
        active_ui_scale = get_persisted_ui_scale()
        set_ui_scale(active_ui_scale)
        from desktop.theme.ui_modules import ensure_scaled_ui_modules

        ensure_scaled_ui_modules()
        log_path = start_gui_event_log_if_enabled()
        if log_path is not None:
            log_event("app.bootstrap.runtime_ready", log_path=str(log_path))
            if dev_reset and dev_reset.get("applied"):
                log_event("app.bootstrap.dev_startup_reset", **dev_reset)
            if profile_reset_result and profile_reset_result.get("applied"):
                log_event("app.bootstrap.profile_reset", **profile_reset_result)
        apply_app_icon(app)
        app.setFont(QFont(FONT_FAMILY, font_px(FONT_APP)))
        from desktop.shell.main_window import WatchedMoviesWindow, scaled_main_window_size

        requested_initial_size = scaled_main_window_size()
        log_startup_scale_diagnostics(
            app,
            persisted_settings=persisted_settings,
            active_ui_scale=active_ui_scale,
            requested_initial_size=requested_initial_size,
        )
        window = WatchedMoviesWindow()
        try:
            window.show()
            window.schedule_tmdb_startup_gate()
            log_event("app.window.shown")
            exit_code = app.exec()
        finally:
            window.shutdown_background_workers()
        log_event("app.exit", exit_code=exit_code)
        sys.exit(exit_code)
    except Exception as error:
        log_exception("app.error", error)
        from app.use_cases.sqlite_recovery import is_startup_database_error

        if is_startup_database_error(error):
            _show_database_recovery_dialog(error)
            return
        if is_storage_write_error(error):
            from PyQt6.QtWidgets import QMessageBox

            QMessageBox.warning(None, "Watchbane", storage_write_error_message())
            return
        raise
    finally:
        instance_guard.release()

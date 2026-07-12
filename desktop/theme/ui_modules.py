"""Import/reload helpers for modules that freeze scaled UI values at import time."""

from __future__ import annotations

import importlib
import sys

_SCALED_UI_MODULE_NAMES = (
    "desktop.theme.layout",
    "desktop.shared.detail.profiles",
    "desktop.theme.shell_layout",
    "desktop.theme.styles.shell",
    "desktop.watched.add_title.constants",
    "desktop.analytics.charts",
    "desktop.analytics.constants",
)

_SCALED_MAIN_TAB_MODULE_NAMES = (
    "desktop.watched.sidebar",
    "desktop.watched.tab",
    "desktop.candidates.filters_view",
    "desktop.candidates.list_view",
    "desktop.candidates",
    "desktop.settings.tab_view",
    "desktop.shell.tabs",
)


def ensure_scaled_ui_modules() -> None:
    """Import or reload UI modules after the active ui_scale is set."""
    for module_name in _SCALED_UI_MODULE_NAMES:
        module = sys.modules.get(module_name)
        if module is None:
            importlib.import_module(module_name)
        else:
            importlib.reload(module)

    _clear_list_thumb_cache()


def ensure_scaled_main_tab_modules() -> None:
    """Refresh loaded main-tab consumers after changing scale at runtime."""
    ensure_scaled_ui_modules()
    for module_name in _SCALED_MAIN_TAB_MODULE_NAMES:
        module = sys.modules.get(module_name)
        if module is not None:
            importlib.reload(module)


def _clear_list_thumb_cache() -> None:
    try:
        from desktop.shared.detail import list_delegate
    except ImportError:
        return
    list_delegate._thumb_pixmap_cache.clear()

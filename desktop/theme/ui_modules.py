"""Import/reload helpers for modules that freeze scaled UI values at import time."""

from __future__ import annotations

import importlib
import sys

_SCALED_UI_MODULE_NAMES = (
    "desktop.shared.detail.profiles",
    "desktop.theme.shell_layout",
    "desktop.watched.add_title.constants",
    "desktop.analytics.charts",
    "desktop.analytics.constants",
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


def _clear_list_thumb_cache() -> None:
    try:
        from desktop.shared.detail import list_delegate
    except ImportError:
        return
    list_delegate._thumb_pixmap_cache.clear()

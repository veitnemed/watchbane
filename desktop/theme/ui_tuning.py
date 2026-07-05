"""Local visual scale tuning for desktop theme channels."""

from __future__ import annotations

import importlib
import math
import re
from typing import Any

SCALE_TUNING_MIN = 0.50
SCALE_TUNING_MAX = 2.00
SCALE_TUNING_DEFAULT = 1.00

SCALE_TUNING = {
    "ui": 1.00,
    "font": 1.00,
    "layout": 1.00,
    "control": 1.00,
    "list": 1.00,
    "detail": 1.00,
    "poster": 1.00,
}


def _normalize_scale_tuning_value(value: Any) -> float:
    if isinstance(value, bool) or value in (None, ""):
        return SCALE_TUNING_DEFAULT

    if isinstance(value, str):
        value = value.strip()
        if value == "":
            return SCALE_TUNING_DEFAULT
        if re.fullmatch(r"[+-]?(\d+(\.\d+)?|\.\d+)", value) is None:
            return SCALE_TUNING_DEFAULT

    try:
        scale = float(value)
    except (TypeError, ValueError):
        return SCALE_TUNING_DEFAULT

    if math.isfinite(scale) is False:
        return SCALE_TUNING_DEFAULT

    return max(SCALE_TUNING_MIN, min(SCALE_TUNING_MAX, scale))


def _load_local_overrides() -> dict[str, Any]:
    try:
        local_tuning = importlib.import_module("desktop.theme.local_ui_tuning")
    except ModuleNotFoundError as error:
        if error.name == "desktop.theme.local_ui_tuning":
            return {}
        raise

    overrides = getattr(local_tuning, "SCALE_TUNING_OVERRIDES", {})
    if isinstance(overrides, dict) is False:
        return {}
    return overrides


def get_scale_tuning() -> dict[str, float]:
    """Return validated scale tuning, including optional local overrides."""
    tuning = dict(SCALE_TUNING)
    for key, value in _load_local_overrides().items():
        if key in tuning:
            tuning[key] = value
    return {key: _normalize_scale_tuning_value(value) for key, value in tuning.items()}


__all__ = [
    "SCALE_TUNING",
    "SCALE_TUNING_DEFAULT",
    "SCALE_TUNING_MAX",
    "SCALE_TUNING_MIN",
    "get_scale_tuning",
]

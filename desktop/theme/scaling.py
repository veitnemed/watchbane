"""Central application-level UI scaling helpers."""

from __future__ import annotations

from desktop.settings.app_settings import normalize_ui_scale

_ui_scale = 1.0


def set_ui_scale(value) -> None:
    """Set the process-wide application UI scale."""
    global _ui_scale
    _ui_scale = normalize_ui_scale(value)


def get_ui_scale() -> float:
    """Return the current process-wide application UI scale."""
    return _ui_scale


def scale_float(value: int | float) -> float:
    """Scale a numeric value using the current application UI scale."""
    return float(value) * _ui_scale


def _minimum_preserving_round(value: int | float) -> int:
    if value == 0:
        return 0
    scaled = int(round(scale_float(value)))
    if scaled == 0:
        return 1 if value > 0 else -1
    return scaled


def scale_px(value: int | float) -> int:
    """Scale geometry values to integer pixels."""
    return _minimum_preserving_round(value)


def scale_font(value: int | float) -> int:
    """Scale font point/pixel values to an integer."""
    return _minimum_preserving_round(value)

"""Central application-level UI scaling helpers."""

from __future__ import annotations

from desktop.settings.app_settings import AppSettings, normalize_ui_scale
from desktop.theme.ui_tuning import get_scale_tuning

_ui_scale = 1.0
_scale_tuning = get_scale_tuning()


def set_app_scale_settings(settings: AppSettings) -> None:
    """Compatibility helper: apply the persisted app UI scale."""
    set_ui_scale(getattr(settings, "ui_scale", 1.0))


def get_app_scale_settings() -> AppSettings:
    """Compatibility helper: return the active persisted app UI scale."""
    return AppSettings(ui_scale=_ui_scale)


def set_ui_scale(value) -> None:
    """Set the process-wide application UI scale."""
    global _ui_scale
    _ui_scale = normalize_ui_scale(value)


def get_ui_scale() -> float:
    """Return the current process-wide application UI scale."""
    return _ui_scale


def get_channel_scale(channel: str) -> float:
    """Return the effective application scale for a visual channel."""
    if channel not in _scale_tuning:
        raise ValueError(f"Unknown scale channel: {channel}")

    ui_tuning = _scale_tuning["ui"]
    if channel == "ui":
        return _ui_scale * ui_tuning
    return _ui_scale * ui_tuning * _scale_tuning[channel]


def get_scale(channel: str = "layout") -> float:
    """Compatibility alias for channel scale lookup."""
    return get_channel_scale(channel)


def scale_float(value: int | float, channel: str = "layout") -> float:
    """Scale a numeric value using the effective channel scale."""
    return float(value) * get_channel_scale(channel)


def _minimum_preserving_round(value: int | float, channel: str = "layout") -> int:
    if value == 0:
        return 0
    scaled_value = scale_float(value, channel=channel)
    scaled = int(round(scaled_value))
    if scaled == 0:
        return 1 if scaled_value > 0 else -1
    return scaled


def scale_px(value: int | float, channel: str = "layout") -> int:
    """Scale geometry values to integer pixels."""
    return _minimum_preserving_round(value, channel=channel)


def scale_font(value: int | float) -> int:
    """Scale font point/pixel values to an integer."""
    if value == 0:
        return 0
    scaled_value = scale_float(value, channel="font")
    scaled = int(scaled_value + 0.5) if scaled_value > 0 else int(scaled_value - 0.5)
    if scaled == 0:
        return 1 if scaled_value > 0 else -1
    return scaled


def layout_px(value: int | float) -> int:
    return scale_px(value, channel="layout")


def control_px(value: int | float) -> int:
    return scale_px(value, channel="control")


def list_px(value: int | float) -> int:
    return scale_px(value, channel="list")


def detail_px(value: int | float) -> int:
    return scale_px(value, channel="detail")


def poster_px(value: int | float) -> int:
    return scale_px(value, channel="poster")


def font_px(value: int | float) -> int:
    return scale_font(value)

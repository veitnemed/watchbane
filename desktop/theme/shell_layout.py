"""Compatibility re-exports for scaled shell layout constants."""

from __future__ import annotations

import importlib

from desktop.theme import layout as _layout

_layout = importlib.reload(_layout)

__all__ = _layout.__all__
globals().update({name: getattr(_layout, name) for name in __all__})

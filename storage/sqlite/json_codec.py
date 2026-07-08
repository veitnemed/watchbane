"""Canonical JSON codec helpers for SQLite payload columns."""

from __future__ import annotations

import json
from typing import Any


def dumps_json(value: Any) -> str:
    """Serialize canonical JSON for SQLite payload columns."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def loads_json(value: str | None, default: Any = None) -> Any:
    if value in (None, ""):
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default

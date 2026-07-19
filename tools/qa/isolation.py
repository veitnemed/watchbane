"""Isolation helpers for recommendation QA audits (no product path freezing).

This module may import ``config.app_paths`` only. It must never import
``config.constant`` — that freezes ``APP_DATA_DIR`` at import time.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

from config.app_paths import DATA_DIR_ENV, resolve_runtime_root

ISOLATION_MARKER_NAME = ".watchbane_qa_isolated"
ISOLATION_META_NAME = "isolation_meta.json"


class IsolationError(ValueError):
    """Raised when a runtime root is unsafe for QA audits."""


def real_watchbane_profile_root(
    *,
    environ: Mapping[str, str] | None = None,
    platform: str | None = None,
    home: str | Path | None = None,
) -> Path:
    """Return the real user Watchbane profile root (ignores WATCHBANE_DATA_DIR)."""
    values = dict(os.environ if environ is None else environ)
    values.pop(DATA_DIR_ENV, None)
    return resolve_runtime_root(environ=values, platform=platform, home=home)


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def assert_runtime_is_isolated(
    runtime_root: Path | str,
    *,
    real_root: Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> Path:
    """Validate runtime_root is safe; return resolved absolute path.

    Rejects missing/empty roots and any path equal to, parent of, or inside the
    real Watchbane user profile.
    """
    text = str(runtime_root if runtime_root is not None else "").strip()
    if text in {"", ".", "./"}:
        raise IsolationError(
            f"Runtime root is required. Set --runtime-root / {DATA_DIR_ENV}; "
            "refusing to use the real Watchbane profile."
        )
    resolved = Path(text).expanduser().resolve()
    real = (real_root or real_watchbane_profile_root(environ=environ)).resolve()

    if resolved == real:
        raise IsolationError(
            f"Refusing runtime root {resolved}: equals real Watchbane profile {real}."
        )
    if resolved == real.parent or _is_relative_to(real, resolved):
        raise IsolationError(
            f"Refusing runtime root {resolved}: it contains or is the parent of "
            f"real Watchbane profile {real}."
        )
    if _is_relative_to(resolved, real):
        raise IsolationError(
            f"Refusing runtime root {resolved}: inside real Watchbane profile {real}."
        )
    return resolved


def write_isolation_marker(runtime_root: Path, *, meta: dict | None = None) -> Path:
    """Create isolation marker (+ optional meta JSON) under runtime_root."""
    runtime_root.mkdir(parents=True, exist_ok=True)
    marker = runtime_root / ISOLATION_MARKER_NAME
    marker.write_text("watchbane-qa-isolated\n", encoding="utf-8")
    if meta is not None:
        (runtime_root / ISOLATION_META_NAME).write_text(
            json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return marker


def apply_isolated_data_dir(runtime_root: Path) -> Path:
    """Set WATCHBANE_DATA_DIR to resolved isolated root; return resolved path."""
    resolved = assert_runtime_is_isolated(runtime_root)
    os.environ[DATA_DIR_ENV] = str(resolved)
    return resolved


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

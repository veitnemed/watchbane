"""Shared JSON persistence helpers for candidate repositories."""

from __future__ import annotations

from pathlib import Path

from storage.files import dump_json_atomic as _dump_json_atomic


def ensure_parent_dir(path: str) -> None:
    """Create the parent directory for legacy callers."""
    parent = Path(path).parent
    if str(parent):
        parent.mkdir(parents=True, exist_ok=True)


def dump_json_atomic(path: str, payload: dict) -> None:
    """Write a JSON mapping through a same-directory temp file, then replace."""
    _dump_json_atomic(path, payload, trailing_newline=True)

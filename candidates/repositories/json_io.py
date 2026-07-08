"""Shared JSON persistence helpers for candidate repositories."""

from __future__ import annotations

import json
import os
from pathlib import Path


def ensure_parent_dir(path: str) -> None:
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)


def dump_json_atomic(path: str, payload: dict) -> None:
    """Write a JSON mapping through a same-directory temp file, then replace."""
    target = Path(path)
    ensure_parent_dir(str(target))
    temp_path = target.with_name(f"{target.name}.tmp")

    try:
        with temp_path.open("w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=4)
            file.write("\n")
        os.replace(temp_path, target)
    except Exception:
        try:
            temp_path.unlink()
        except OSError:
            pass
        raise

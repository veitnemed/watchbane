"""Manual TMDb ID overrides for watched metadata lookup."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from candidates.models.keys import title_identity_key
from config import constant

DEFAULT_TMDB_CACHE_DIR = Path(constant.CACHE_DIR) / "tmdb"
DEFAULT_WATCHED_TMDB_OVERRIDES_JSON = DEFAULT_TMDB_CACHE_DIR / "watched_tmdb_overrides.json"


def load_watched_tmdb_overrides(path: str | Path | None = None) -> dict:
    """Load manual TMDb overrides or return empty dict when file is missing."""
    overrides_path = DEFAULT_WATCHED_TMDB_OVERRIDES_JSON if path is None else Path(path)
    if overrides_path.is_file() is False:
        return {}

    try:
        with open(overrides_path, "r", encoding="utf-8-sig") as file:
            payload = json.load(file)
    except (OSError, json.JSONDecodeError):
        return {}

    return payload if isinstance(payload, dict) else {}


def get_watched_tmdb_override(
    title: str,
    year: Any,
    overrides: dict | None = None,
) -> dict | None:
    """Return one manual override entry for title/year identity, if configured."""
    cache = load_watched_tmdb_overrides() if overrides is None else overrides
    identity = title_identity_key({"title": title, "year": year})
    entry = cache.get(identity)
    if isinstance(entry, dict) is False:
        return None

    tmdb_id = entry.get("tmdb_id")
    if tmdb_id in (None, ""):
        return None

    return entry

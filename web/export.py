"""Read-only export helpers built from already loaded project data."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from candidates.models.keys import title_identity_key
from common.cards import build_watched_movie_card, resolve_watched_description

DEFAULT_WATCHED_MOVIES_JSON = Path("web") / "data" / "watched_movies.json"


def iter_dataset_movies(data):
    """Return dataset records from dict or list payloads."""
    if isinstance(data, dict):
        return list(data.values())
    return data if isinstance(data, list) else list(data or [])


def build_export_lookup_cache(meta=None, pool_by_identity=None) -> dict:
    """Build one lookup map for meta and candidate pool descriptions."""
    if meta is None:
        from storage.data import load_meta

        meta = load_meta()

    meta_by_title = {}
    for meta_title, meta_obj in meta.items():
        if isinstance(meta_obj, dict):
            meta_by_title[meta_title.strip().casefold()] = meta_obj

    if pool_by_identity is None:
        pool_by_identity = {}
        try:
            from candidates.repositories.pool_repository import load_candidate_pool

            for candidate in load_candidate_pool().values():
                if isinstance(candidate, dict):
                    pool_by_identity.setdefault(title_identity_key(candidate), candidate)
        except Exception:
            pass

    return {
        "meta_by_title": meta_by_title,
        "pool_by_identity": pool_by_identity,
    }


def export_watched_movies_json(data, path=None) -> Path:
    """Export watched dataset records to JSON."""
    output_path = DEFAULT_WATCHED_MOVIES_JSON if path is None else Path(path)
    try:
        from posters.cache import load_poster_cache

        poster_cache = load_poster_cache()
    except Exception:
        poster_cache = {}

    lookup_cache = build_export_lookup_cache()
    items = [
        build_watched_movie_card(
            movie_obj,
            poster_cache=poster_cache,
            lookup_cache=lookup_cache,
        )
        for movie_obj in iter_dataset_movies(data)
    ]
    payload = {
        "report_type": "watched_movies",
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "count": len(items),
        "items": items,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
    return output_path


__all__ = [
    "DEFAULT_WATCHED_MOVIES_JSON",
    "build_export_lookup_cache",
    "build_watched_movie_card",
    "export_watched_movies_json",
    "iter_dataset_movies",
    "resolve_watched_description",
]

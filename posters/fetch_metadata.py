"""Fetch poster metadata for watched titles from TMDb cache/API."""

from __future__ import annotations

from apis import tmdb_api
from posters.cache import (
    build_tmdb_poster_url,
    load_poster_cache,
    lookup_poster_cache_entry,
    poster_identity_key,
    save_poster_cache,
    upsert_poster_cache_entry,
)
from storage import data as storage_data


def _read_poster_from_tmdb_details_cache(tmdb_id) -> dict | None:
    try:
        tmdb_id_int = int(tmdb_id)
    except (TypeError, ValueError):
        return None

    safe_language = tmdb_api.DEFAULT_LANGUAGE.replace("-", "_")
    cache_path = tmdb_api.DETAILS_CACHE_DIR / f"{tmdb_id_int}_{safe_language}.json"
    cached = tmdb_api.read_json(cache_path)
    if isinstance(cached, dict) is False:
        return None

    poster_path = cached.get("poster_path")
    if poster_path in (None, ""):
        return None

    return {
        "poster_path": poster_path,
        "poster_url": build_tmdb_poster_url(poster_path),
        "source": "tmdb_details_cache",
        "status": "found",
    }


def _read_poster_from_tmdb_api(tmdb_id) -> dict | None:
    try:
        raw_details = tmdb_api.get_tv_details(int(tmdb_id))
    except Exception:
        return None

    if isinstance(raw_details, dict) is False:
        return None

    normalized = tmdb_api.normalize_tmdb_tv(raw_details)
    poster_path = normalized.get("poster_path")
    poster_url = normalized.get("poster_url") or build_tmdb_poster_url(poster_path)
    if poster_path in (None, "") and poster_url in (None, ""):
        return None

    return {
        "poster_path": poster_path,
        "poster_url": poster_url,
        "source": "tmdb_api",
        "status": "found",
    }


def fetch_poster_metadata_for_watched(*, use_api: bool = True, progress_callback=None) -> dict:
    """Fill missing poster-cache entries using TMDb details cache and optional API."""
    data = storage_data.load_dataset()
    poster_cache = load_poster_cache()

    stats = {
        "total": 0,
        "skipped_found": 0,
        "updated_from_cache": 0,
        "updated_from_api": 0,
        "missing_tmdb_id": 0,
        "still_missing": 0,
    }

    total = len(data)
    for dataset_key, movie in data.items():
        stats["total"] += 1
        main_info = movie.get("main_info") or {}
        title = str(main_info.get("title") or movie.get("title") or dataset_key).strip()
        year = main_info.get("year", movie.get("year"))
        identity = poster_identity_key(title, year)

        existing = lookup_poster_cache_entry(title, year, cache=poster_cache)
        if existing and existing.get("status") == "found":
            stats["skipped_found"] += 1
            if progress_callback is not None:
                progress_callback(stats["total"], total, title)
            continue

        meta_obj = storage_data.get_meta_obj(title)
        tmdb_id = meta_obj.get("tmdb_id") if isinstance(meta_obj, dict) else None
        if tmdb_id in (None, ""):
            stats["missing_tmdb_id"] += 1
            stats["still_missing"] += 1
            if progress_callback is not None:
                progress_callback(stats["total"], total, title)
            continue

        poster_info = _read_poster_from_tmdb_details_cache(tmdb_id)
        if poster_info is not None:
            stats["updated_from_cache"] += 1
        elif use_api:
            poster_info = _read_poster_from_tmdb_api(tmdb_id)
            if poster_info is not None:
                stats["updated_from_api"] += 1

        if poster_info is None:
            upsert_poster_cache_entry(
                title,
                year,
                {
                    "poster_path": None,
                    "poster_url": None,
                    "source": None,
                    "status": "missing",
                },
                cache=poster_cache,
                persist=False,
            )
            stats["still_missing"] += 1
        else:
            upsert_poster_cache_entry(title, year, poster_info, cache=poster_cache, persist=False)

        if progress_callback is not None:
            progress_callback(stats["total"], total, title)

    save_poster_cache(poster_cache)
    return stats

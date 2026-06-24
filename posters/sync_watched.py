"""Batch sync of descriptions and poster-cache for watched titles."""

from __future__ import annotations

from model import train_report
from posters.cache import load_poster_cache, save_poster_cache, sync_poster_cache_from_meta_and_sources
from storage import data as storage_data
from web.export import build_export_lookup_cache


def _find_meta_entry(meta: dict, title: str) -> tuple[str | None, dict | None]:
    expected = title.strip().lower()
    for meta_title, meta_obj in meta.items():
        if meta_title.strip().lower() != expected:
            continue
        if isinstance(meta_obj, dict):
            return meta_title, meta_obj
    return None, None


def sync_watched_metadata(*, write_meta: bool = True, progress_callback=None) -> dict:
    """Backfill meta descriptions and poster-cache for watched dataset records."""
    data = storage_data.load_dataset()
    meta = storage_data.load_meta()
    lookup_cache = build_export_lookup_cache(meta=meta)
    poster_cache = load_poster_cache()

    stats = {
        "total": 0,
        "description_updated": 0,
        "description_found": 0,
        "poster_found": 0,
        "poster_missing": 0,
    }

    total = len(data)
    for dataset_key, movie in data.items():
        stats["total"] += 1
        main_info = movie.get("main_info") or {}
        title = str(main_info.get("title") or movie.get("title") or dataset_key).strip()
        year = main_info.get("year", movie.get("year"))

        meta_title, meta_obj = _find_meta_entry(meta, title)
        description = train_report.resolve_movie_description(
            title,
            year,
            meta_obj,
            lookup_cache["pool_by_identity"],
        )
        if description != "нет описания":
            stats["description_found"] += 1
            if (
                write_meta
                and meta_title is not None
                and isinstance(meta_obj, dict)
                and str(meta_obj.get("description") or "").strip() == ""
            ):
                updated_meta = dict(meta_obj)
                updated_meta["description"] = description
                meta[meta_title] = updated_meta
                meta_obj = updated_meta
                stats["description_updated"] += 1

        poster_entry = sync_poster_cache_from_meta_and_sources(
            title,
            year,
            meta_obj=meta_obj,
            movie=movie,
            cache=poster_cache,
            persist=False,
        )
        if poster_entry.get("status") == "found":
            stats["poster_found"] += 1
        else:
            stats["poster_missing"] += 1

        if progress_callback is not None:
            progress_callback(stats["total"], total, title)

    if write_meta:
        storage_data.save_meta(meta)
    save_poster_cache(poster_cache)
    return stats

"""Read facade for watched dataset display models."""

from __future__ import annotations

from copy import deepcopy

from candidates.models.keys import title_identity_key
from common.cards import build_watched_movie_card
from dataset.language import normalize_data_language, tmdb_locale_for_data_language
from storage import data as storage_data

WatchedEntry = tuple[str, dict, dict]

_poster_cache = None
_lookup_cache = None


def reload_poster_cache() -> dict:
    """Reload poster cache from disk after add/delete/download side effects."""
    global _poster_cache
    try:
        from posters.cache import load_poster_cache

        _poster_cache = load_poster_cache()
    except Exception:
        _poster_cache = {}
    return _poster_cache


def _get_poster_cache() -> dict:
    global _poster_cache
    if _poster_cache is None:
        return reload_poster_cache()
    return _poster_cache


def build_watched_lookup_cache(meta=None, pool_by_identity=None) -> dict:
    """Build lookup map used by watched card descriptions."""
    if meta is None:
        meta = storage_data.load_meta()

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


def _get_lookup_cache() -> dict:
    global _lookup_cache
    if _lookup_cache is None:
        _lookup_cache = build_watched_lookup_cache()
    return _lookup_cache


def load_watched_entries(data_language: str = "ru") -> list[WatchedEntry]:
    """Load dataset and return (dataset_key, movie, display_card) tuples."""
    data = storage_data.load_dataset()
    poster_cache = reload_poster_cache()
    lookup_cache = _get_lookup_cache()
    return [
        (
            key,
            movie,
            build_watched_movie_card(
                movie,
                poster_cache=poster_cache,
                lookup_cache=lookup_cache,
                data_language=data_language,
            ),
        )
        for key, movie in data.items()
    ]


def prepare_card_for_display(movie: dict, data_language: str = "ru") -> dict:
    """Build a watched display card without mutating the source movie."""
    original = deepcopy(movie)
    card = build_watched_movie_card(
        movie,
        poster_cache=_get_poster_cache(),
        lookup_cache=_get_lookup_cache(),
        data_language=data_language,
    )
    if movie != original:
        raise RuntimeError("build_watched_movie_card mutated the source movie")
    return card


def _movie_title_year(movie: dict) -> tuple[str, object]:
    main_info = movie.get("main_info") if isinstance(movie.get("main_info"), dict) else {}
    title = str(main_info.get("title") or movie.get("title") or "").strip()
    year = main_info.get("year", movie.get("year"))
    return title, year


def _localized_poster_available(record: dict | None, data_language: str) -> bool:
    if isinstance(record, dict) is False:
        return False
    localized = record.get("localized") if isinstance(record.get("localized"), dict) else {}
    block = localized.get(normalize_data_language(data_language))
    if isinstance(block, dict) is False:
        return False
    return any(block.get(key) not in (None, "") for key in ("poster_url", "poster_path"))


def _tmdb_id_from_meta(meta_obj: dict | None):
    if isinstance(meta_obj, dict) is False:
        return None
    if meta_obj.get("tmdb_id") not in (None, ""):
        return meta_obj.get("tmdb_id")
    tmdb_data = meta_obj.get("tmdb_data")
    if isinstance(tmdb_data, dict):
        return tmdb_data.get("id") or tmdb_data.get("tmdb_id")
    return None


def _merge_localized_blocks(record: dict, blocks: dict) -> dict:
    updated = deepcopy(record)
    localized = updated.setdefault("localized", {})
    if isinstance(localized, dict) is False:
        localized = {}
        updated["localized"] = localized

    for language, block in blocks.items():
        if isinstance(block, dict) is False:
            continue
        language_block = localized.setdefault(normalize_data_language(language), {})
        if isinstance(language_block, dict) is False:
            language_block = {}
            localized[normalize_data_language(language)] = language_block
        for field_name, value in block.items():
            if value in (None, ""):
                continue
            if field_name in {"poster_path", "poster_url"} or language_block.get(field_name) in (None, ""):
                language_block[field_name] = value
    return updated


def _find_meta_key(meta: dict, title: str) -> str | None:
    expected = str(title or "").strip().casefold()
    for key in meta.keys():
        if str(key).strip().casefold() == expected:
            return key
    return None


def _ensure_tmdb_localized_poster_in_meta(
    title: str,
    meta_obj: dict | None,
    data_language: str,
) -> tuple[dict | None, bool]:
    """Fetch and persist localized poster metadata for old records on demand."""
    language = normalize_data_language(data_language)
    if _localized_poster_available(meta_obj, language):
        return meta_obj, False

    tmdb_id = _tmdb_id_from_meta(meta_obj)
    if tmdb_id in (None, ""):
        return meta_obj, False

    from apis import tmdb_api
    from dataset.tmdb_localized import localized_blocks_from_tmdb_details

    details = tmdb_api.get_tv_details(
        int(tmdb_id),
        language=tmdb_locale_for_data_language(language),
        append_to_response=tmdb_api.DEFAULT_TV_DETAIL_APPENDS,
    )
    blocks = localized_blocks_from_tmdb_details(details, current_language=language)
    if _localized_poster_available({"localized": blocks}, language) is False:
        return meta_obj, False

    updated_meta_obj = _merge_localized_blocks(dict(meta_obj or {}), blocks)
    try:
        meta = storage_data.load_meta()
        meta_key = _find_meta_key(meta, title)
        if meta_key is not None:
            meta[meta_key] = _merge_localized_blocks(
                meta[meta_key] if isinstance(meta[meta_key], dict) else {},
                blocks,
            )
            storage_data.save_meta(meta)
            global _lookup_cache
            _lookup_cache = None
            return meta[meta_key], True
    except Exception:
        return updated_meta_obj, True
    return updated_meta_obj, True


def sync_poster_for_display(movie: dict, data_language: str = "ru") -> dict:
    """Best-effort lazy poster sync for the current data language."""
    title, year = _movie_title_year(movie)
    if title == "":
        return {"updated": False, "reason": "missing_title"}

    from posters.cache import lookup_poster_cache_entry, sync_poster_cache_from_meta_and_sources
    from posters.download_images import download_poster_for_title

    cache_before = _get_poster_cache()
    before = lookup_poster_cache_entry(title, year, cache=cache_before) or {}
    meta_obj = storage_data.get_meta_obj(title)
    meta_obj, meta_updated = _ensure_tmdb_localized_poster_in_meta(title, meta_obj, data_language)
    entry = sync_poster_cache_from_meta_and_sources(
        title,
        year,
        meta_obj=meta_obj,
        movie=movie,
        data_language=data_language,
    )
    poster_changed = before.get("poster_url") != entry.get("poster_url")
    needs_download = entry.get("status") == "found" and (
        poster_changed or entry.get("local_path") in (None, "")
    )
    download = None
    if needs_download:
        download = download_poster_for_title(title, year)
    reload_poster_cache()
    return {
        "updated": bool(meta_updated or poster_changed or needs_download),
        "meta_updated": meta_updated,
        "poster_changed": poster_changed,
        "download": download,
        "entry": entry,
    }


__all__ = [
    "WatchedEntry",
    "build_watched_lookup_cache",
    "load_watched_entries",
    "prepare_card_for_display",
    "reload_poster_cache",
    "sync_poster_for_display",
]

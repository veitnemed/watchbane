"""Read facade for watched dataset display models."""

from __future__ import annotations

from contextlib import closing
from copy import deepcopy
from dataclasses import dataclass
import sqlite3

from candidates.models.keys import title_identity_key
from common.cards import build_watched_movie_card
from dataset.language import normalize_data_language, tmdb_locale_for_data_language
from dataset.models.identity import get_record_main_info, normalize_title_key
from dataset.models.media_type import MEDIA_TYPE_MOVIE, MOVIE_MEDIA_TYPE_ALIASES, TV_MEDIA_TYPE_ALIASES
from storage import data as storage_data
from storage.sqlite.connection import connect
from storage.sqlite.json_codec import dumps_json, loads_json
from storage.sqlite.migrations import apply_migrations
from storage.sqlite.session import utc_now
from storage.sqlite.watched_mapper import extract_watched_record

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


@dataclass(frozen=True)
class _PosterRefreshTarget:
    dataset_key: str
    media_type: str
    tmdb_id: int | None
    created_at: str


def _select_poster_refresh_target(conn, movie: dict) -> tuple[_PosterRefreshTarget, dict | None] | None:
    title, _ = _movie_title_year(movie)
    supplied = extract_watched_record(title, movie)
    matches = []
    for row in conn.execute(
        """SELECT dataset_key, year, media_type, tmdb_id, created_at, payload_json, meta_json
           FROM watched_records WHERE title_normalized = ?""",
        (normalize_title_key(title),),
    ):
        if supplied.year is not None and row["year"] is not None and supplied.year != row["year"]:
            continue
        payload = loads_json(row["payload_json"], None)
        if not isinstance(payload, dict) or not payload:
            continue
        # The poster cache is keyed by display title/year, not by trusted ID.
        # Any sibling that can use that key makes a refresh unsafe.
        matches.append(row)
    if len(matches) != 1:
        return None
    row = matches[0]
    if supplied.tmdb_id and supplied.tmdb_id != row["tmdb_id"]:
        return None
    raw_type = get_record_main_info(movie).get("media_type") or movie.get("media_type")
    media_explicit = str(raw_type or "").strip().casefold() in MOVIE_MEDIA_TYPE_ALIASES | TV_MEDIA_TYPE_ALIASES
    if media_explicit and supplied.media_type != row["media_type"]:
        return None
    meta = loads_json(row["meta_json"], None)
    meta = meta if isinstance(meta, dict) else None
    source_id = _tmdb_id_from_meta(meta)
    try:
        source_id = int(source_id) if source_id not in (None, "") else None
    except (TypeError, ValueError):
        return None
    if row["tmdb_id"] and source_id and row["tmdb_id"] != source_id:
        return None
    return _PosterRefreshTarget(
        row["dataset_key"], row["media_type"], source_id or row["tmdb_id"], row["created_at"]
    ), meta


def _fetch_localized_poster(target: _PosterRefreshTarget, language: str) -> dict:
    from apis import tmdb_api
    from dataset.tmdb_localized import localized_blocks_from_tmdb_details

    if target.media_type == MEDIA_TYPE_MOVIE:
        get_details = tmdb_api.get_movie_details
        append = tmdb_api.DEFAULT_MOVIE_DETAIL_APPENDS
    else:
        get_details = tmdb_api.get_tv_details
        append = tmdb_api.DEFAULT_TV_DETAIL_APPENDS
    details = get_details(
        target.tmdb_id, language=tmdb_locale_for_data_language(language), append_to_response=append,
    )
    return localized_blocks_from_tmdb_details(details, current_language=language)


def _refresh_localized_poster(movie: dict, data_language: str) -> tuple[dict | None, bool] | None:
    """Explicit refresh only. Recheck identity and merge just this row after I/O."""
    language = normalize_data_language(data_language)
    try:
        with closing(connect()) as conn:
            apply_migrations(conn)
            selected = _select_poster_refresh_target(conn, movie)
    except (OSError, sqlite3.Error):
        return None
    if selected is None:
        return None
    target, meta = selected
    if _localized_poster_available(meta, language) or not target.tmdb_id:
        return meta, False

    blocks = _fetch_localized_poster(target, language)
    if not _localized_poster_available({"localized": blocks}, language):
        return meta, False

    try:
        with closing(connect()) as conn, conn:
            conn.execute("BEGIN IMMEDIATE")
            current = _select_poster_refresh_target(conn, movie)
            if current is None or current[0] != target:
                return None
            latest = current[1]
            if meta is not None and latest is None:
                return None
            if _localized_poster_available(latest, language):
                return latest, False
            updated = _merge_localized_blocks(latest or {}, {language: blocks[language]})
            conn.execute(
                "UPDATE watched_records SET meta_json = ?, updated_at = ? WHERE dataset_key = ?",
                (dumps_json(updated), utc_now(), target.dataset_key),
            )
    except (OSError, sqlite3.Error):
        return None
    global _lookup_cache
    _lookup_cache = None
    return updated, True


def sync_poster_for_display(movie: dict, data_language: str = "ru") -> dict:
    """Explicit poster refresh for one unambiguous watched title and language."""
    title, year = _movie_title_year(movie)
    if title == "":
        return {"updated": False, "reason": "missing_title"}

    from posters.cache import lookup_poster_cache_entry, sync_poster_cache_from_meta_and_sources
    from posters.download_images import download_poster_for_title

    refreshed = _refresh_localized_poster(movie, data_language)
    if refreshed is None:
        return {"updated": False, "reason": "watched_row_changed_or_ambiguous"}
    meta_obj, meta_updated = refreshed
    cache_before = _get_poster_cache()
    before = lookup_poster_cache_entry(title, year, cache=cache_before) or {}
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
        download = download_poster_for_title(title, year, force=poster_changed)
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

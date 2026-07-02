"""Fetch TMDb metadata for watched dataset records by title + year."""

from __future__ import annotations

from urllib.error import HTTPError, URLError

from apis import tmdb_api
from dataset.resolve.helpers import extract_candidate_year
from dataset.resolve.identity import extract_api_identity_titles, title_identity_match
from posters.cache import load_poster_cache, save_poster_cache, sync_poster_cache_from_meta_and_sources
from posters.tmdb_overrides import get_watched_tmdb_override, load_watched_tmdb_overrides
from storage import data as storage_data


def _find_meta_entry(meta: dict, title: str) -> tuple[str | None, dict | None]:
    expected = title.strip().lower()
    for meta_title, meta_obj in meta.items():
        if meta_title.strip().lower() != expected:
            continue
        if isinstance(meta_obj, dict):
            return meta_title, meta_obj
    return None, None


def _meta_text(value) -> str:
    return str(value or "").strip()


def _needs_tmdb_fetch(meta_obj: dict | None, title: str, year) -> bool:
    if isinstance(meta_obj, dict) is False:
        return True
    if _meta_text(meta_obj.get("tmdb_id")) == "":
        return True
    if _meta_text(meta_obj.get("description")) == "":
        return True
    if _meta_text(meta_obj.get("poster_url")) == "" and _meta_text(meta_obj.get("poster_path")) == "":
        from posters.cache import lookup_poster_cache_entry

        cache_entry = lookup_poster_cache_entry(title, year)
        if cache_entry is None or cache_entry.get("status") != "found":
            return True
    return False


def _search_result_year(result: dict) -> int | None:
    year = tmdb_api.get_year(result.get("first_air_date"))
    if year is not None:
        return year
    return extract_candidate_year(result)


def _years_compatible(expected_year, result_year) -> bool:
    if expected_year in (None, ""):
        return True
    if result_year is None:
        return True
    try:
        return abs(int(expected_year) - int(result_year)) <= 1
    except (TypeError, ValueError):
        return True


def match_tmdb_search_result(title: str, year, results: list[dict]) -> tuple[dict | None, str]:
    """Match one TMDb search result using existing identity/year policy."""
    if not isinstance(results, list) or len(results) == 0:
        return None, "not_found"

    matched: list[dict] = []
    for result in results:
        if isinstance(result, dict) is False:
            continue
        result_titles = extract_api_identity_titles(result)
        title_ok = any(title_identity_match(title, candidate_title) for candidate_title in result_titles)
        if title_ok is False:
            continue
        if _years_compatible(year, _search_result_year(result)) is False:
            continue
        matched.append(result)

    if len(matched) == 0:
        return None, "not_found"
    if len(matched) > 1:
        if year not in (None, ""):
            exact_year_matches = [
                item for item in matched if _search_result_year(item) == int(year)
            ]
            if len(exact_year_matches) == 1:
                return exact_year_matches[0], "matched"
        return None, "uncertain_match"
    return matched[0], "matched"


def build_tmdb_meta_fields(normalized: dict) -> dict:
    """Build flat meta fields from normalized TMDb TV details."""
    fields: dict = {"source": "tmdb_api"}
    mapping = {
        "tmdb_id": "tmdb_id",
        "overview": "description",
        "imdb_id": "imdb_id",
        "poster_path": "poster_path",
        "poster_url": "poster_url",
    }
    for source_key, target_key in mapping.items():
        value = normalized.get(source_key)
        if value not in (None, ""):
            fields[target_key] = value
    if len(fields) == 1 and fields.get("source") == "tmdb_api":
        return {}
    return fields


def merge_watched_meta_fields(title: str, movie: dict, fields: dict, meta: dict | None = None) -> tuple[dict, dict]:
    """Merge metadata into meta without overwriting existing non-empty fields."""
    if isinstance(fields, dict) is False or len(fields) == 0:
        current_meta = meta if meta is not None else storage_data.load_meta()
        _, meta_obj = _find_meta_entry(current_meta, title)
        return current_meta, meta_obj or {}

    current_meta = dict(meta if meta is not None else storage_data.load_meta())
    meta_title, meta_obj = _find_meta_entry(current_meta, title)

    if meta_obj is None:
        main_info = movie.get("main_info") or {}
        raw_scores = movie.get("raw_scores") or {}
        storage_data.add_movies_to_meta(main_info, raw_scores, extra_meta=fields)
        refreshed = storage_data.load_meta()
        _, meta_obj = _find_meta_entry(refreshed, title)
        return refreshed, meta_obj or {}

    updated = dict(meta_obj)
    applied: dict = {}
    for key, value in fields.items():
        if key in {"main_info", "raw_scores"}:
            continue
        if _meta_text(updated.get(key)) != "":
            continue
        updated[key] = value
        applied[key] = value

    if len(applied) == 0:
        return current_meta, meta_obj

    current_meta[meta_title] = updated
    return current_meta, updated


def _record_unresolved(unresolved: list[dict], title: str, year, reason: str) -> None:
    unresolved.append(
        {
            "title": title,
            "year": year,
            "reason": reason,
        }
    )


def _update_fetch_stats(stats: dict, before_meta: dict, updated_meta: dict, poster_entry: dict) -> None:
    if _meta_text(before_meta.get("tmdb_id")) == "" and _meta_text(updated_meta.get("tmdb_id")) != "":
        stats["found_tmdb_id"] += 1
    if _meta_text(before_meta.get("description")) == "" and _meta_text(updated_meta.get("description")) != "":
        stats["added_description"] += 1
    if _meta_text(before_meta.get("poster_url")) == "" and _meta_text(updated_meta.get("poster_url")) != "":
        stats["added_poster_url"] += 1
    if poster_entry.get("status") == "found":
        stats["poster_cache_updated"] += 1


def _apply_tmdb_details(
    *,
    title: str,
    year,
    movie: dict,
    meta: dict,
    meta_obj: dict | None,
    poster_cache: dict,
    stats: dict,
    normalized: dict,
    source: str,
) -> tuple[dict, dict | None, bool]:
    """Merge normalized TMDb details into meta and poster-cache."""
    fields = build_tmdb_meta_fields(normalized)
    if len(fields) == 0:
        return meta, meta_obj, False

    fields["source"] = source
    before_meta = dict(meta_obj or {})
    meta, updated_meta = merge_watched_meta_fields(title, movie, fields, meta=meta)

    poster_entry = sync_poster_cache_from_meta_and_sources(
        title,
        year,
        meta_obj=updated_meta,
        movie=movie,
        extra_sources=normalized,
        cache=poster_cache,
        persist=False,
    )
    _update_fetch_stats(stats, before_meta, updated_meta, poster_entry)
    return meta, updated_meta, True


def _fetch_override_details(override: dict, details_func) -> dict | None:
    media_type = str(override.get("media_type") or "tv").strip().lower()
    if media_type != "tv":
        return None

    try:
        tmdb_id = int(override["tmdb_id"])
    except (KeyError, TypeError, ValueError):
        return None

    return details_func(tmdb_id)


def format_watched_tmdb_unresolved_report(unresolved: list[dict]) -> str:
    """Build read-only text report for unresolved watched TMDb lookups."""
    if len(unresolved) == 0:
        return "  Нерешённых записей нет."

    lines = ["  Нерешённые записи:"]
    for index, item in enumerate(unresolved, start=1):
        title = item.get("title") or "?"
        year = item.get("year")
        year_label = year if year not in (None, "") else "—"
        reason = item.get("reason") or "unknown"
        lines.append(f"  {index}. {title} ({year_label}) — {reason}")
    return "\n".join(lines)


def fetch_watched_tmdb_metadata(
    *,
    search_func=None,
    details_func=None,
    progress_callback=None,
    overrides: dict | None = None,
) -> dict:
    """Lookup TMDb metadata for watched records missing tmdb_id/description/poster."""
    search_func = search_func or tmdb_api.search_tv_by_name
    details_func = details_func or tmdb_api.get_tv_details
    manual_overrides = load_watched_tmdb_overrides() if overrides is None else overrides

    data = storage_data.load_dataset()
    meta = storage_data.load_meta()
    poster_cache = load_poster_cache()
    unresolved: list[dict] = []

    stats = {
        "checked": 0,
        "already_had_tmdb_id": 0,
        "found_tmdb_id": 0,
        "added_description": 0,
        "added_poster_url": 0,
        "poster_cache_updated": 0,
        "manual_overrides_used": 0,
        "manual_overrides_failed": 0,
        "skipped_not_found": 0,
        "skipped_uncertain_match": 0,
        "network_errors": 0,
        "unresolved": unresolved,
    }

    total = len(data)
    for dataset_key, movie in data.items():
        stats["checked"] += 1
        main_info = movie.get("main_info") or {}
        title = str(main_info.get("title") or movie.get("title") or dataset_key).strip()
        year = main_info.get("year", movie.get("year"))

        meta_title, meta_obj = _find_meta_entry(meta, title)
        if _meta_text((meta_obj or {}).get("tmdb_id")) != "":
            stats["already_had_tmdb_id"] += 1

        if _needs_tmdb_fetch(meta_obj, title, year) is False:
            if progress_callback is not None:
                progress_callback(stats["checked"], total, title)
            continue

        override = get_watched_tmdb_override(title, year, overrides=manual_overrides)
        if override is not None:
            try:
                raw_details = _fetch_override_details(override, details_func)
            except (HTTPError, URLError, OSError, RuntimeError, KeyError, TypeError, ValueError):
                stats["manual_overrides_failed"] += 1
                _record_unresolved(unresolved, title, year, "manual_override_failed")
                if progress_callback is not None:
                    progress_callback(stats["checked"], total, title)
                continue

            if isinstance(raw_details, dict) is False:
                stats["manual_overrides_failed"] += 1
                _record_unresolved(unresolved, title, year, "manual_override_failed")
                if progress_callback is not None:
                    progress_callback(stats["checked"], total, title)
                continue

            normalized = tmdb_api.normalize_tmdb_tv(raw_details)
            meta, updated_meta, applied = _apply_tmdb_details(
                title=title,
                year=year,
                movie=movie,
                meta=meta,
                meta_obj=meta_obj,
                poster_cache=poster_cache,
                stats=stats,
                normalized=normalized,
                source="tmdb_manual_override",
            )
            if applied is False:
                stats["manual_overrides_failed"] += 1
                _record_unresolved(unresolved, title, year, "manual_override_failed")
            else:
                stats["manual_overrides_used"] += 1

            if progress_callback is not None:
                progress_callback(stats["checked"], total, title)
            continue

        try:
            results = search_func(title)
        except (HTTPError, URLError, OSError, RuntimeError):
            stats["network_errors"] += 1
            _record_unresolved(unresolved, title, year, "network_error")
            if progress_callback is not None:
                progress_callback(stats["checked"], total, title)
            continue

        selected, match_status = match_tmdb_search_result(title, year, results)
        if match_status == "uncertain_match":
            stats["skipped_uncertain_match"] += 1
            _record_unresolved(unresolved, title, year, "uncertain_match")
            if progress_callback is not None:
                progress_callback(stats["checked"], total, title)
            continue
        if selected is None:
            stats["skipped_not_found"] += 1
            _record_unresolved(unresolved, title, year, "not_found")
            if progress_callback is not None:
                progress_callback(stats["checked"], total, title)
            continue

        try:
            raw_details = details_func(int(selected["id"]))
        except (HTTPError, URLError, OSError, RuntimeError, KeyError, TypeError, ValueError):
            stats["network_errors"] += 1
            _record_unresolved(unresolved, title, year, "network_error")
            if progress_callback is not None:
                progress_callback(stats["checked"], total, title)
            continue

        normalized = tmdb_api.normalize_tmdb_tv(raw_details)
        meta, updated_meta, applied = _apply_tmdb_details(
            title=title,
            year=year,
            movie=movie,
            meta=meta,
            meta_obj=meta_obj,
            poster_cache=poster_cache,
            stats=stats,
            normalized=normalized,
            source="tmdb_api",
        )
        if applied is False:
            stats["skipped_not_found"] += 1
            _record_unresolved(unresolved, title, year, "not_found")
            if progress_callback is not None:
                progress_callback(stats["checked"], total, title)
            continue

        if progress_callback is not None:
            progress_callback(stats["checked"], total, title)

    storage_data.save_meta(meta)
    save_poster_cache(poster_cache)
    return stats

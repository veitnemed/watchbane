"""Refresh watched dataset metadata and TMDb raw scores from TMDb Details."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from apis import tmdb_api
from candidates.models import genre_schema
from common import format_score
from config import scheme
from dataset.models.media_type import MEDIA_TYPE_MOVIE, normalize_media_type
from posters.fetch_watched_tmdb import match_tmdb_search_result
from storage import data as storage_data
from storage.normalize import normalize_raw_scores
from storage.sqlite.backup import backup_sqlite_database
from storage.sqlite.connection import get_db_path

REPORT_PATH = ROOT_DIR / "data" / "diagnostics" / "watched_tmdb_refresh_report.json"
RAW_SCORE_FIELDS = ("tmdb_score", "tmdb_votes", "tmdb_popularity")
LEGACY_RATING_FIELDS = {"kp_score", "kp_votes", "imdb_score", "imdb_votes"}


def dataset_path() -> Path:
    return get_db_path()


def meta_path() -> Path:
    return get_db_path()


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=4)


def _has_value(value) -> bool:
    return value not in (None, "")


def _find_meta_entry(
    meta: dict[str, Any],
    dataset_key: str,
    title: str,
) -> tuple[str, dict[str, Any]]:
    direct = meta.get(dataset_key)
    if isinstance(direct, dict):
        return str(dataset_key), dict(direct)
    expected = str(title or "").strip().lower()
    for meta_title, meta_obj in meta.items():
        if str(meta_title).strip().lower() == expected and isinstance(meta_obj, dict):
            return str(meta_title), dict(meta_obj)
    return str(dataset_key), {}


def _watched_title(dataset_key: str, movie: dict[str, Any]) -> str:
    main_info = movie.get(scheme.MAIN_INFO) or {}
    return str(main_info.get("title") or movie.get("title") or dataset_key).strip()


def _watched_year(movie: dict[str, Any]):
    main_info = movie.get(scheme.MAIN_INFO) or {}
    return main_info.get("year", movie.get("year"))


def _watched_media_type(movie: dict[str, Any]) -> str:
    main_info = movie.get(scheme.MAIN_INFO) or {}
    return normalize_media_type(main_info.get("media_type", movie.get("media_type")))


def _raw_scores_from_details(raw_details: dict[str, Any]) -> dict[str, Any]:
    raw_scores = {
        "tmdb_score": raw_details.get("vote_average"),
        "tmdb_votes": raw_details.get("vote_count"),
        "tmdb_popularity": raw_details.get("popularity"),
    }
    return normalize_raw_scores({key: value for key, value in raw_scores.items() if _has_value(value)})


def _unique_non_empty(values) -> list:
    result = []
    seen = set()
    for value in values or []:
        text = str(value or "").strip()
        if text == "" or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _genre_keys(genres: list[str]) -> list[str]:
    keys = []
    seen = set()
    for genre in genres:
        key = genre_schema.normalize_genre_to_key(genre)
        if key is None or key in seen:
            continue
        seen.add(key)
        keys.append(key)
    return keys


def _meta_fields_from_details(raw_details: dict[str, Any]) -> dict[str, Any]:
    poster_path = tmdb_api.extract_best_poster_path(raw_details)
    overview = tmdb_api.extract_best_overview(raw_details)
    external_ids = tmdb_api.extract_external_ids(raw_details)
    genres = tmdb_api.names_from_items(raw_details.get("genres"))
    origin_country = _unique_non_empty(raw_details.get("origin_country") or [])
    production_country_names = tmdb_api.names_from_items(raw_details.get("production_countries"))
    production_country_codes = tmdb_api.country_codes_from_items(raw_details.get("production_countries"))
    aggregate_credits = tmdb_api.extract_aggregate_credits_top(raw_details, limit=10)
    fields: dict[str, Any] = {
        "source": "tmdb",
        "tmdb_id": raw_details.get("id"),
        "imdb_id": external_ids.get("imdb_id"),
        "description": overview,
        "overview": overview,
        "poster_path": poster_path,
        "poster_url": tmdb_api.image_link(poster_path),
        "release_date": raw_details.get("release_date"),
        "runtime": raw_details.get("runtime"),
        "first_air_date": raw_details.get("first_air_date"),
        "last_air_date": raw_details.get("last_air_date"),
        "status": raw_details.get("status"),
        "type": raw_details.get("type"),
        "in_production": raw_details.get("in_production"),
        "number_of_seasons": raw_details.get("number_of_seasons"),
        "number_of_episodes": raw_details.get("number_of_episodes"),
        "episode_run_time": raw_details.get("episode_run_time"),
        "original_language": raw_details.get("original_language"),
        "origin_country": origin_country,
        "countries": _unique_non_empty([*origin_country, *production_country_names]),
        "country_codes": _unique_non_empty([*origin_country, *production_country_codes]),
        "genres": genres,
        "genre_keys": _genre_keys(genres),
        "networks": tmdb_api.names_from_items(raw_details.get("networks")),
        "production_companies": tmdb_api.names_from_items(raw_details.get("production_companies")),
        "content_rating": tmdb_api.get_content_rating(raw_details),
        "watch_providers": tmdb_api.get_watch_providers(raw_details),
        "actors_top": aggregate_credits["actors_top"],
        "crew_top": aggregate_credits["crew_top"],
        "keywords": tmdb_api.extract_keywords(raw_details),
    }
    return {
        key: value
        for key, value in fields.items()
        if value not in (None, "", [])
    }


_DETAIL_META_SOURCES = {
    "overview": ("description", "overview"),
    "poster_path": ("poster_path", "poster_url"),
    "release_date": ("release_date",),
    "runtime": ("runtime",),
    "first_air_date": ("first_air_date",),
    "last_air_date": ("last_air_date",),
    "status": ("status",),
    "type": ("type",),
    "in_production": ("in_production",),
    "number_of_seasons": ("number_of_seasons",),
    "number_of_episodes": ("number_of_episodes",),
    "episode_run_time": ("episode_run_time",),
    "original_language": ("original_language",),
    "origin_country": ("origin_country", "countries", "country_codes"),
    "production_countries": ("countries", "country_codes"),
    "genres": ("genres", "genre_keys"),
    "networks": ("networks",),
    "production_companies": ("production_companies",),
    "content_ratings": ("content_rating",),
    "release_dates": ("content_rating",),
    "watch/providers": ("watch_providers",),
    "aggregate_credits": ("actors_top", "crew_top"),
    "credits": ("actors_top", "crew_top"),
    "keywords": ("keywords",),
}


def _clear_explicitly_refreshed_meta(updated_meta: dict[str, Any], raw_details: dict[str, Any]) -> None:
    """Drop stale TMDb fields only when the response explicitly supplies their source."""
    for source_key, target_keys in _DETAIL_META_SOURCES.items():
        if source_key not in raw_details:
            continue
        for target_key in target_keys:
            updated_meta.pop(target_key, None)


def _strip_legacy_raw_scores(raw_scores: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in normalize_raw_scores(raw_scores).items()
        if key not in LEGACY_RATING_FIELDS
    }


def _tmdb_score_fields_for_meta(meta_obj: dict[str, Any], raw_scores: dict[str, Any]) -> dict[str, float]:
    from candidates.sources.tmdb.scoring import (
        compute_metadata_completeness_score,
        compute_tmdb_final_score,
        compute_tmdb_hidden_gem_score,
        compute_tmdb_quality_score,
    )

    main_info = meta_obj.get(scheme.MAIN_INFO) or {}
    candidate_like = {
        **meta_obj,
        **raw_scores,
        "country": meta_obj.get("country") or main_info.get("country"),
    }
    metadata_score = compute_metadata_completeness_score(candidate_like)
    quality_score = compute_tmdb_quality_score(candidate_like)
    hidden_gem_score = compute_tmdb_hidden_gem_score(candidate_like)
    final_score = compute_tmdb_final_score(
        {
            **candidate_like,
            "metadata_completeness_score": metadata_score,
            "quality_score": quality_score,
            "hidden_gem_score": hidden_gem_score,
        }
    )
    return {
        "metadata_completeness_score": metadata_score,
        "quality_score": quality_score,
        "hidden_gem_score": hidden_gem_score,
        "final_score": final_score,
    }


def _apply_details_to_record(
    *,
    dataset_key: str,
    movie: dict[str, Any],
    meta_title: str,
    meta_obj: dict[str, Any],
    raw_details: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], bool]:
    updated_movie = dict(movie)
    main_info = dict(updated_movie.get(scheme.MAIN_INFO) or {})
    old_raw_scores = dict(updated_movie.get(scheme.RAW_SCORES) or {})
    new_raw_scores = _strip_legacy_raw_scores(old_raw_scores)
    tmdb_raw_scores = _raw_scores_from_details(raw_details)
    changed_raw = False

    raw_score_sources = {
        "tmdb_score": "vote_average",
        "tmdb_votes": "vote_count",
        "tmdb_popularity": "popularity",
    }
    for key, source_key in raw_score_sources.items():
        if source_key not in raw_details:
            continue
        if key in tmdb_raw_scores:
            value = tmdb_raw_scores[key]
            if new_raw_scores.get(key) == value:
                continue
            new_raw_scores[key] = value
            changed_raw = True
        elif key in new_raw_scores:
            new_raw_scores.pop(key)
            changed_raw = True

    updated_movie[scheme.RAW_SCORES] = new_raw_scores
    updated_movie["computed_scores"] = format_score.raw_to_struct(new_raw_scores, main_info)

    updated_meta = dict(meta_obj)
    updated_meta.setdefault(scheme.MAIN_INFO, main_info)
    updated_meta[scheme.RAW_SCORES] = dict(new_raw_scores)
    _clear_explicitly_refreshed_meta(updated_meta, raw_details)
    for key, value in _meta_fields_from_details(raw_details).items():
        updated_meta[key] = value
    updated_meta.update(_tmdb_score_fields_for_meta(updated_meta, new_raw_scores))

    del dataset_key, meta_title
    return updated_movie, updated_meta, changed_raw


def _details_by_search(
    *,
    title: str,
    year,
    search_func,
    details_func,
    force_refresh: bool,
    token: str | None,
    append_to_response,
) -> tuple[dict[str, Any] | None, str]:
    results = search_func(title, token=token)
    selected, match_status = match_tmdb_search_result(title, year, results)
    if match_status == "uncertain_match":
        return None, "needs_manual_match"
    if selected is None:
        return None, "failed"
    details = details_func(
        int(selected["id"]),
        append_to_response=append_to_response,
        force_refresh=force_refresh,
        token=token,
    )
    return details, "matched_by_search"


def refresh_watched(
    dataset: dict[str, Any],
    meta: dict[str, Any],
    *,
    limit: int | None = None,
    only_missing: bool = False,
    force_refresh: bool = False,
    token: str | None = None,
    search_func=None,
    details_func=None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    updated_dataset = dict(dataset)
    updated_meta = dict(meta)
    report = {
        "total": len(dataset) if isinstance(dataset, dict) else 0,
        "processed": 0,
        "refreshed_by_tmdb_id": 0,
        "matched_by_search": 0,
        "needs_manual_match": 0,
        "failed": 0,
        "updated_raw_scores": 0,
        "items": [],
    }
    if isinstance(dataset, dict) is False:
        return {}, dict(meta or {}), report

    remaining = None if limit is None else max(0, int(limit))
    for dataset_key, movie in dataset.items():
        if isinstance(movie, dict) is False:
            continue
        if remaining == 0:
            continue

        title = _watched_title(dataset_key, movie)
        year = _watched_year(movie)
        media_type = _watched_media_type(movie)
        meta_title, meta_obj = _find_meta_entry(updated_meta, dataset_key, title)
        current_tmdb_id = meta_obj.get("tmdb_id")

        selected_search_func = search_func
        selected_details_func = details_func
        if selected_search_func is None:
            selected_search_func = (
                tmdb_api.search_movie_by_title
                if media_type == MEDIA_TYPE_MOVIE
                else tmdb_api.search_tv_by_name
            )
        if selected_details_func is None:
            selected_details_func = (
                tmdb_api.get_movie_details
                if media_type == MEDIA_TYPE_MOVIE
                else tmdb_api.get_tv_details
            )
        append_to_response = (
            tmdb_api.DEFAULT_MOVIE_DETAIL_APPENDS
            if media_type == MEDIA_TYPE_MOVIE
            else tmdb_api.DEFAULT_TV_DETAIL_APPENDS
        )

        if only_missing and _has_value(current_tmdb_id):
            continue

        try:
            if _has_value(current_tmdb_id):
                raw_details = selected_details_func(
                    int(current_tmdb_id),
                    append_to_response=append_to_response,
                    force_refresh=force_refresh,
                    token=token,
                )
                status = "refreshed_by_tmdb_id"
            else:
                raw_details, status = _details_by_search(
                    title=title,
                    year=year,
                    search_func=selected_search_func,
                    details_func=selected_details_func,
                    force_refresh=force_refresh,
                    token=token,
                    append_to_response=append_to_response,
                )
                if raw_details is None:
                    report[status] += 1
                    report["items"].append({"title": title, "year": year, "status": status})
                    if remaining is not None:
                        remaining -= 1
                    report["processed"] += 1
                    continue

            if not isinstance(raw_details, dict) or not raw_details:
                raise ValueError("TMDb returned an empty details response")

            refreshed_movie, refreshed_meta, changed_raw = _apply_details_to_record(
                dataset_key=dataset_key,
                movie=movie,
                meta_title=meta_title,
                meta_obj=meta_obj,
                raw_details=raw_details,
            )
            updated_dataset[dataset_key] = refreshed_movie
            updated_meta[meta_title] = refreshed_meta
            report[status] += 1
            if changed_raw:
                report["updated_raw_scores"] += 1
            report["items"].append({"title": title, "year": year, "status": status})
        except Exception as error:  # noqa: BLE001 - refresh report should capture external failures.
            report["failed"] += 1
            report["items"].append({"title": title, "year": year, "status": "failed", "error": str(error)})

        if remaining is not None:
            remaining -= 1
        report["processed"] += 1

    return updated_dataset, updated_meta, report


def build_report(*, mode: str, dataset_path: Path, meta_path: Path, backup_paths: dict[str, str] | None, stats: dict) -> dict:
    return {
        "mode": mode,
        "dataset_path": str(dataset_path),
        "meta_path": str(meta_path),
        "backup_paths": backup_paths or {},
        "created_at": datetime.now().isoformat(timespec="seconds"),
        **stats,
    }


def run_refresh(
    *,
    apply: bool,
    limit: int | None = None,
    only_missing: bool = False,
    force_refresh: bool = False,
    report_path: Path = REPORT_PATH,
    token: str | None = None,
    search_func=None,
    details_func=None,
) -> dict:
    watched_path = dataset_path()
    watched_meta_path = meta_path()
    dataset = storage_data.load_dataset()
    meta = storage_data.load_meta()
    refreshed_dataset, refreshed_meta, stats = refresh_watched(
        dataset,
        meta,
        limit=limit,
        only_missing=only_missing,
        force_refresh=force_refresh,
        token=token,
        search_func=search_func,
        details_func=details_func,
    )

    backup_paths = {}
    if apply:
        database_backup = backup_sqlite_database(db_path=watched_path)
        storage_data.save_dataset_and_meta(refreshed_dataset, refreshed_meta)
        backup_paths = {"database": str(database_backup)}

    report = build_report(
        mode="apply" if apply else "dry-run",
        dataset_path=watched_path,
        meta_path=watched_meta_path,
        backup_paths=backup_paths,
        stats=stats,
    )
    write_json(report_path, report)
    return report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh watched metadata and raw_scores from TMDb.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Build report without changing the SQLite runtime.")
    mode.add_argument("--apply", action="store_true", help="Backup and update the SQLite runtime.")
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of watched records to process.")
    parser.add_argument("--only-missing", action="store_true", help="Only refresh records without meta.tmdb_id.")
    parser.add_argument("--force-refresh", action="store_true", help="Bypass TMDb details cache where supported.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = run_refresh(
        apply=args.apply,
        limit=args.limit,
        only_missing=args.only_missing,
        force_refresh=args.force_refresh,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

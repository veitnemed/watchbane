"""Thin facade for candidate pool console flows (read views and selected write actions)."""

from __future__ import annotations

import json
from pathlib import Path

from app.core import candidates as search_core
from app.core import ranking as search_ranking
from app.core import storage as search_storage
from candidates.models.keys import COMMON_POOL_CRITERIA_NAME
from candidates.onboarding.autofill import (
    CountrySelection,
    OnboardingTasteProfile,
    build_country_plan,
    build_fetch_buckets,
    media_weights,
    origin_weights,
    release_weights,
    run_onboarding_autofill,
    should_start_onboarding_autofill,
    vibe_weights,
)
from candidates.pool.dataset_overlap import (
    count_pool_dataset_title_matches,
    purge_dataset_title_matches_from_pool,
)
from candidates.pool.dedupe import clean_common_pool_duplicates as _clean_common_pool_duplicates_impl
from candidates.pool.diagnostics import (
    build_candidate_poster_diagnostics,
    build_title_duplicate_summary,
    collect_candidate_poster_download_urls,
    collect_unique_pool_poster_urls,
    find_cross_year_title_groups,
    find_suspicious_duplicates,
    find_title_duplicate_groups,
)
from candidates.pool.queries import (
    get_all_candidates,
    get_incomplete_candidates,
    is_candidate_incomplete,
)
from candidates.pool.search_helpers import (
    build_search_filter_defaults,
    collect_search_country_options,
    collect_search_genre_options,
)
from candidates.pool.stats import build_pool_genre_count_rows, get_pool_stats
from candidates.pool.watched_cleanup import remove_candidate_from_pool
from candidates.repositories.criteria_repository import (
    build_criteria_label,
    clear_common_pool,
    ensure_common_pool_criteria as _ensure_common_pool_criteria_impl,
    load_candidate_criteria,
)
from candidates.repositories.pool_repository import load_candidate_pool
from candidates.scoring.sort_keys import dedupe_ranked_candidates_by_title_identity
from candidates.sources.tmdb import builder as tmdb_build
from candidates.sources.tmdb import country_options as tmdb_country_options
from candidates.sources.tmdb import importer as tmdb_import
from candidates.views.formatters import (
    format_candidate_description as _format_candidate_description_impl,
    format_pool_stats_lines,
    format_pool_stats_summary,
    format_search_filter_default_lines,
)
from dataset import filter_popularity
from candidates.views import filter_popularity as pool_filter_popularity
from storage import data as storage_data


def get_pool_view(criteria_name: str | None = None) -> list:
    """Returns candidates for display without writing the SQLite candidate pool."""
    del criteria_name
    return get_all_candidates()


def get_pool_stats_view(criteria_name: str | None = None) -> dict:
    """Returns pool stats and formatted lines for UI without writing JSON."""
    stats = get_pool_stats(criteria_name=criteria_name)
    return {
        "stats": stats,
        "lines": format_pool_stats_lines(stats),
        "summary": format_pool_stats_summary(stats),
    }


def get_pool_genre_count_rows() -> list[dict]:
    """Read-only genre distribution rows for candidate pool analytics."""
    return build_pool_genre_count_rows(get_pool_view())


def get_search_overview_view() -> dict:
    """Read-only pool overview for the local candidate search screen."""
    stats_view = get_pool_stats_view()
    candidates = get_pool_view()
    return {
        "stats": stats_view["stats"],
        "lines": stats_view["lines"],
        "summary": stats_view["summary"],
        "candidates": candidates,
        "is_empty": stats_view["stats"]["storage_total"] == 0,
    }


def get_search_filter_view(candidates: list, filters: dict) -> dict:
    """Applies runtime filters for local search without model scoring."""
    search_view = search_core.search_candidates(candidates, filters)
    filtered_candidates = search_view["candidates"]
    ready_candidates = filtered_candidates
    incomplete_candidates = [
        candidate for candidate in filtered_candidates
        if is_candidate_incomplete(candidate)
    ]

    return {
        "filtered_candidates": filtered_candidates,
        "ready_candidates": ready_candidates,
        "incomplete_candidates": incomplete_candidates,
        "filtered_count": len(filtered_candidates),
        "ready_count": len(ready_candidates),
        "skipped_incomplete_count": 0,
        "candidates": filtered_candidates,
    }


def get_search_filter_defaults_view(criteria_name: str | None = None) -> dict:
    """Returns saved search filter defaults for UI without writing JSON."""
    del criteria_name
    defaults = build_search_filter_defaults()
    lines = format_search_filter_default_lines(defaults)
    common_criteria = load_candidate_criteria().get(COMMON_POOL_CRITERIA_NAME)
    return {
        "defaults": defaults,
        "lines": lines,
        "has_defaults": isinstance(common_criteria, dict) and len(common_criteria) > 0,
    }


def get_search_genre_options_view(criteria_name: str | None = None) -> dict:
    """Returns saved-pool genres available for search filters without writing JSON."""
    del criteria_name
    candidates = get_pool_view()
    genres = collect_search_genre_options(candidates)
    return {
        "criteria_name": COMMON_POOL_CRITERIA_NAME,
        "genres": genres,
        "count": len(genres),
        "label": "Доступные жанры для поиска (по сохранённым данным pool)",
    }


def get_search_filter_chip_options_view() -> dict:
    """Returns watched-dataset genre/country options for filter chips, popular first."""
    dataset = storage_data.load_dataset()
    dataset_total = len(dataset) if isinstance(dataset, dict) else 0
    pool_candidates = get_pool_view()
    pool_genres = collect_search_genre_options(pool_candidates)
    pool_countries = collect_search_country_options(pool_candidates)

    genres = filter_popularity.build_dataset_genre_popularity(dataset)
    countries = filter_popularity.build_dataset_country_popularity(dataset)
    genres = pool_filter_popularity.merge_genre_popularity_with_pool(genres, pool_genres)
    countries = pool_filter_popularity.merge_country_popularity_with_pool(countries, pool_countries)

    source = "dataset" if dataset_total > 0 else "fallback"
    if not genres:
        source = "fallback"
        genres = [{"label": label, "count": 0} for label in pool_genres]

    if not countries:
        source = "fallback"
        countries = [
            {"code": option["code"], "label": option["label"], "count": 0}
            for option in tmdb_country_options.country_options()
        ]

    return {
        "genres": genres,
        "countries": countries,
        "dataset_total": dataset_total,
        "is_empty": dataset_total == 0,
        "source": source,
    }


def mark_candidate_watched_in_pool(candidate: dict) -> dict:
    """Removes watched candidate from pool via existing title+year write-path."""
    removed_count = remove_candidate_from_pool(candidate)
    if removed_count > 0:
        message = f"Из pool удалено записей: {removed_count}"
    else:
        message = "Совпадающих записей в pool не найдено"

    return {
        "removed": removed_count > 0,
        "removed_count": removed_count,
        "message": message,
        "candidate": candidate,
    }


def get_metadata_diagnostics_view(criteria_name: str | None = None) -> dict:
    """Prepares incomplete TMDb/core metadata diagnostics without writing JSON."""
    del criteria_name
    pool = load_candidate_pool()
    incomplete_candidates = get_incomplete_candidates(pool, criteria_name=None)

    return {
        "is_empty": len(pool) == 0,
        "incomplete_candidates": incomplete_candidates,
        "incomplete_count": len(incomplete_candidates),
    }


def should_show_onboarding_autofill() -> bool:
    """Return True when startup should collect taste and build the first pool."""
    return should_start_onboarding_autofill()


def build_onboarding_candidate_pool(
    profile: OnboardingTasteProfile | dict,
    *,
    progress_callback=None,
    cancel_checker=None,
) -> dict:
    """Run deterministic onboarding autofill through the service boundary."""
    if isinstance(profile, OnboardingTasteProfile):
        taste_profile = profile
    else:
        taste_profile = OnboardingTasteProfile(
            media_preference=profile.get("media_preference"),
            release_preference=profile.get("release_preference"),
            vibe_preference=profile.get("vibe_preference"),
            origin_preference=profile.get("origin_preference"),
            ui_language=profile.get("ui_language"),
            country_selection=profile.get("country_selection"),
            include_genres=profile.get("include_genres"),
            include_genre_mode=profile.get("include_genre_mode", "or"),
            exclude_genres=profile.get("exclude_genres"),
            min_year=profile.get("min_year"),
            max_year=profile.get("max_year"),
            discover_pages=profile.get("discover_pages", 3),
            details_limit=profile.get("details_limit", 50),
        )
    result = run_onboarding_autofill(
        taste_profile,
        progress_callback=progress_callback,
        cancel_checker=cancel_checker,
    )
    return {
        "ok": result.ok,
        "profile_id": result.profile_id,
        "created_count": result.created_count,
        "pool_size": result.pool_size,
        "api_requests": result.api_requests,
        "cancelled": result.cancelled,
        "warning": result.warning,
        "warnings": result.warnings,
        "planned_counts": result.planned_counts,
        "actual_counts": result.actual_counts,
        "rejected_future_count": result.rejected_future_count,
        "duplicate_requests_skipped": result.duplicate_requests_skipped,
        "candidates": result.candidates,
    }


def _normalize_onboarding_profile(profile: OnboardingTasteProfile | dict) -> OnboardingTasteProfile:
    if isinstance(profile, OnboardingTasteProfile):
        return profile.normalized()
    return OnboardingTasteProfile(
        media_preference=profile.get("media_preference"),
        release_preference=profile.get("release_preference"),
        vibe_preference=profile.get("vibe_preference"),
        origin_preference=profile.get("origin_preference"),
        ui_language=profile.get("ui_language"),
        country_selection=profile.get("country_selection"),
        include_genres=profile.get("include_genres"),
        include_genre_mode=profile.get("include_genre_mode", "or"),
        exclude_genres=profile.get("exclude_genres"),
        min_year=profile.get("min_year"),
        max_year=profile.get("max_year"),
        discover_pages=profile.get("discover_pages", 3),
        details_limit=profile.get("details_limit", 50),
    ).normalized()


def get_onboarding_autofill_plan_view(profile: OnboardingTasteProfile | dict) -> dict:
    """Return deterministic onboarding pool quotas without making TMDb calls."""
    taste_profile = _normalize_onboarding_profile(profile)
    buckets = build_fetch_buckets(taste_profile)

    def quota_by(field: str) -> dict[str, int]:
        totals: dict[str, int] = {}
        for bucket in buckets:
            value = getattr(bucket, field)
            if value is None:
                continue
            totals[str(value)] = totals.get(str(value), 0) + int(bucket.quota)
        return totals

    return {
        "profile": taste_profile.as_repository_dict(),
        "target": sum(int(bucket.quota) for bucket in buckets),
        "bucket_count": len(buckets),
        "quotas": {
            "media_type": quota_by("media_type"),
            "release": quota_by("era"),
            "vibe": quota_by("vibe"),
            "country": quota_by("target_country"),
            "origin": quota_by("origin"),
            "original_language": quota_by("original_language"),
        },
        "weights": {
            "media_type": media_weights(taste_profile.media_preference),
            "release": release_weights(taste_profile.release_preference),
            "vibe": vibe_weights(taste_profile.vibe_preference),
            "origin": origin_weights(taste_profile.origin_preference, ui_language=taste_profile.ui_language),
            "country": (
                taste_profile.country_selection.country_weights
                if isinstance(taste_profile.country_selection, CountrySelection)
                else {}
            ),
        },
        "country_selection": (
            taste_profile.country_selection.as_repository_dict()
            if isinstance(taste_profile.country_selection, CountrySelection)
            else {}
        ),
        "country_plan": (
            build_country_plan(taste_profile.country_selection, sum(int(bucket.quota) for bucket in buckets))
            if isinstance(taste_profile.country_selection, CountrySelection)
            else {}
        ),
    }


def get_tmdb_import_files_view() -> dict:
    """Returns available TMDb result JSON files for import UI without writing JSON."""
    files = tmdb_import.list_tmdb_result_files()
    return {
        "files": files,
        "file_names": [path.name for path in files],
        "is_empty": len(files) == 0,
    }


def load_tmdb_result_import_preview(result_path: str | Path) -> dict:
    """Loads TMDb result JSON preview for import UI without mutating pool."""
    result_path = Path(result_path)
    try:
        with open(result_path, "r", encoding="utf-8-sig") as file:
            result = json.load(file)
    except (OSError, json.JSONDecodeError) as error:
        return {
            "ok": False,
            "error": str(error),
            "result_path": result_path,
            "candidates": [],
            "candidate_count": 0,
            "default_criteria_name": "",
        }

    candidates = result.get("candidates") if isinstance(result, dict) else None
    if isinstance(candidates, list) is False:
        return {
            "ok": False,
            "error": "В файле нет списка candidates.",
            "result_path": result_path,
            "candidates": [],
            "candidate_count": 0,
            "default_criteria_name": "",
        }

    default_criteria_name = tmdb_import.tmdb_import_default_criteria_name(result) or ""
    return {
        "ok": True,
        "error": None,
        "result_path": result_path,
        "result": result,
        "candidates": candidates,
        "candidate_count": len(candidates),
        "default_criteria_name": default_criteria_name,
    }


def import_tmdb_result_to_pool(result_path: str | Path, criteria_name: str | None = None) -> dict:
    """Imports TMDb result JSON into common candidate_pool via existing write-path."""
    result_path = Path(result_path)
    stats = tmdb_import.import_tmdb_result_to_common_pool(result_path, criteria_name=criteria_name)
    resolved_criteria_name = stats.get("criteria_name") or criteria_name
    return {
        "ok": stats.get("ok", False),
        "stats": stats,
        "result_file": str(result_path),
        "criteria_name": resolved_criteria_name,
        "error": stats.get("error"),
    }


def build_tmdb_criteria_name(
    country: str,
    mode: str,
    year_min: int | None = None,
    min_tmdb_score: float | None = None,
) -> str:
    """Returns default criteria_name for TMDb build flow without writing JSON."""
    return tmdb_build.build_tmdb_criteria_name(
        country,
        mode,
        year_min=year_min,
        min_tmdb_score=min_tmdb_score,
    )


def build_tmdb_candidate_pool(
    country: str,
    pages: int = 3,
    details_limit: int = 50,
    mode: str = "quality",
    criteria_name: str | None = None,
    year_min: int | None = None,
    year_max: int | None = None,
    min_tmdb_score: float | None = None,
    min_tmdb_votes: int | None = None,
    with_genres: str | None = None,
    without_genres: str | None = None,
    force_refresh: bool = False,
    skip_existing_pool: bool = True,
    language: str | None = None,
    media_type: str | None = None,
) -> dict:
    """Builds TMDb-only candidate snapshot via discover/details path."""
    build_kwargs = {
        "country": country,
        "pages": pages,
        "details_limit": details_limit,
        "mode": mode,
        "criteria_name": criteria_name,
        "year_min": year_min,
        "year_max": year_max,
        "min_tmdb_score": min_tmdb_score,
        "min_tmdb_votes": min_tmdb_votes,
        "with_genres": with_genres,
        "without_genres": without_genres,
        "force_refresh": force_refresh,
        "skip_existing_pool": skip_existing_pool,
        "language": language,
        "media_type": media_type,
    }
    return tmdb_build.build_candidate_pool(**build_kwargs)


def save_tmdb_build_result(result: dict, *, is_test_run: bool = False) -> dict:
    """Saves TMDb build snapshot JSON/CSV via existing write-path."""
    if is_test_run:
        json_path, csv_path = tmdb_build.save_candidate_pool_test_result(result)
    else:
        json_path, csv_path = tmdb_build.save_candidate_pool_result(result)

    return {
        "ok": True,
        "json_path": json_path,
        "csv_path": csv_path,
        "is_test_run": is_test_run,
        "criteria_name": result.get("criteria_name"),
    }


def build_and_save_tmdb_candidate_pool(*, is_test_run: bool = False, **build_kwargs) -> dict:
    """Builds and saves TMDb snapshot via existing write-path without auto-import prompt."""
    try:
        result = build_tmdb_candidate_pool(**build_kwargs)
    except Exception as error:
        return {
            "ok": False,
            "error": str(error),
            "result": None,
            "json_path": None,
            "csv_path": None,
            "criteria_name": build_kwargs.get("criteria_name"),
            "is_test_run": is_test_run,
            "stats": {},
            "candidates": [],
        }

    save_result = save_tmdb_build_result(result, is_test_run=is_test_run)
    return {
        "ok": True,
        "error": None,
        "result": result,
        "json_path": save_result["json_path"],
        "csv_path": save_result["csv_path"],
        "criteria_name": result.get("criteria_name") or build_kwargs.get("criteria_name"),
        "is_test_run": is_test_run,
        "stats": result.get("stats") or {},
        "candidates": result.get("candidates") or [],
    }


def get_mark_watched_view(criteria_name: str | None = None) -> dict:
    """Prepares candidate list and pool stats for mark-watched UI without writing JSON."""
    del criteria_name
    candidates = get_pool_view()
    stats_view = get_pool_stats_view()
    return {
        "criteria_name": COMMON_POOL_CRITERIA_NAME,
        "candidates": candidates,
        "stats": stats_view["stats"],
        "lines": stats_view["lines"],
        "summary": stats_view["summary"],
        "is_empty": len(candidates) == 0,
    }


def is_pool_candidate_incomplete(candidate: dict) -> bool:
    """Returns incomplete flag for mark-watched UI without writing JSON."""
    return is_candidate_incomplete(candidate)


def clear_common_candidate_pool() -> dict:
    """Clears all candidates from the shared pool via existing write-path."""
    result = clear_common_pool()
    return {
        "cleared": result.get("cleared", 0),
        "criteria_name": COMMON_POOL_CRITERIA_NAME,
    }


def clean_common_pool_duplicates(
    *,
    merge_similar: bool = True,
    merge_cross_year: bool = True,
) -> dict:
    """Removes exact, similar, and cross-year duplicates from shared pool via write-path."""
    return _clean_common_pool_duplicates_impl(
        merge_similar=merge_similar,
        merge_cross_year=merge_cross_year,
    )


def get_pool_dataset_title_matches_view() -> dict:
    """Read-only preview of pool entries whose title exists in watched dataset."""
    return count_pool_dataset_title_matches()


def purge_pool_dataset_title_matches() -> dict:
    """Removes pool entries whose normalized title exists in watched dataset."""
    return purge_dataset_title_matches_from_pool()


def delete_candidate_pool_criteria(criteria_name: str) -> dict:
    """Legacy alias: clears the shared candidate pool."""
    del criteria_name
    result = clear_common_candidate_pool()
    return {
        "deleted": result["cleared"] > 0,
        "deleted_criteria": False,
        "deleted_candidates": result["cleared"],
        "criteria_name": COMMON_POOL_CRITERIA_NAME,
    }


def get_suspicious_duplicates_view() -> dict:
    """Prepares suspicious duplicate pairs for diagnostics UI without writing JSON."""
    pairs = find_suspicious_duplicates()
    return {
        "pairs": pairs,
        "count": len(pairs),
        "is_empty": len(pairs) == 0,
    }


def get_cross_year_duplicates_view() -> dict:
    """Prepares cross-year duplicate groups for diagnostics UI without writing JSON."""
    groups = find_cross_year_title_groups()
    return {
        "groups": groups,
        "count": len(groups),
        "is_empty": len(groups) == 0,
    }


def get_title_duplicates_view() -> dict:
    """Prepares title duplicate groups and summary for diagnostics UI without writing JSON."""
    groups = find_title_duplicate_groups()
    summary = build_title_duplicate_summary(groups)
    return {
        "groups": groups,
        "summary": summary,
        "group_count": summary["group_count"],
        "extra_entries": summary["extra_entries"],
        "reported_groups": summary["reported_groups"],
        "dataset_overlap_count": summary["dataset_overlap_count"],
        "count": summary["reported_groups"],
        "is_empty": len(groups) == 0,
    }


def get_candidate_poster_diagnostics_view() -> dict:
    """Prepares poster coverage diagnostics for saved pool candidates without writes."""
    overview = get_search_overview_view()
    if overview.get("is_empty"):
        return {
            "is_empty_pool": True,
            "is_empty": True,
            "total": 0,
            "counts": {"displayable": 0, "metadata_only": 0, "missing": 0},
            "source_counts": {},
            "problem_rows": [],
        }

    diagnostics = build_candidate_poster_diagnostics(overview["candidates"])
    return {
        "is_empty_pool": False,
        **diagnostics,
    }


def get_console_candidate_summary_view() -> dict:
    """Returns compact candidate-pool counters for the main console menu."""
    stats_view = get_pool_stats_view()
    poster_view = get_candidate_poster_diagnostics_view()
    stats = stats_view.get("stats") or {}
    counts = poster_view.get("counts") or {}

    total = int(stats.get("unique_total") or stats.get("storage_total") or 0)
    complete = int(stats.get("ready_total") or 0)
    incomplete = int(stats.get("incomplete_total") or max(0, total - complete))
    posters_displayable = int(counts.get("displayable") or 0)
    posters_to_download = int(counts.get("metadata_only") or 0)
    posters_missing_metadata = int(counts.get("missing") or 0)
    line = (
        f"Candidate pool: {total} | complete: {complete} | "
        f"posters: {posters_displayable} | need posters: {posters_to_download}"
    )

    return {
        "total": total,
        "complete": complete,
        "incomplete": incomplete,
        "posters_displayable": posters_displayable,
        "posters_to_download": posters_to_download,
        "posters_missing_metadata": posters_missing_metadata,
        "line": line,
    }


def download_candidate_pool_preview_posters(
    *,
    progress_callback=None,
    error_callback=None,
    result_callback=None,
    should_stop_callback=None,
) -> dict:
    """Download candidate pool poster URLs that do not have a local preview yet."""
    from posters.download_images import download_preview_posters_for_urls

    overview = get_search_overview_view()
    if overview.get("is_empty"):
        return {
            "ok": False,
            "is_empty_pool": True,
            "pool_total": 0,
            "unique_urls": 0,
            "poster_displayable": 0,
            "poster_metadata_only": 0,
            "poster_missing": 0,
            "download_queue_total": 0,
            "already_displayable": 0,
            "downloaded": 0,
            "skipped_existing": 0,
            "failed": 0,
            "skipped_invalid": 0,
            "failures": [],
        }

    candidates = overview["candidates"]
    diagnostics = build_candidate_poster_diagnostics(candidates)
    counts = diagnostics.get("counts") or {}
    urls = collect_candidate_poster_download_urls(candidates)
    if len(urls) == 0:
        stats = {
            "total_urls": 0,
            "downloaded": 0,
            "skipped_existing": 0,
            "failed": 0,
            "skipped_invalid": 0,
            "failures": [],
        }
    else:
        call_kwargs = {
            "progress_callback": progress_callback,
            "error_callback": error_callback,
        }
        if result_callback is not None:
            call_kwargs["result_callback"] = result_callback
        if should_stop_callback is not None:
            call_kwargs["should_stop_callback"] = should_stop_callback
        stats = download_preview_posters_for_urls(
            urls,
            **call_kwargs,
        )
    return {
        "ok": True,
        "is_empty_pool": False,
        "pool_total": len(candidates),
        "unique_urls": len(urls),
        "poster_displayable": int(counts.get("displayable") or 0),
        "poster_metadata_only": int(counts.get("metadata_only") or 0),
        "poster_missing": int(counts.get("missing") or 0),
        "download_queue_total": len(urls),
        "already_displayable": int(counts.get("displayable") or 0),
        **stats,
    }


def get_criteria_catalog_view() -> dict:
    """Returns the single shared pool criteria entry for UI pickers."""
    all_criteria = load_candidate_criteria()
    criteria = all_criteria.get(COMMON_POOL_CRITERIA_NAME)
    items = []
    if isinstance(criteria, dict):
        items.append({
            "criteria_name": COMMON_POOL_CRITERIA_NAME,
            "criteria": criteria,
            "label": build_criteria_label(COMMON_POOL_CRITERIA_NAME, criteria),
        })
    return {
        "items": items,
        "by_name": {COMMON_POOL_CRITERIA_NAME: criteria} if isinstance(criteria, dict) else {},
        "is_empty": len(items) == 0,
    }


def get_common_pool_criteria_view() -> dict:
    """Returns shared pool build/filter settings without writing JSON."""
    criteria = load_candidate_criteria().get(COMMON_POOL_CRITERIA_NAME)
    return {
        "criteria_name": COMMON_POOL_CRITERIA_NAME,
        "criteria": criteria if isinstance(criteria, dict) else {},
        "has_criteria": isinstance(criteria, dict),
    }


def ensure_common_pool_criteria() -> tuple[str, dict]:
    """Ensures shared pool criteria entry exists (write-path)."""
    return _ensure_common_pool_criteria_impl()


def rank_search_candidates(candidates: list) -> dict:
    """Ranks and dedupes candidates by explainable quality score."""
    scored_candidates = search_ranking.rank_candidates(candidates)
    before_dedupe_count = len(scored_candidates)
    scored_candidates = dedupe_ranked_candidates_by_title_identity(scored_candidates)
    return {
        "candidates": scored_candidates,
        "before_dedupe_count": before_dedupe_count,
        "hidden_duplicates": before_dedupe_count - len(scored_candidates),
    }


SEARCH_SORT_MODES = (
    "final_score",
    "quality_score",
    "tmdb_score",
    "tmdb_votes",
    "tmdb_popularity",
    "year",
)

SEARCH_SORT_MODE_LABELS = {
    "final_score": "Итог",
    "quality_score": "Качество",
    "tmdb_score": "TMDb",
    "tmdb_votes": "Голоса TMDb",
    "tmdb_popularity": "Популярность TMDb",
    "year": "Год",
}
DEFAULT_SEARCH_SORT_MODE = "final_score"


def _sort_field_value(candidate: dict, field_name: str) -> float | None:
    from candidates.models.schema import coerce_candidate_number

    return coerce_candidate_number(candidate.get(field_name))


def _sort_candidates_by_mode(candidates: list, sort_mode: str) -> list:
    field_name = sort_mode if sort_mode in SEARCH_SORT_MODES else DEFAULT_SEARCH_SORT_MODE

    def sort_key(candidate: dict) -> tuple:
        value = _sort_field_value(candidate, field_name)
        title = str(candidate.get("title") or candidate.get("name") or "").casefold()
        if value is None:
            return (1, 0.0, title)
        return (0, -float(value), title)

    return sorted(list(candidates), key=sort_key)


def sort_search_candidates(candidates: list, sort_mode: str) -> dict:
    """Dedupes and sorts filtered candidates by a numeric pool field."""
    normalized_mode = sort_mode if sort_mode in SEARCH_SORT_MODES else DEFAULT_SEARCH_SORT_MODE
    before_dedupe_count = len(candidates)
    deduped = dedupe_ranked_candidates_by_title_identity(list(candidates))
    sorted_candidates = _sort_candidates_by_mode(deduped, normalized_mode)
    return {
        "candidates": sorted_candidates,
        "sort_mode": normalized_mode,
        "before_dedupe_count": before_dedupe_count,
        "hidden_duplicates": before_dedupe_count - len(deduped),
    }


def search_candidate_pool(candidates: list, filters: dict) -> dict:
    """Filters and ranks saved candidates for local search."""
    return search_core.search_candidates(candidates, filters)


def add_candidate_to_watchlist(candidate: dict) -> dict:
    """Adds a candidate to the local watchlist JSON."""
    return search_storage.add_to_watchlist(candidate)


def hide_candidate(candidate: dict) -> dict:
    """Adds a candidate to the local hidden JSON."""
    return search_storage.add_to_hidden(candidate)


def format_candidate_description(candidate: dict, limit: int = 200) -> str:
    """Returns truncated candidate description for UI cards."""
    return _format_candidate_description_impl(candidate, limit=limit)

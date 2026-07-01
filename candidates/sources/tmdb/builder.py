"""Build orchestration for TMDb + local IMDb SQL candidate pools."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from candidates.keys import COMMON_POOL_CRITERIA_NAME
from candidates.sources.tmdb import debug as kp_tmdb_build_debug
from candidates.sources.tmdb.discover_dedupe import (
    deduplicate_discover_results,
    remove_watched_discover,
    sort_discover_for_details,
)
from candidates.sources.tmdb.discover_query import (
    apply_discover_filters,
    discover_defaults,
    is_iso2_country_code,
    normalize_country_code,
    normalize_optional_tmdb_genre_filter,
)
from candidates.sources.tmdb.transformer import (
    NETWORK_ERROR_SKIP_THRESHOLD,
    append_signal,
    compute_final_score,
    compute_hidden_gem_score,
    compute_quality_score,
    connect_imdb,
    enrich_from_imdb_sql,
    enrich_from_kp_api_if_needed,
    enrich_from_kp_cache_only,
    mark_kp_pending_limit,
    normalize_tmdb_candidate_for_common_pool,
    passes_imdb_filters,
    prepare_candidate,
    report_progress,
)
from apis import imdb_sql as sql_search
from apis import tmdb_api as api_tmdb


def build_candidate_pool(
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
    db_path: str | Path = sql_search.DEFAULT_DB_PATH,
    kp_api_limit: int | None = None,
    kp_build_debug: bool = True,
) -> dict[str, Any]:
    country = normalize_country_code(country)
    if is_iso2_country_code(country) is False:
        raise ValueError("country must be a 2-letter ISO code")
    if mode not in {"quality", "hidden_gems"}:
        raise ValueError("mode должен быть quality или hidden_gems")
    criteria_name = str(criteria_name or "").strip() or COMMON_POOL_CRITERIA_NAME

    token = api_tmdb.load_tmdb_token()
    query = apply_discover_filters(
        discover_defaults(country),
        year_min=year_min,
        year_max=year_max,
        min_tmdb_score=min_tmdb_score,
        min_tmdb_votes=min_tmdb_votes,
        with_genres=with_genres,
        without_genres=without_genres,
    )
    report_progress("TMDb Discover", "Ожидание ответа")
    try:
        discover_results = api_tmdb.discover_tv_candidates(
            max_pages=pages,
            force_refresh=force_refresh,
            token=token,
            **query,
        )
    except Exception:
        report_progress("TMDb Discover", "Ошибка сети")
        raise
    report_progress("TMDb Discover", f"Успешно, кандидатов: {len(discover_results)}")
    unique_results, duplicates_removed = deduplicate_discover_results(discover_results)
    not_watched_results, watched_skipped = remove_watched_discover(unique_results)
    sorted_results = sort_discover_for_details(not_watched_results)
    details_candidates = sorted_results[: int(details_limit)]

    conn = connect_imdb(db_path)
    candidates: list[dict[str, Any]] = []
    stats = {
        "discover_total": len(discover_results),
        "discover_filters": {
            "year_min": year_min,
            "year_max": year_max,
            "min_tmdb_score": min_tmdb_score,
            "min_tmdb_votes": min_tmdb_votes,
            "with_genres": normalize_optional_tmdb_genre_filter(with_genres),
            "without_genres": normalize_optional_tmdb_genre_filter(without_genres),
        },
        "duplicates_removed": duplicates_removed,
        "watched_skipped": watched_skipped,
        "details_requested": len(details_candidates),
        "tmdb_details_errors": 0,
        "tmdb_details_skipped_after_errors": 0,
        "has_imdb_id": 0,
        "found_in_imdb_sql": 0,
        "country_passed": 0,
        "country_borderline": 0,
        "country_rejected": 0,
        "imdb_filter_rejected": 0,
        "adult_title_type_rejected": 0,
        "kp_cache_hit": 0,
        "kp_api_requested": 0,
        "kp_api_found": 0,
        "kp_api_not_found": 0,
        "kp_api_rejected_by_match": 0,
        "kp_api_errors": 0,
        "kp_api_skipped_after_errors": 0,
        "kp_api_skipped_cache": 0,
        "kp_pending_limit": 0,
        "kp_incomplete_candidates": 0,
        "complete_candidates": 0,
        "final_candidates": 0,
    }

    tmdb_details_consecutive_errors = 0
    tmdb_details_skip_network = False
    kp_api_consecutive_errors = 0
    kp_api_skip_network = False
    kp_debug_session = None
    if kp_build_debug:
        kp_debug_session = kp_tmdb_build_debug.KpBuildDebugSession(
            country=country,
            criteria_name=criteria_name,
        )

    try:
        for detail_index, item in enumerate(details_candidates, start=1):
            if tmdb_details_skip_network:
                stats["tmdb_details_skipped_after_errors"] += 1
                report_progress("TMDb Details", f"Пропущено [{detail_index}/{len(details_candidates)}]")
                continue

            report_progress("TMDb Details", f"Ожидание ответа [{detail_index}/{len(details_candidates)}]")
            try:
                details = api_tmdb.get_tv_details(
                    int(item["id"]),
                    language=query["language"],
                    force_refresh=force_refresh,
                    token=token,
                )
            except Exception:
                stats["tmdb_details_errors"] += 1
                tmdb_details_consecutive_errors += 1
                report_progress("TMDb Details", "Ошибка сети")
                if tmdb_details_consecutive_errors >= NETWORK_ERROR_SKIP_THRESHOLD:
                    tmdb_details_skip_network = True
                continue
            tmdb_details_consecutive_errors = 0
            report_progress("TMDb Details", f"Успешно [{detail_index}/{len(details_candidates)}]")
            candidate = prepare_candidate(details, country, source_query=query)
            if candidate.get("imdb_id"):
                stats["has_imdb_id"] += 1
            report_progress("IMDb dataset", f"Поиск [{detail_index}/{len(details_candidates)}]")
            candidate = enrich_from_imdb_sql(candidate, conn)
            if candidate.get("imdb_found_in_sql"):
                stats["found_in_imdb_sql"] += 1
                report_progress("IMDb dataset", f"Успешно [{detail_index}/{len(details_candidates)}]")
            else:
                report_progress("IMDb dataset", f"Нет кандидатов [{detail_index}/{len(details_candidates)}]")
            candidate = enrich_from_kp_cache_only(candidate)
            if "kp_cache_hit" in candidate.get("signals", []):
                stats["kp_cache_hit"] += 1
            if kp_api_skip_network:
                candidate = enrich_from_kp_api_if_needed(
                    candidate, country, stats, skip_network=True, kp_debug_session=kp_debug_session,
                )
            elif candidate.get("kp_status") == "cache_hit":
                candidate = enrich_from_kp_api_if_needed(
                    candidate, country, stats, kp_debug_session=kp_debug_session,
                )
            elif kp_api_limit is not None and stats["kp_api_requested"] >= int(kp_api_limit):
                candidate = mark_kp_pending_limit(candidate)
                report_progress("KP API", "Лимит, добрать позже")
            else:
                kp_errors_before = stats["kp_api_errors"]
                kp_requested_before = stats["kp_api_requested"]
                candidate = enrich_from_kp_api_if_needed(
                    candidate, country, stats, kp_debug_session=kp_debug_session,
                )
                if stats["kp_api_errors"] > kp_errors_before:
                    kp_api_consecutive_errors += 1
                    if kp_api_consecutive_errors >= NETWORK_ERROR_SKIP_THRESHOLD:
                        kp_api_skip_network = True
                elif stats["kp_api_requested"] > kp_requested_before:
                    kp_api_consecutive_errors = 0

            if candidate["country_score"] >= 0.70:
                stats["country_passed"] += 1
            elif candidate["country_score"] >= 0.40:
                stats["country_borderline"] += 1
                append_signal(candidate, "borderline_country_score")
            else:
                stats["country_rejected"] += 1
                continue

            passes, reason = passes_imdb_filters(candidate)
            if passes is False:
                stats["imdb_filter_rejected"] += 1
                if reason in {"adult", "title_type"}:
                    stats["adult_title_type_rejected"] += 1
                append_signal(candidate, f"rejected_{reason}")
                continue

            candidate["quality_score"] = compute_quality_score(candidate)
            candidate["hidden_gem_score"] = compute_hidden_gem_score(candidate)
            candidate["final_score"] = compute_final_score(candidate, mode)
            candidates.append(normalize_tmdb_candidate_for_common_pool(candidate, criteria_name=criteria_name))
    finally:
        if conn is not None:
            conn.close()

    candidates.sort(
        key=lambda candidate: (
            -(candidate.get("final_score") or 0),
            -(candidate.get("quality_score") or 0),
            -(candidate.get("tmdb_votes") or 0),
            candidate.get("title") or "",
        )
    )
    stats["final_candidates"] = len(candidates)
    stats["kp_pending_limit"] = sum(1 for candidate in candidates if candidate.get("kp_status") == "pending_limit")
    stats["kp_incomplete_candidates"] = sum(1 for candidate in candidates if candidate.get("is_complete") is not True)
    stats["complete_candidates"] = sum(1 for candidate in candidates if candidate.get("is_complete") is True)

    result_payload = {
        "criteria_name": criteria_name,
        "country": country,
        "mode": mode,
        "source": "tmdb_discover_imdb_sql",
        "query": query,
        "settings": {
            "criteria_name": criteria_name,
            "country": country,
            "mode": mode,
            "pages": int(pages),
            "details_limit": int(details_limit),
            "year_min": year_min,
            "year_max": year_max,
            "min_tmdb_score": min_tmdb_score,
            "min_tmdb_votes": min_tmdb_votes,
            "with_genres": normalize_optional_tmdb_genre_filter(with_genres),
            "without_genres": normalize_optional_tmdb_genre_filter(without_genres),
        },
        "stats": stats,
        "candidates": candidates,
    }
    if kp_debug_session is not None:
        result_payload["kp_debug"] = kp_debug_session.to_report()
    return result_payload


from candidates.sources.tmdb.discover_dedupe import *  # noqa: E402, F403
from candidates.sources.tmdb.discover_query import *  # noqa: E402, F403
from candidates.sources.tmdb.output import *  # noqa: E402, F403
from candidates.sources.tmdb.transformer import *  # noqa: E402, F403

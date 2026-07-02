"""TMDb-only build orchestration for candidate pool snapshots."""

from __future__ import annotations

from typing import Any

from apis import tmdb_api as api_tmdb
from candidates.models.keys import COMMON_POOL_CRITERIA_NAME
from candidates.pool.existing_index import build_existing_candidate_index, discover_item_existing_reason
from candidates.repositories.pool_repository import load_candidate_pool
from candidates.sources.tmdb.discover_dedupe import remove_watched_discover, sort_discover_for_details
from candidates.sources.tmdb.discover_query import (
    build_tmdb_criteria_name,
    is_iso2_country_code,
    normalize_country_code,
    normalize_optional_tmdb_genre_filter,
)
from candidates.sources.tmdb.discovery_strategy import build_discovery_slices, merge_discovery_results
from candidates.sources.tmdb.normalizer import prepare_tmdb_candidate
from candidates.sources.tmdb.scoring import (
    compute_metadata_completeness_score,
    compute_tmdb_final_score,
    compute_tmdb_hidden_gem_score,
    compute_tmdb_quality_score,
)


def _sort_candidates_by_scores(candidates: list[dict[str, Any]]) -> None:
    candidates.sort(
        key=lambda candidate: (
            -(candidate.get("final_score") or 0),
            -(candidate.get("quality_score") or 0),
            -(candidate.get("tmdb_votes") or 0),
            -(candidate.get("tmdb_popularity") or 0),
            candidate.get("title") or "",
        )
    )


def _unique_upper(values) -> set[str]:
    result = set()
    for value in values or []:
        text = str(value or "").strip().upper()
        if text:
            result.add(text)
    return result


def compute_country_score(candidate: dict[str, Any], target_country: str) -> tuple[float, list[str]]:
    target_country = normalize_country_code(target_country)
    codes = _unique_upper(candidate.get("country_codes"))
    language = str(candidate.get("original_language") or "").strip().casefold()
    networks = {str(item or "").strip().casefold() for item in candidate.get("networks") or []}
    companies = {str(item or "").strip().casefold() for item in candidate.get("production_companies") or []}
    score = 0.0
    signals: list[str] = []

    if target_country in codes:
        score += 0.70
        signals.append("country_code_match")
    if target_country == "RU" and language == "ru":
        score += 0.20
        signals.append("original_language_ru")
    if target_country == "RU" and networks & {"kinopoisk", "channel one", "russia-1", "ntv", "start", "premier"}:
        score += 0.05
        signals.append("russian_network")
    if target_country == "RU" and companies & {"sreda", "kinopoisk", "plus studio", "1-2-3 production"}:
        score += 0.05
        signals.append("russian_production_company")
    if target_country != "RU" and language:
        score += 0.10
        signals.append("has_original_language")

    return round(min(score, 1.0), 4), signals


def _discover_params(
    slice_query: dict[str, Any],
    *,
    language: str,
    min_tmdb_score: float | None,
    min_tmdb_votes: int | None,
    page: int,
) -> dict[str, Any]:
    params = {
        "include_adult": "false",
        "language": language,
        "page": int(page),
        "sort_by": slice_query.get("sort_by") or "vote_count.desc",
    }
    for field_name in (
        "with_origin_country",
        "with_original_language",
        "first_air_date.gte",
        "first_air_date.lte",
        "with_genres",
        "without_genres",
    ):
        value = slice_query.get(field_name)
        if value not in (None, ""):
            params[field_name] = value
    if min_tmdb_score is not None:
        params["vote_average.gte"] = float(min_tmdb_score)
    if min_tmdb_votes is not None:
        params["vote_count.gte"] = int(min_tmdb_votes)
    return params


def _fetch_discovery_slices(
    slices: list[dict[str, Any]],
    *,
    language: str,
    min_tmdb_score: float | None,
    min_tmdb_votes: int | None,
    force_refresh: bool,
    token: str,
) -> tuple[list[dict[str, Any]], int]:
    results_by_slice: list[dict[str, Any]] = []
    discover_total = 0
    for discovery_slice in slices:
        query = discovery_slice.get("query") or {}
        max_pages = int(discovery_slice.get("pages_per_slice") or query.get("max_pages") or 1)
        max_pages = max(1, max_pages)
        for page in range(1, max_pages + 1):
            params = _discover_params(
                query,
                language=language,
                min_tmdb_score=min_tmdb_score,
                min_tmdb_votes=min_tmdb_votes,
                page=page,
            )
            payload = api_tmdb.tmdb_get("/discover/tv", params=params, token=token)
            page_results = payload.get("results") if isinstance(payload, dict) else []
            page_results = page_results if isinstance(page_results, list) else []
            discover_total += len(page_results)
            results_by_slice.append({
                "slice_name": discovery_slice.get("slice_name"),
                "query": params,
                "page": page,
                "results": page_results,
            })
            total_pages = int((payload or {}).get("total_pages") or page)
            if page >= total_pages:
                break
    if force_refresh:
        # Kept as a named input for CLI/API compatibility with cache-aware callers.
        # Direct Discover requests are intentionally uncached in this TMDb-only builder.
        pass
    return results_by_slice, discover_total


def _filter_existing_discover_items(items: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int, int]:
    existing_index = build_existing_candidate_index(load_candidate_pool())
    novel_results: list[dict[str, Any]] = []
    skipped_tmdb_id = 0
    skipped_title_year = 0
    for item in items:
        existing_reason = discover_item_existing_reason(item, existing_index)
        if existing_reason == "tmdb_id":
            skipped_tmdb_id += 1
            continue
        if existing_reason == "title_year":
            skipped_title_year += 1
            continue
        novel_results.append(item)
    return novel_results, skipped_tmdb_id, skipped_title_year


def _score_candidate(candidate: dict[str, Any], country: str, mode: str) -> dict[str, Any]:
    country_score, country_signals = compute_country_score(candidate, country)
    candidate["country_score"] = country_score
    candidate["country_signals"] = country_signals
    candidate["metadata_completeness_score"] = compute_metadata_completeness_score(candidate)
    candidate["quality_score"] = compute_tmdb_quality_score(candidate)
    candidate["hidden_gem_score"] = compute_tmdb_hidden_gem_score(candidate)
    candidate["final_score"] = compute_tmdb_final_score(candidate, mode)
    return candidate


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
    skip_existing_pool: bool = True,
) -> dict[str, Any]:
    country = normalize_country_code(country)
    if is_iso2_country_code(country) is False:
        raise ValueError("country must be a 2-letter ISO code")
    if mode not in {"quality", "hidden_gems"}:
        raise ValueError("mode должен быть quality или hidden_gems")
    criteria_name = str(criteria_name or "").strip() or COMMON_POOL_CRITERIA_NAME

    token = api_tmdb.load_tmdb_token()
    language = api_tmdb.DEFAULT_LANGUAGE
    slices = build_discovery_slices(
        country,
        year_min=year_min,
        year_max=year_max,
        with_genres=with_genres,
        without_genres=without_genres,
        pages_per_slice=pages,
    )
    results_by_slice, discover_total = _fetch_discovery_slices(
        slices,
        language=language,
        min_tmdb_score=min_tmdb_score,
        min_tmdb_votes=min_tmdb_votes,
        force_refresh=force_refresh,
        token=token,
    )
    merged_results = merge_discovery_results(results_by_slice)
    duplicates_removed = max(0, discover_total - len(merged_results))
    not_watched_results, watched_skipped = remove_watched_discover(merged_results)
    if skip_existing_pool:
        novel_results, existing_pool_skipped_tmdb_id, existing_pool_skipped_title_year = _filter_existing_discover_items(
            not_watched_results
        )
    else:
        novel_results = not_watched_results
        existing_pool_skipped_tmdb_id = 0
        existing_pool_skipped_title_year = 0

    details_candidates = sort_discover_for_details(novel_results)[: int(details_limit)]
    candidates: list[dict[str, Any]] = []
    details_errors = 0
    external_ids_imdb_id_count = 0

    for item in details_candidates:
        try:
            details = api_tmdb.get_tv_details(
                int(item["id"]),
                language=language,
                append_to_response=api_tmdb.DEFAULT_TV_DETAIL_APPENDS,
                force_refresh=force_refresh,
                token=token,
            )
        except Exception:
            details_errors += 1
            continue

        candidate = prepare_tmdb_candidate(
            details,
            country=country,
            source_query={
                "country": country,
                "language": language,
                "min_tmdb_score": min_tmdb_score,
                "min_tmdb_votes": min_tmdb_votes,
                "with_genres": normalize_optional_tmdb_genre_filter(with_genres),
                "without_genres": normalize_optional_tmdb_genre_filter(without_genres),
            },
            source_trace=item.get("source_trace"),
        )
        if candidate.get("imdb_id"):
            external_ids_imdb_id_count += 1
        candidate = _score_candidate(candidate, country, mode)
        candidates.append(candidate)

    _sort_candidates_by_scores(candidates)
    stats = {
        "source": "tmdb",
        "source_version": 2,
        "discover_total": discover_total,
        "duplicates_removed": duplicates_removed,
        "watched_skipped": watched_skipped,
        "existing_pool_skipped_tmdb_id": existing_pool_skipped_tmdb_id,
        "existing_pool_skipped_title_year": existing_pool_skipped_title_year,
        "details_requested": len(details_candidates),
        "details_errors": details_errors,
        "external_ids_imdb_id_count": external_ids_imdb_id_count,
        "complete_candidates": sum(1 for candidate in candidates if candidate.get("is_complete") is True),
        "incomplete_candidates": sum(1 for candidate in candidates if candidate.get("is_complete") is not True),
        "final_candidates": len(candidates),
    }

    return {
        "criteria_name": criteria_name,
        "country": country,
        "mode": mode,
        "source": "tmdb",
        "source_provider": "tmdb",
        "source_version": 2,
        "query": {
            "country": country,
            "language": language,
            "slices": slices,
            "min_tmdb_score": min_tmdb_score,
            "min_tmdb_votes": min_tmdb_votes,
            "with_genres": normalize_optional_tmdb_genre_filter(with_genres),
            "without_genres": normalize_optional_tmdb_genre_filter(without_genres),
        },
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
            "skip_existing_pool": bool(skip_existing_pool),
        },
        "stats": stats,
        "candidates": candidates,
    }


def build_tmdb_candidate_pool(**kwargs) -> dict[str, Any]:
    return build_candidate_pool(**kwargs)


def save_candidate_pool_result(result: dict[str, Any]):
    from candidates.sources.tmdb.output import save_candidate_pool_result as save_result

    return save_result(result)


def save_candidate_pool_test_result(result: dict[str, Any]):
    from candidates.sources.tmdb.output import save_candidate_pool_test_result as save_result

    return save_result(result)


def build_summary_lines(result: dict[str, Any]) -> list[str]:
    from candidates.sources.tmdb.output import build_summary_lines as build_lines

    return build_lines(result)

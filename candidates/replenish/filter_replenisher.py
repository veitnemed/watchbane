"""Domain pipeline for filter-driven candidate replenish."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from candidates.models.keys import pool_entry_key, title_identity_key
from candidates.models.schema import normalize_candidate_for_storage
from candidates.replenish.compatibility import resolve_filter_replenish_compatibility
from candidates.replenish.filter_discover import build_filter_discover_params
from candidates.replenish.filter_intent import FilterReplenishIntent
from candidates.replenish.filter_plan import build_filter_replenish_plan
from candidates.replenish.result import FilterReplenishResult
from candidates.sources.tmdb.scoring import (
    compute_metadata_completeness_score,
    compute_tmdb_final_score,
    compute_tmdb_hidden_gem_score,
    compute_tmdb_quality_score,
)
from candidates.sources.tmdb.normalizer import prepare_tmdb_candidate, prepare_tmdb_movie_candidate


def _as_intent(intent: FilterReplenishIntent | dict[str, Any]) -> FilterReplenishIntent:
    if isinstance(intent, FilterReplenishIntent):
        return intent
    return FilterReplenishIntent.from_dict(intent)


def _safe_int(value: Any) -> int | None:
    try:
        if value in (None, ""):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _year_from_date(value: Any) -> int | None:
    text = str(value or "").strip()
    if len(text) >= 4 and text[:4].isdigit():
        return int(text[:4])
    return None


def _scenario_set(tmdb_client: Any, name: str) -> set[int]:
    scenario = getattr(tmdb_client, "scenario", None)
    return {int(value) for value in getattr(scenario, name, ()) or ()}


def _tmdb_id_set(values: Any) -> set[int]:
    result: set[int] = set()
    for value in values or ():
        number = _safe_int(value)
        if number is not None:
            result.add(number)
    return result


def _existing_indexes(existing_pool: dict[str, Any] | list[dict[str, Any]] | None) -> tuple[set[tuple[str, int]], set[str]]:
    values = existing_pool.values() if isinstance(existing_pool, dict) else existing_pool or []
    tmdb_ids: set[tuple[str, int]] = set()
    title_keys: set[str] = set()
    for candidate in values:
        if isinstance(candidate, dict) is False:
            continue
        tmdb_id = _safe_int(candidate.get("tmdb_id"))
        media_type = str(candidate.get("media_type") or "").strip()
        if tmdb_id is not None and media_type:
            tmdb_ids.add((media_type, tmdb_id))
        title_keys.add(title_identity_key(candidate))
    return tmdb_ids, title_keys


def _raw_title(raw: dict[str, Any], media_type: str) -> str:
    if media_type == "tv":
        return str(raw.get("name") or raw.get("title") or raw.get("original_name") or "").strip()
    return str(raw.get("title") or raw.get("name") or raw.get("original_title") or "").strip()


def _raw_date(raw: dict[str, Any], media_type: str) -> str:
    if media_type == "tv":
        return str(raw.get("first_air_date") or "").strip()
    return str(raw.get("release_date") or "").strip()


def _has_value(value: Any) -> bool:
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) > 0
    return value is not None and str(value).strip() != ""


def _finalize_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_candidate_for_storage(candidate)
    normalized["metadata_completeness_score"] = compute_metadata_completeness_score(normalized)
    normalized["quality_score"] = compute_tmdb_quality_score(normalized)
    normalized["hidden_gem_score"] = compute_tmdb_hidden_gem_score(normalized)
    normalized["final_score"] = compute_tmdb_final_score(normalized)
    normalized["pool_entry_key"] = pool_entry_key(normalized)
    return normalized


def _candidate_from_discover(raw: dict[str, Any], *, media_type: str, bucket: dict[str, Any]) -> dict[str, Any]:
    title = _raw_title(raw, media_type)
    date_value = _raw_date(raw, media_type)
    year = _year_from_date(date_value)
    tmdb_id = _safe_int(raw.get("id"))
    origin_country = list(raw.get("origin_country") or [])
    if not origin_country and bucket.get("country"):
        origin_country = [bucket["country"]]
    candidate = {
        "title": title,
        "alternative_title": raw.get("original_title") or raw.get("original_name"),
        "year": year,
        "media_type": media_type,
        "type": "series" if media_type == "tv" else "movie",
        "description": raw.get("overview") or "",
        "overview": raw.get("overview") or "",
        "countries": origin_country,
        "country_codes": origin_country,
        "origin_country": origin_country,
        "genre_ids": list(raw.get("genre_ids") or []),
        "criteria_name": "pool",
        "source": "tmdb_filter_replenish",
        "source_provider": "tmdb",
        "source_version": 2,
        "source_bucket_id": bucket.get("bucket_id"),
        "target_country": bucket.get("country"),
        "tmdb_id": tmdb_id,
        "tmdb_score": raw.get("vote_average"),
        "tmdb_votes": raw.get("vote_count"),
        "tmdb_popularity": raw.get("popularity"),
        "original_language": raw.get("original_language"),
    }
    if media_type == "tv":
        candidate["first_air_date"] = date_value
    else:
        candidate["release_date"] = date_value
    return _finalize_candidate(candidate)


def _candidate_reject_reason(candidate: dict[str, Any]) -> str | None:
    if candidate.get("tmdb_id") in (None, ""):
        return "missing_tmdb_id"
    if not str(candidate.get("title") or "").strip():
        return "missing_title"
    if candidate.get("year") is None:
        return "missing_year"
    return None


def _sort_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        candidates,
        key=lambda candidate: (
            -float(candidate.get("final_score") or 0.0),
            -float(candidate.get("tmdb_popularity") or 0.0),
            str(candidate.get("title") or ""),
        ),
    )


def _normalized_detail_candidate(details: dict[str, Any], media_type: str, language: str) -> dict[str, Any]:
    source_query = {"language": language}
    if media_type == "movie":
        return prepare_tmdb_movie_candidate(details, source_query=source_query)
    return prepare_tmdb_candidate(details, source_query=source_query)


def _merge_details_into_candidate(
    candidate: dict[str, Any],
    details: dict[str, Any],
    *,
    language: str,
) -> dict[str, Any]:
    if isinstance(details, dict) is False or len(details) == 0:
        return candidate

    media_type = str(candidate.get("media_type") or "tv")
    detail_candidate = _normalized_detail_candidate(details, media_type, language)
    updated = dict(candidate)

    detail_genres = list(detail_candidate.get("genres") or [])
    if detail_genres:
        updated["genres"] = deepcopy(detail_genres)
        updated["genres_tmdb"] = deepcopy(detail_genres)

    for field_name in (
        "genre_keys",
        "localized",
        "poster_path",
        "poster_url",
        "backdrop_path",
        "backdrop_url",
        "runtime",
        "runtime_minutes",
        "episode_run_time",
        "number_of_seasons",
        "number_of_episodes",
        "status",
        "type",
        "in_production",
        "content_rating",
        "watch_providers",
        "networks",
        "production_companies",
        "actors_top",
        "crew_top",
        "keywords",
        "imdb_id",
    ):
        value = detail_candidate.get(field_name)
        if _has_value(value):
            updated[field_name] = deepcopy(value)

    return _finalize_candidate(updated)


def _maybe_fetch_details(tmdb_client: Any, candidate: dict[str, Any], *, language: str) -> dict[str, Any] | None:
    details = getattr(tmdb_client, "details", None)
    if details is None:
        return None
    payload = details(candidate.get("media_type"), int(candidate["tmdb_id"]), language=language)
    return _merge_details_into_candidate(candidate, payload, language=language)


def replenish_candidates_for_filters(
    intent: FilterReplenishIntent | dict[str, Any],
    *,
    limit: int = 30,
    tmdb_client=None,
    progress_callback=None,
    cancel_checker=None,
    dry_run: bool = False,
    existing_pool: dict[str, Any] | list[dict[str, Any]] | None = None,
    watched_tmdb_ids: set[int] | list[int] | tuple[int, ...] | None = None,
    hidden_tmdb_ids: set[int] | list[int] | tuple[int, ...] | None = None,
) -> dict[str, Any]:
    """Fetch and select candidates for a filter replenish run without saving."""
    normalized = _as_intent(intent)
    safe_limit = max(1, min(30, int(limit or normalized.target_add_count)))
    compatibility = resolve_filter_replenish_compatibility(normalized)
    if compatibility["blocking_conflicts"] and normalized.allow_advanced_override is False:
        return FilterReplenishResult(
            ok=False,
            dry_run=dry_run,
            blocked=True,
            requested_count=safe_limit,
            compatibility=compatibility,
            plan={},
        ).to_dict()

    if tmdb_client is None:
        return FilterReplenishResult(
            ok=False,
            dry_run=dry_run,
            requested_count=safe_limit,
            compatibility=compatibility,
            error="tmdb_client_required",
        ).to_dict()

    plan = build_filter_replenish_plan(normalized)
    existing_tmdb_keys, existing_title_keys = _existing_indexes(existing_pool)
    existing_scenario_ids = _scenario_set(tmdb_client, "existing_tmdb_ids")
    watched_ids = _tmdb_id_set(watched_tmdb_ids) | _scenario_set(tmdb_client, "watched_tmdb_ids")
    hidden_ids = _tmdb_id_set(hidden_tmdb_ids) | _scenario_set(tmdb_client, "hidden_tmdb_ids")
    seen_tmdb_keys: set[tuple[str, int]] = set()
    seen_title_keys: set[str] = set()
    selected: list[dict[str, Any]] = []
    bucket_results: list[dict[str, Any]] = []
    discover_params_sample: list[dict[str, Any]] = []
    counters = {
        "duplicate_count": 0,
        "existing_skipped": 0,
        "watched_skipped": 0,
        "hidden_skipped": 0,
        "rejected_count": 0,
        "raw_seen_count": 0,
        "api_requests": 0,
        "details_requests": 0,
    }

    for bucket in plan["buckets"]:
        if len(selected) >= safe_limit:
            break
        if cancel_checker is not None and cancel_checker():
            return FilterReplenishResult(
                ok=False,
                dry_run=dry_run,
                cancelled=True,
                requested_count=safe_limit,
                created_count=len(selected),
                candidates=_sort_candidates(selected),
                compatibility=compatibility,
                plan=plan,
                bucket_results=bucket_results,
                discover_params_sample=discover_params_sample,
                **counters,
            ).to_dict()

        bucket_counter = {
            "bucket_id": bucket.get("bucket_id"),
            "quota": int(bucket.get("quota") or 0),
            "accepted_count": 0,
            "raw_seen_count": 0,
            "duplicate_count": 0,
            "existing_skipped": 0,
            "watched_skipped": 0,
            "hidden_skipped": 0,
            "rejected_count": 0,
            "api_requests": 0,
        }
        bucket_target = min(int(bucket.get("quota") or 0), safe_limit - len(selected))
        for page in range(1, int(bucket.get("max_pages") or 1) + 1):
            if bucket_counter["accepted_count"] >= bucket_target or len(selected) >= safe_limit:
                break
            params = build_filter_discover_params(bucket, page, intent=plan["intent"])
            if len(discover_params_sample) < 5:
                discover_params_sample.append(dict(params))
            response = tmdb_client.discover(str(bucket.get("media_type") or "movie"), params)
            counters["api_requests"] += 1
            bucket_counter["api_requests"] += 1
            results = list((response or {}).get("results") or [])
            counters["raw_seen_count"] += len(results)
            bucket_counter["raw_seen_count"] += len(results)
            if progress_callback is not None:
                progress_callback({
                    "bucket_id": bucket.get("bucket_id"),
                    "page": page,
                    "raw_seen_count": len(results),
                    "accepted_count": bucket_counter["accepted_count"],
                    "selected_count": len(selected),
                    "target_count": safe_limit,
                    "stage": "page",
                })
            for raw in results:
                if bucket_counter["accepted_count"] >= bucket_target or len(selected) >= safe_limit:
                    break
                if isinstance(raw, dict) is False:
                    counters["rejected_count"] += 1
                    bucket_counter["rejected_count"] += 1
                    continue
                candidate = _candidate_from_discover(raw, media_type=str(bucket["media_type"]), bucket=bucket)
                reject_reason = _candidate_reject_reason(candidate)
                if reject_reason is not None:
                    counters["rejected_count"] += 1
                    bucket_counter["rejected_count"] += 1
                    continue
                tmdb_key = (str(candidate.get("media_type")), int(candidate["tmdb_id"]))
                title_key = title_identity_key(candidate)
                if int(candidate["tmdb_id"]) in watched_ids:
                    counters["watched_skipped"] += 1
                    bucket_counter["watched_skipped"] += 1
                    continue
                if int(candidate["tmdb_id"]) in hidden_ids:
                    counters["hidden_skipped"] += 1
                    bucket_counter["hidden_skipped"] += 1
                    continue
                if (
                    tmdb_key in existing_tmdb_keys
                    or title_key in existing_title_keys
                    or int(candidate["tmdb_id"]) in existing_scenario_ids
                ):
                    counters["existing_skipped"] += 1
                    bucket_counter["existing_skipped"] += 1
                    continue
                if tmdb_key in seen_tmdb_keys or title_key in seen_title_keys:
                    counters["duplicate_count"] += 1
                    bucket_counter["duplicate_count"] += 1
                    continue
                language = params.get("language") or "ru-RU"
                detailed_candidate = _maybe_fetch_details(tmdb_client, candidate, language=str(language))
                if detailed_candidate is not None:
                    counters["details_requests"] += 1
                    candidate = detailed_candidate
                seen_tmdb_keys.add(tmdb_key)
                seen_title_keys.add(title_key)
                selected.append(candidate)
                bucket_counter["accepted_count"] += 1
                if progress_callback is not None:
                    progress_callback({
                        "bucket_id": bucket.get("bucket_id"),
                        "page": page,
                        "raw_seen_count": len(results),
                        "accepted_count": bucket_counter["accepted_count"],
                        "selected_count": len(selected),
                        "target_count": safe_limit,
                        "stage": "accepted",
                    })
            total_pages = int((response or {}).get("total_pages") or page)
            if page >= total_pages:
                break
        bucket_results.append(bucket_counter)

    selected = _sort_candidates(selected)[:safe_limit]
    return FilterReplenishResult(
        ok=True,
        dry_run=dry_run,
        requested_count=safe_limit,
        created_count=len(selected),
        saved_count=0,
        candidates=selected,
        compatibility=compatibility,
        plan=plan,
        bucket_results=bucket_results,
        discover_params_sample=discover_params_sample,
        **counters,
    ).to_dict()

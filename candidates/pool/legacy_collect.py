"""Legacy KP Discover collect into shared candidate pool."""

from __future__ import annotations

import time
from datetime import datetime

from apis import kp_api as api
from candidates.keys import COMMON_POOL_CRITERIA_NAME, pool_entry_key
from candidates.pool.normalization import normalize_storage_pool
from candidates.pool.watched_cleanup import (
    build_dataset_title_keys,
    build_watched_signatures,
    is_watched_candidate,
)
from candidates.schema import normalize_candidate_for_storage

DISCOVER_PAGE_LIMIT = 30
DISCOVER_PAGE_PAUSE_SECONDS = 1.0


def movie_matches_genres(movie: dict, expected_genres: list, excluded_genres: list | None = None) -> bool:
    """Проверяет обязательные и исключенные жанры кандидата."""
    if excluded_genres is None:
        excluded_genres = []
    actual = {
        str(item.get("name", "")).strip().casefold()
        for item in movie.get("genres", []) or []
        if isinstance(item, dict) and item.get("name")
    }
    blocked = {genre.casefold() for genre in excluded_genres}
    if len(actual & blocked) > 0:
        return False
    if len(expected_genres) == 0:
        return True
    wanted = {genre.casefold() for genre in expected_genres}
    return len(actual & wanted) > 0


def normalize_candidate(movie: dict, criteria_name: str) -> dict:
    """Оставляет в пуле кандидатов полезные поля."""
    return normalize_candidate_for_storage({
        "id": movie.get("id"),
        "title": movie.get("name") or movie.get("alternativeName") or movie.get("enName"),
        "alternative_title": movie.get("alternativeName") or movie.get("enName"),
        "year": movie.get("year"),
        "type": movie.get("type"),
        "description": movie.get("shortDescription") or movie.get("description"),
        "kp_score": api.safe_nested(movie, "rating", "kp"),
        "kp_votes": api.safe_nested(movie, "votes", "kp"),
        "imdb_score": api.safe_nested(movie, "rating", "imdb"),
        "imdb_votes": api.safe_nested(movie, "votes", "imdb"),
        "countries": [item.get("name") for item in movie.get("countries", []) or [] if isinstance(item, dict) and item.get("name")],
        "genres": [item.get("name") for item in movie.get("genres", []) or [] if isinstance(item, dict) and item.get("name")],
        "criteria_name": criteria_name,
        "saved_at": datetime.now().isoformat(timespec="seconds"),
    })


def collect_candidates(criteria_name: str, criteria: dict) -> dict:
    """Собирает новых кандидатов из API в общий pool."""
    from candidates import candidate_pool as pool_compat

    criteria_name = COMMON_POOL_CRITERIA_NAME
    pool = normalize_storage_pool(pool_compat.load_candidate_pool())
    watched_signatures = build_watched_signatures()
    dataset_title_keys = build_dataset_title_keys()
    target_count = int(criteria.get("count") or 20)
    availability = api.check_api_available()
    if availability["ok"] is False:
        return {
            "criteria_name": criteria_name,
            "target_count": target_count,
            "added": 0,
            "duplicates": 0,
            "watched_skipped": 0,
            "scanned": 0,
            "last_page": 0,
            "pool_size": len(pool),
            "errors": [availability["details"]],
            "reached_end": False,
            "api_unavailable": True,
        }

    page = 1
    scanned = 0
    added = 0
    duplicates = 0
    watched_skipped = 0
    errors = []
    reached_end = False

    while added < target_count and page <= 20:
        result = api.discover_series_by_filters(criteria, page=page, limit=DISCOVER_PAGE_LIMIT)
        if result["ok"] is False:
            errors.append(result["details"] or result["error"] or "unknown_error")
            break

        docs = result["data"]
        if len(docs) == 0:
            reached_end = True
            break

        for movie in docs:
            scanned += 1

            if movie_matches_genres(
                movie,
                criteria.get("genres", []),
                criteria.get("excluded_genres", []),
            ) is False:
                continue

            candidate = normalize_candidate(movie, criteria_name)
            if is_watched_candidate(candidate, watched_signatures, dataset_title_keys):
                watched_skipped += 1
                continue

            key = pool_entry_key(candidate)
            if key in pool:
                duplicates += 1
                continue

            pool[key] = candidate
            added += 1

            if added >= target_count:
                break

        page += 1
        if added < target_count:
            time.sleep(DISCOVER_PAGE_PAUSE_SECONDS)

    pool_compat.save_candidate_pool(pool)
    return {
        "criteria_name": criteria_name,
        "target_count": target_count,
        "added": added,
        "duplicates": duplicates,
        "watched_skipped": watched_skipped,
        "scanned": scanned,
        "last_page": page,
        "pool_size": len(pool),
        "errors": errors,
        "reached_end": reached_end,
        "api_unavailable": False,
    }

"""Pool statistics and analytics rows."""

from __future__ import annotations

from collections import defaultdict

from candidates import genre_schema
from candidates.pool.dedupe import (
    candidate_title,
    dedupe_pool_by_similar_titles,
    dedupe_pool_cross_year_titles,
)
from candidates.pool.normalization import normalize_storage_pool
from candidates.pool.queries import get_all_candidates
from candidates.pool.watched_cleanup import (
    build_dataset_title_keys,
    build_watched_signatures,
    is_watched_candidate,
)
from candidates.schema import (
    is_candidate_complete as schema_is_candidate_complete,
    normalize_candidate_record,
)


POOL_GENRE_COUNT_CHART_LIMIT = 15
POOL_GENRE_COUNT_TITLE_LIMIT = 3


def _count_raw_pool_entries(raw_pool: dict, criteria_name: str | None = None) -> int:
    if isinstance(raw_pool, dict) is False:
        return 0
    if criteria_name is None:
        return len(raw_pool)
    return sum(
        1
        for candidate in raw_pool.values()
        if isinstance(candidate, dict) and candidate.get("criteria_name") == criteria_name
    )


def get_pool_stats(criteria_name: str | None = None) -> dict:
    """Возвращает согласованные счётчики pool для UI и диагностики."""
    from candidates import candidate_pool as pool_compat

    raw_pool = pool_compat.load_candidate_pool()
    storage_pool = normalize_storage_pool(raw_pool)
    watched_signatures = build_watched_signatures()
    dataset_title_keys = build_dataset_title_keys()

    candidates = [
        candidate
        for candidate in storage_pool.values()
        if isinstance(candidate, dict)
        and (criteria_name is None or candidate.get("criteria_name") == criteria_name)
    ]

    unique_total = len(candidates)
    raw_total = _count_raw_pool_entries(raw_pool, criteria_name=criteria_name)
    duplicate_entries = max(0, raw_total - unique_total)
    similar_duplicate_total = 0
    cross_year_duplicate_total = 0
    if criteria_name is None and unique_total > 1:
        _, similar_duplicate_total = dedupe_pool_by_similar_titles(storage_pool)
        _, cross_year_duplicate_total = dedupe_pool_cross_year_titles(storage_pool)

    watched_total = sum(
        1 for candidate in candidates
        if is_watched_candidate(candidate, watched_signatures, dataset_title_keys)
    )
    ready_total = sum(
        1 for candidate in candidates
        if schema_is_candidate_complete(candidate)
    )
    incomplete_total = unique_total - ready_total

    return {
        "criteria_name": criteria_name,
        "raw_total": raw_total,
        "unique_total": unique_total,
        "storage_total": unique_total,
        "duplicate_entries": duplicate_entries,
        "similar_duplicate_total": similar_duplicate_total,
        "cross_year_duplicate_total": cross_year_duplicate_total,
        "watched_total": watched_total,
        "active_total": unique_total - watched_total,
        "ready_total": ready_total,
        "incomplete_total": incomplete_total,
    }


def build_pool_genre_count_rows(
    candidates: list | None = None,
    *,
    limit: int = POOL_GENRE_COUNT_CHART_LIMIT,
    title_limit: int = POOL_GENRE_COUNT_TITLE_LIMIT,
) -> list[dict]:
    """Count unique pool candidates per display genre label."""
    if candidates is None:
        candidates = get_all_candidates()

    grouped: dict[str, list[str]] = defaultdict(list)
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        normalized = normalize_candidate_record(candidate)
        title = candidate_title(normalized)
        for genre in genre_schema.candidate_genres_for_display(normalized):
            grouped[genre].append(title)

    rows = [
        {
            "label": genre,
            "count": len(titles),
            "example_titles": titles[:title_limit],
            "extra_count": max(0, len(titles) - title_limit),
        }
        for genre, titles in grouped.items()
    ]
    rows.sort(key=lambda row: (-int(row["count"]), str(row["label"]).casefold()))
    return rows[:limit]

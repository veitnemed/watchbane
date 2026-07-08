"""SQLite persistence facade for runtime candidate criteria."""

from __future__ import annotations

from datetime import datetime

from candidates.models.keys import COMMON_POOL_CRITERIA_NAME
from candidates.repositories import pool_repository


def init_candidate_criteria() -> None:
    """Ensure candidate criteria tables exist."""
    from storage.sqlite.migrations import apply_migrations

    apply_migrations()


def load_candidate_criteria() -> dict:
    """Load runtime candidate criteria from SQLite."""
    from storage.sqlite.candidate_repository import load_candidate_criteria_dict

    return load_candidate_criteria_dict()


def save_candidate_criteria(data: dict) -> None:
    """Save runtime candidate criteria to SQLite."""
    from storage.sqlite.candidate_repository import save_candidate_criteria_dict

    save_candidate_criteria_dict(data)


def save_named_criteria(criteria_name: str, criteria: dict) -> tuple[str, dict]:
    """Save one named criteria entry and return it."""
    all_criteria = load_candidate_criteria()
    all_criteria[criteria_name] = criteria
    save_candidate_criteria(all_criteria)
    return criteria_name, criteria


def patch_criteria_filters(
    criteria_name: str,
    current: dict,
    *,
    min_tmdb_score,
    genres: list,
    excluded_genres: list,
) -> dict:
    """Update only filter fields for a criteria entry."""
    all_criteria = load_candidate_criteria()

    updated = dict(current)
    updated["min_tmdb_score"] = min_tmdb_score
    updated["genres"] = genres
    updated["excluded_genres"] = excluded_genres
    updated["updated_at"] = datetime.now().isoformat(timespec="seconds")

    all_criteria[criteria_name] = updated
    save_candidate_criteria(all_criteria)
    return updated


def build_criteria_label(criteria_name: str, criteria: dict) -> str:
    """Build a compact label for one criteria entry."""
    parts = [criteria_name]
    if criteria.get("count"):
        parts.append(f"count={criteria['count']}")
    if criteria.get("min_tmdb_score") is not None:
        parts.append(f"TMDb>={criteria['min_tmdb_score']}")
    if criteria.get("min_year") is not None:
        parts.append(f"year>={criteria['min_year']}")
    if criteria.get("country"):
        parts.append(criteria["country"])
    if criteria.get("genres"):
        parts.append(f"genres={len(criteria['genres'])}")
    if criteria.get("excluded_genres"):
        parts.append(f"excluded={len(criteria['excluded_genres'])}")
    return " | ".join(parts)


def ensure_common_pool_criteria() -> tuple[str, dict]:
    """Return the shared criteria entry, creating it when missing."""
    all_criteria = load_candidate_criteria()
    existing = all_criteria.get(COMMON_POOL_CRITERIA_NAME)
    if isinstance(existing, dict):
        return COMMON_POOL_CRITERIA_NAME, existing

    criteria = {
        "country": None,
        "count": 50,
        "min_tmdb_score": None,
        "min_year": None,
        "max_year": None,
        "genres": [],
        "excluded_genres": [],
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    return save_named_criteria(COMMON_POOL_CRITERIA_NAME, criteria)


def clear_common_pool() -> dict:
    """Remove all candidates from the shared pool without touching watched data."""
    pool = pool_repository.load_candidate_pool()
    cleared = len(pool)
    pool_repository.save_candidate_pool({})
    return {"ok": True, "cleared": cleared}


def delete_criteria_and_candidates(criteria_name: str) -> dict:
    """Delete a criteria entry and all candidates associated with it."""
    from candidates.pool.normalization import normalize_storage_pool

    all_criteria = load_candidate_criteria()
    if criteria_name not in all_criteria:
        return {
            "deleted_criteria": False,
            "deleted_candidates": 0,
        }

    all_criteria.pop(criteria_name, None)
    save_candidate_criteria(all_criteria)

    pool = normalize_storage_pool(pool_repository.load_candidate_pool())
    filtered_pool = {}
    deleted_candidates = 0
    for key, candidate in pool.items():
        if candidate.get("criteria_name") == criteria_name:
            deleted_candidates += 1
            continue
        filtered_pool[key] = candidate
    pool_repository.save_candidate_pool(filtered_pool)

    return {
        "deleted_criteria": True,
        "deleted_candidates": deleted_candidates,
    }

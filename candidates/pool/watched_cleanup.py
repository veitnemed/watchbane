"""Remove watched candidates from saved pool on write-path."""

from __future__ import annotations

from candidates.models.keys import title_identity_key
from candidates.pool.dataset_overlap import build_dataset_title_keys, is_dataset_title_match
from candidates.pool.dedupe import (
    candidates_are_same,
    compact_title_key,
    normalized_title_key,
    titles_are_similar,
)
from candidates.pool.normalization import normalize_storage_pool


def build_watched_signatures() -> set:
    """Собирает сигнатуры уже просмотренных объектов из основного датасета."""
    from storage import data as storage_data

    dataset = storage_data.load_dataset()
    signatures = set()
    for movie in dataset.values():
        main_info = movie.get("main_info", {})
        signature = title_identity_key({
            "title": main_info.get("title"),
            "year": main_info.get("year"),
        })
        if signature != "|":
            signatures.add(signature)
    return signatures


def is_watched_candidate(
    candidate: dict,
    watched_signatures: set | None = None,
    dataset_title_keys: set[str] | None = None,
) -> bool:
    """Проверяет, есть ли кандидат уже в основном датасете."""
    if is_dataset_title_match(candidate, dataset_title_keys):
        return True

    if watched_signatures is None:
        watched_signatures = build_watched_signatures()

    title = normalized_title_key(candidate.get("title") or candidate.get("alternative_title") or "")
    year = candidate.get("year") or ""
    exact_signature = title_identity_key(candidate)
    if exact_signature in watched_signatures:
        return True

    candidate_compact = compact_title_key(title)
    for watched_signature in watched_signatures:
        watched_title, _, watched_year = watched_signature.partition("|")
        if str(watched_year) != str(year):
            continue
        if titles_are_similar(candidate_compact, watched_title):
            return True
    return False


def remove_watched_candidates(pool: dict) -> dict:
    """Удаляет из пула кандидатов уже просмотренные объекты."""
    watched_signatures = build_watched_signatures()
    dataset_title_keys = build_dataset_title_keys()
    filtered = {}
    for key, candidate in pool.items():
        if is_watched_candidate(
            candidate,
            watched_signatures,
            dataset_title_keys=dataset_title_keys,
        ):
            continue
        filtered[key] = candidate
    return filtered


def purge_watched_from_pool(pool: dict) -> dict:
    """Удаляет просмотренных кандидатов из пула (write-path only)."""
    return remove_watched_candidates(pool)


def remove_candidate_from_pool(target_candidate: dict) -> int:
    """Удаляет из общего пула все варианты кандидата, совпадающие по названию и году."""
    from candidates import candidate_pool as pool_compat

    pool = normalize_storage_pool(pool_compat.load_candidate_pool())
    filtered_pool = {}
    removed = 0

    for key, candidate in pool.items():
        if candidates_are_same(candidate, target_candidate, include_criteria=False):
            removed += 1
            continue
        filtered_pool[key] = candidate

    if removed > 0:
        pool_compat.save_candidate_pool(filtered_pool)
    return removed

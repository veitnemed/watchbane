"""Exact, fuzzy, and cross-year deduplication for saved candidate pool."""

from __future__ import annotations

from difflib import SequenceMatcher

from candidates.models.keys import normalize_key_part, pool_entry_key, title_identity_key
from candidates.models.schema import normalize_candidate_for_storage, resolve_canonical_year
from candidates.scoring.sort_keys import candidate_sort_score
from dataset.models.media_type import normalize_media_type


def candidate_key(movie: dict) -> str:
    """Строит стабильный ключ кандидата для дедупликации."""
    return title_identity_key(movie)


def normalized_title_key(title: str) -> str:
    """Нормализует название для дедупликации кандидатов."""
    return normalize_key_part(title)


def compact_title_key(title: str) -> str:
    """Возвращает компактное название без пробелов для мягкого сравнения."""
    return normalized_title_key(title).replace(" ", "")


def titles_are_similar(left_title: str, right_title: str) -> bool:
    """Проверяет, что два названия достаточно похожи для дедупликации."""
    left = normalized_title_key(left_title)
    right = normalized_title_key(right_title)
    if left == "" or right == "":
        return False
    if left == right:
        return True

    left_compact = compact_title_key(left)
    right_compact = compact_title_key(right)
    if left_compact == right_compact:
        return True

    ratio = SequenceMatcher(None, left_compact, right_compact).ratio()
    if ratio >= 0.92:
        return True

    left_tokens = set(left.split())
    right_tokens = set(right.split())
    if left_tokens and right_tokens and left_tokens == right_tokens:
        return True

    return False


def candidate_pool_key(candidate: dict) -> str:
    """Строит ключ дедупликации для уже сохраненного кандидата."""
    return pool_entry_key(candidate)


def candidate_title(candidate: dict) -> str:
    """Возвращает лучшее доступное название кандидата."""
    return (
        candidate.get("title")
        or candidate.get("alternative_title")
        or candidate.get("name")
        or candidate.get("alternativeName")
        or candidate.get("enName")
        or ""
    )


def candidates_are_same(candidate: dict, other_candidate: dict, include_criteria: bool = True) -> bool:
    """Проверяет, относятся ли два кандидата к одному сериалу."""
    if include_criteria and (candidate.get("criteria_name") or "") != (other_candidate.get("criteria_name") or ""):
        return False
    if normalize_media_type(candidate.get("media_type")) != normalize_media_type(other_candidate.get("media_type")):
        return False

    left_year = candidate.get("year") or ""
    right_year = other_candidate.get("year") or ""
    if left_year != right_year:
        return False

    return titles_are_similar(candidate_title(candidate), candidate_title(other_candidate))


def deduplicate_pool(pool: dict) -> dict:
    """Удаляет дубли из пула, оставляя лучший вариант по рейтингу и голосам."""
    deduplicated = {}
    for candidate in pool.values():
        if isinstance(candidate, dict) is False:
            continue
        candidate = normalize_candidate_for_storage(candidate)
        key = pool_entry_key(candidate)
        current_best = deduplicated.get(key)
        if current_best is None or candidate_sort_score(candidate) > candidate_sort_score(current_best):
            deduplicated[key] = candidate
    return deduplicated


def dedupe_pool_by_similar_titles(pool: dict) -> tuple[dict, int]:
    """Сливает кандидатов одного года с похожими названиями, оставляя лучшую запись."""
    candidates = [
        normalize_candidate_for_storage(candidate)
        for candidate in pool.values()
        if isinstance(candidate, dict)
    ]
    if len(candidates) <= 1:
        return dict(pool), 0

    kept: list[dict] = []
    bucket_indices: dict[tuple[str, object], list[int]] = {}
    removed = 0
    for candidate in candidates:
        bucket_key = (
            normalize_media_type(candidate.get("media_type")),
            candidate.get("year") or "",
        )
        match_index = None
        for index in bucket_indices.get(bucket_key, []):
            existing = kept[index]
            if candidates_are_same(candidate, existing, include_criteria=False):
                match_index = index
                break
        if match_index is None:
            kept.append(candidate)
            bucket_indices.setdefault(bucket_key, []).append(len(kept) - 1)
            continue

        removed += 1
        if candidate_sort_score(candidate) > candidate_sort_score(kept[match_index]):
            kept[match_index] = candidate

    deduplicated: dict = {}
    for candidate in kept:
        key = pool_entry_key(candidate)
        current_best = deduplicated.get(key)
        if current_best is None or candidate_sort_score(candidate) > candidate_sort_score(current_best):
            deduplicated[key] = candidate
    return deduplicated, removed


def _storage_id_value(candidate: dict, field_name: str) -> str | None:
    value = candidate.get(field_name)
    if value in (None, ""):
        return None
    text = str(value).strip()
    return text or None


def _cross_year_ids_conflict(left: dict, right: dict) -> bool:
    for field_name in ("imdb_id", "tmdb_id"):
        left_id = _storage_id_value(left, field_name)
        right_id = _storage_id_value(right, field_name)
        if left_id and right_id and left_id != right_id:
            return True
    return False


def _canonical_years_within_delta(left: dict, right: dict, *, max_year_delta: int = 1) -> bool:
    left_year = resolve_canonical_year(left)
    right_year = resolve_canonical_year(right)
    if left_year is None or right_year is None:
        return False
    return abs(left_year - right_year) <= max_year_delta


def _same_normalized_storage_title(left: dict, right: dict) -> bool:
    return normalize_key_part(candidate_title(left)) == normalize_key_part(candidate_title(right))


def can_merge_cross_year_candidates(left: dict, right: dict, *, max_year_delta: int = 1) -> bool:
    """True when same normalized title, years within delta, and ids do not conflict."""
    if normalize_media_type(left.get("media_type")) != normalize_media_type(right.get("media_type")):
        return False
    if not _same_normalized_storage_title(left, right):
        return False
    if not _canonical_years_within_delta(left, right, max_year_delta=max_year_delta):
        return False
    if _cross_year_ids_conflict(left, right):
        return False
    return True


def _candidate_field_has_value(value) -> bool:
    return value is not None and str(value).strip() != ""


def merge_pool_candidate_records(winner: dict, loser: dict) -> dict:
    """Merges two pool records, preferring winner fields and filling gaps from loser."""
    merged = dict(winner)
    for field_name, value in loser.items():
        if _candidate_field_has_value(merged.get(field_name)):
            continue
        if _candidate_field_has_value(value) is False:
            continue
        merged[field_name] = value
    return normalize_candidate_for_storage(merged)


def dedupe_pool_cross_year_titles(pool: dict, *, max_year_delta: int = 1) -> tuple[dict, int]:
    """Сливает кандидатов с одним названием и годами в пределах ±max_year_delta."""
    candidates = [
        normalize_candidate_for_storage(candidate)
        for candidate in pool.values()
        if isinstance(candidate, dict)
    ]
    if len(candidates) <= 1:
        return dict(pool), 0

    kept: list[dict] = []
    bucket_indices: dict[tuple[str, str], list[int]] = {}
    removed = 0
    for candidate in candidates:
        bucket_key = (
            normalize_media_type(candidate.get("media_type")),
            normalize_key_part(candidate_title(candidate)),
        )
        match_index = None
        for index in bucket_indices.get(bucket_key, []):
            existing = kept[index]
            if can_merge_cross_year_candidates(candidate, existing, max_year_delta=max_year_delta):
                match_index = index
                break
        if match_index is None:
            kept.append(candidate)
            bucket_indices.setdefault(bucket_key, []).append(len(kept) - 1)
            continue

        removed += 1
        existing = kept[match_index]
        if candidate_sort_score(candidate) > candidate_sort_score(existing):
            kept[match_index] = merge_pool_candidate_records(candidate, existing)
        else:
            kept[match_index] = merge_pool_candidate_records(existing, candidate)

    deduplicated: dict = {}
    for candidate in kept:
        key = pool_entry_key(candidate)
        current_best = deduplicated.get(key)
        if current_best is None or candidate_sort_score(candidate) > candidate_sort_score(current_best):
            deduplicated[key] = candidate
    return deduplicated, removed


def clean_common_pool_duplicates(
    *,
    merge_similar: bool = True,
    merge_cross_year: bool = True,
) -> dict:
    """Явно чистит общий pool от exact-, fuzzy- и cross-year-дублей (write-path)."""
    from candidates.pool.normalization import normalize_storage_pool
    from candidates.repositories.pool_repository import load_candidate_pool, save_candidate_pool

    raw_pool = load_candidate_pool()
    raw_total = len(raw_pool) if isinstance(raw_pool, dict) else 0

    exact_pool = normalize_storage_pool(raw_pool)
    exact_unique = len(exact_pool)
    exact_removed = max(0, raw_total - exact_unique)

    final_pool = exact_pool
    similar_removed = 0
    if merge_similar and exact_unique > 1:
        final_pool, similar_removed = dedupe_pool_by_similar_titles(exact_pool)

    cross_year_removed = 0
    if merge_cross_year and len(final_pool) > 1:
        final_pool, cross_year_removed = dedupe_pool_cross_year_titles(final_pool)

    final_unique = len(final_pool)
    changed = (
        raw_total != final_unique
        or similar_removed > 0
        or cross_year_removed > 0
        or set(raw_pool.keys()) != set(final_pool.keys())
    )
    if changed:
        save_candidate_pool(final_pool)

    return {
        "ok": True,
        "changed": changed,
        "raw_total": raw_total,
        "exact_unique": exact_unique,
        "unique_total": final_unique,
        "removed_exact": exact_removed,
        "removed_similar": similar_removed,
        "removed_cross_year": cross_year_removed,
        "removed_total": max(0, raw_total - final_unique),
    }

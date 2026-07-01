"""Dataset title overlap checks for saved candidate pool."""

from __future__ import annotations

from candidates.models.keys import normalize_key_part
from candidates.pool.dedupe import candidate_title
from candidates.pool.normalization import normalize_storage_pool


def build_dataset_entries_by_title_key() -> dict[str, list[dict]]:
    """Read-only index of watched dataset records grouped by normalized title."""
    from storage import data as storage_data

    dataset = storage_data.load_dataset()
    groups: dict[str, list[dict]] = {}
    for dataset_key, movie in dataset.items():
        if isinstance(movie, dict) is False:
            continue
        main_info = movie.get("main_info") or {}
        title = main_info.get("title") or dataset_key
        title_key = normalize_key_part(title)
        if title_key == "":
            continue
        groups.setdefault(title_key, []).append({
            "dataset_key": dataset_key,
            "title": title,
            "year": main_info.get("year"),
        })
    return groups


def build_dataset_title_keys() -> set[str]:
    """Read-only set of normalized dataset titles for strict pool gate."""
    return set(build_dataset_entries_by_title_key().keys())


def is_dataset_title_match(candidate: dict, dataset_title_keys: set[str] | None = None) -> bool:
    """True when candidate normalized title already exists in watched dataset."""
    if dataset_title_keys is None:
        dataset_title_keys = build_dataset_title_keys()
    title_key = normalize_key_part(candidate_title(candidate))
    return title_key != "" and title_key in dataset_title_keys


def count_pool_dataset_title_matches(pool: dict | None = None) -> dict:
    """Read-only count of pool entries whose title already exists in dataset."""
    from candidates import candidate_pool as pool_compat

    if pool is None:
        pool = normalize_storage_pool(pool_compat.load_candidate_pool())
    dataset_title_keys = build_dataset_title_keys()
    matches = []
    for key, candidate in pool.items():
        if isinstance(candidate, dict) is False:
            continue
        if is_dataset_title_match(candidate, dataset_title_keys):
            matches.append({
                "pool_key": key,
                "title": candidate_title(candidate),
                "year": candidate.get("year"),
            })
    return {
        "match_count": len(matches),
        "matches": matches,
        "is_empty": len(matches) == 0,
    }


def purge_dataset_title_matches_from_pool() -> dict:
    """Removes pool entries whose normalized title exists in watched dataset."""
    from candidates import candidate_pool as pool_compat

    raw_pool = pool_compat.load_candidate_pool()
    raw_total = len(raw_pool) if isinstance(raw_pool, dict) else 0
    storage_pool = normalize_storage_pool(raw_pool)
    dataset_title_keys = build_dataset_title_keys()

    filtered = {}
    removed = 0
    for key, candidate in storage_pool.items():
        if isinstance(candidate, dict) is False:
            continue
        if is_dataset_title_match(candidate, dataset_title_keys):
            removed += 1
            continue
        filtered[key] = candidate

    changed = removed > 0 or set(raw_pool.keys()) != set(filtered.keys())
    if changed:
        pool_compat.save_candidate_pool(filtered)

    return {
        "ok": True,
        "changed": changed,
        "raw_total": raw_total,
        "unique_total": len(filtered),
        "removed_dataset_title_matches": removed,
    }

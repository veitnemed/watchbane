"""Dataset title overlap checks for saved candidate pool."""

from __future__ import annotations

from candidates.models.keys import normalize_key_part
from candidates.pool.dedupe import candidate_title
from candidates.pool.normalization import normalize_storage_pool
from dataset.models.media_type import normalize_media_type


TITLE_ALIAS_SELECTORS = (
    ("main_info", "title"),
    ("localized", "ru", "title"),
    ("localized", "en", "title"),
    ("meta", "localized", "ru", "title"),
    ("meta", "localized", "en", "title"),
    ("tmdb_data", "localized", "ru", "title"),
    ("tmdb_data", "localized", "en", "title"),
    ("title",),
    ("name",),
    ("original_title",),
    ("original_name",),
    ("alternative_title",),
    ("alternativeName",),
    ("enName",),
    ("title_en",),
    ("name_en",),
)


class DatasetTitleKeys(set[str]):
    """Title-key set carrying media-aware watched entries for modern callers."""

    def __init__(self, entries_by_key: dict[str, list[dict]]) -> None:
        super().__init__(entries_by_key)
        self.entries_by_key = entries_by_key


def _clean_text(value) -> str | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    return text if text else None


def _path_value(record: dict, selector: tuple[str, ...]):
    current = record
    for part in selector:
        if isinstance(current, dict) is False:
            return None
        current = current.get(part)
    return current


def _unique_texts(values) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _clean_text(value)
        if text is None:
            continue
        key = normalize_key_part(text)
        if key == "" or key in seen:
            continue
        seen.add(key)
        result.append(text)
    return result


def dataset_title_aliases(dataset_key: str, movie: dict) -> list[str]:
    """Return watched title aliases used to keep saved pool free of repeats."""
    source = movie if isinstance(movie, dict) else {}
    values = [dataset_key]
    values.extend(_path_value(source, selector) for selector in TITLE_ALIAS_SELECTORS)
    return _unique_texts(values)


def candidate_title_aliases(candidate: dict) -> list[str]:
    """Return candidate title aliases for dataset-overlap checks."""
    source = candidate if isinstance(candidate, dict) else {}
    values = [candidate_title(source)]
    values.extend(_path_value(source, selector) for selector in TITLE_ALIAS_SELECTORS)
    return _unique_texts(values)


def candidate_title_keys(candidate: dict) -> set[str]:
    """Return normalized title keys for all candidate aliases."""
    return {
        key
        for key in (normalize_key_part(title) for title in candidate_title_aliases(candidate))
        if key
    }


def build_dataset_entries_by_title_key() -> dict[str, list[dict]]:
    """Read-only index of watched dataset records grouped by normalized title."""
    from storage import data as storage_data

    dataset = storage_data.load_dataset()
    groups: dict[str, list[dict]] = {}
    for dataset_key, movie in dataset.items():
        if isinstance(movie, dict) is False:
            continue
        main_info = movie.get("main_info") or {}
        for title in dataset_title_aliases(dataset_key, movie):
            title_key = normalize_key_part(title)
            if title_key == "":
                continue
            groups.setdefault(title_key, []).append({
                "dataset_key": dataset_key,
                "title": title,
                "year": main_info.get("year"),
                "media_type": normalize_media_type(
                    main_info.get("media_type") or movie.get("media_type")
                ),
                "has_media_type": bool(
                    main_info.get("media_type") not in (None, "")
                    or movie.get("media_type") not in (None, "")
                ),
            })
    return groups


def build_dataset_title_keys() -> set[str]:
    """Read-only title set with media identity details for strict pool gates."""
    return DatasetTitleKeys(build_dataset_entries_by_title_key())


def is_dataset_title_match(candidate: dict, dataset_title_keys: set[str] | None = None) -> bool:
    """True when candidate normalized title already exists in watched dataset."""
    if dataset_title_keys is None:
        dataset_title_keys = build_dataset_title_keys()
    matching_keys = candidate_title_keys(candidate).intersection(dataset_title_keys)
    if not matching_keys:
        return False

    entries_by_key = getattr(dataset_title_keys, "entries_by_key", None)
    candidate_media_type = candidate.get("media_type")
    if not isinstance(entries_by_key, dict) or candidate_media_type in (None, ""):
        return True

    normalized_media_type = normalize_media_type(candidate_media_type)
    for title_key in matching_keys:
        for entry in entries_by_key.get(title_key) or []:
            if not entry.get("has_media_type"):
                return True
            if entry.get("media_type") == normalized_media_type:
                return True
    return False


def count_pool_dataset_title_matches(pool: dict | None = None) -> dict:
    """Read-only count of pool entries whose title already exists in dataset."""
    from candidates.repositories.pool_repository import load_candidate_pool

    if pool is None:
        pool = normalize_storage_pool(load_candidate_pool())
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
    from candidates.repositories.pool_repository import load_candidate_pool, save_candidate_pool

    raw_pool = load_candidate_pool()
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
        save_candidate_pool(filtered)

    return {
        "ok": True,
        "changed": changed,
        "raw_total": raw_total,
        "unique_total": len(filtered),
        "removed_dataset_title_matches": removed,
    }

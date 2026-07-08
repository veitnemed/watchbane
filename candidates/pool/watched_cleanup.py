"""Remove watched candidates from saved pool on write-path."""

from __future__ import annotations

from candidates.models.keys import title_identity_key
from candidates.pool.dataset_overlap import (
    build_dataset_title_keys,
    candidate_title_aliases,
    dataset_title_aliases,
    is_dataset_title_match,
)
from candidates.pool.dedupe import (
    candidates_are_same,
    compact_title_key,
    normalized_title_key,
    titles_are_similar,
)
from candidates.pool.normalization import normalize_storage_pool
from dataset.models.media_type import normalize_media_type


_EXTERNAL_ID_FIELDS = {
    "tmdb_id": "tmdb",
    "tmdbId": "tmdb",
    "imdb_id": "imdb",
    "imdbId": "imdb",
}


def _clean_text(value) -> str | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    return text if text else None


def _year_from_value(value) -> str:
    text = _clean_text(value)
    if text is None:
        return ""
    if len(text) >= 4 and text[:4].isdigit():
        return text[:4]
    return text


def _movie_year(movie: dict) -> str:
    source = movie if isinstance(movie, dict) else {}
    main_info = source.get("main_info") if isinstance(source.get("main_info"), dict) else {}
    for value in (
        main_info.get("year"),
        source.get("year"),
        source.get("first_air_date"),
        source.get("release_date"),
        source.get("start_year"),
    ):
        year = _year_from_value(value)
        if year:
            return year
    return ""


def _candidate_year(candidate: dict) -> str:
    source = candidate if isinstance(candidate, dict) else {}
    for value in (source.get("year"), source.get("first_air_date"), source.get("release_date"), source.get("start_year")):
        year = _year_from_value(value)
        if year:
            return year
    return ""


def _movie_media_type(movie: dict) -> str:
    source = movie if isinstance(movie, dict) else {}
    main_info = source.get("main_info") if isinstance(source.get("main_info"), dict) else {}
    return normalize_media_type(main_info.get("media_type") or source.get("media_type"))


def _candidate_media_type(candidate: dict) -> str | None:
    source = candidate if isinstance(candidate, dict) else {}
    if source.get("media_type") in (None, ""):
        return None
    return normalize_media_type(source.get("media_type"))


def _external_id_signatures(value, *, media_type: str | None = None, include_unscoped: bool = True) -> set[str]:
    signatures: set[str] = set()
    normalized_media_type = normalize_media_type(media_type) if media_type is not None else None

    def visit(current) -> None:
        if isinstance(current, dict):
            for key, nested_value in current.items():
                prefix = _EXTERNAL_ID_FIELDS.get(str(key))
                if prefix is not None:
                    text = _clean_text(nested_value)
                    if text is not None:
                        lowered = text.casefold()
                        if normalized_media_type is not None:
                            signatures.add(f"{prefix}:{normalized_media_type}:{lowered}")
                        if include_unscoped:
                            signatures.add(f"{prefix}:{lowered}")
                if isinstance(nested_value, (dict, list, tuple)):
                    visit(nested_value)
            return
        if isinstance(current, (list, tuple)):
            for item in current:
                visit(item)

    visit(value)
    return signatures


def _candidate_external_signatures(candidate: dict) -> set[str]:
    media_type = _candidate_media_type(candidate)
    return _external_id_signatures(candidate, media_type=media_type, include_unscoped=media_type is None)


def build_watched_signatures() -> set:
    """Собирает сигнатуры уже просмотренных объектов из основного датасета."""
    from storage import data as storage_data

    dataset = storage_data.load_dataset()
    signatures = set()
    for dataset_key, movie in dataset.items():
        if isinstance(movie, dict) is False:
            continue
        media_type = _movie_media_type(movie)
        year = _movie_year(movie)
        for title in dataset_title_aliases(dataset_key, movie):
            signature = title_identity_key({
                "title": title,
                "year": year,
            })
            if signature != "|":
                signatures.add(signature)
        signatures.update(_external_id_signatures(movie, media_type=media_type, include_unscoped=True))
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

    candidate_external = _candidate_external_signatures(candidate)
    if candidate_external and candidate_external.intersection(watched_signatures):
        return True

    title_aliases = candidate_title_aliases(candidate)
    year = _candidate_year(candidate)
    for title in title_aliases:
        exact_signature = title_identity_key({"title": title, "year": year})
        if exact_signature in watched_signatures:
            return True

    candidate_compacts = [
        compact_title_key(normalized_title_key(title))
        for title in title_aliases
        if normalized_title_key(title)
    ]
    for watched_signature in watched_signatures:
        if "|" not in watched_signature:
            continue
        watched_title, _, watched_year = watched_signature.partition("|")
        if str(watched_year) != str(year):
            continue
        for candidate_compact in candidate_compacts:
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
    from candidates.repositories.pool_repository import load_candidate_pool, save_candidate_pool

    pool = normalize_storage_pool(load_candidate_pool())
    filtered_pool = {}
    removed = 0

    for key, candidate in pool.items():
        if candidates_are_same(candidate, target_candidate, include_criteria=False):
            removed += 1
            continue
        filtered_pool[key] = candidate

    if removed > 0:
        save_candidate_pool(filtered_pool)
    return removed

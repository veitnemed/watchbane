"""Candidate pool -> dataset transfer payloads."""

from config import constant
from config import genre_tags
from config import scheme
from dataset.genres.mapping import candidate_genre_keys_to_dataset_genres
from dataset.meta.payload import build_candidate_meta_payload
from dataset.resolve.countries import extract_country_value
from dataset.resolve.defaults import build_api_defaults
from dataset.resolve.genres import (
    build_genre_defaults,
    extract_candidate_fallback_genres,
)


def _normalize_candidate_genre_keys(candidate: dict) -> list[str]:
    genre_keys = candidate.get("genre_keys")
    if isinstance(genre_keys, list):
        return list(genre_keys)
    return []


def _candidate_has_raw_genre_signals(candidate: dict) -> bool:
    for field_name in ("genres", "imdb_genres", "genres_tmdb"):
        values = candidate.get(field_name)
        if isinstance(values, list) is False:
            continue
        for item in values:
            if isinstance(item, dict) and str(item.get("name") or "").strip() != "":
                return True
            if isinstance(item, str) and item.strip() != "":
                return True
    return False


def _extract_raw_genre_strings(candidate: dict) -> list[str]:
    raw_genres = []
    for field_name in ("genres", "imdb_genres", "genres_tmdb"):
        values = candidate.get(field_name) or []
        if isinstance(values, list) is False:
            continue
        for item in values:
            if isinstance(item, dict) and item.get("name"):
                text = str(item["name"]).strip()
            elif isinstance(item, str):
                text = item.strip()
            else:
                continue
            if text != "" and text not in raw_genres:
                raw_genres.append(text)
    return raw_genres


def build_candidate_transfer_genre_defaults(candidate: dict) -> dict:
    """Собирает genre defaults для переноса кандидата из pool genre_keys или raw genres."""
    genre_keys = candidate.get("genre_keys")
    if isinstance(genre_keys, list) and len(genre_keys) > 0:
        genre_result = candidate_genre_keys_to_dataset_genres(genre_keys)
        if genre_result["status"] != "missing":
            return dict(genre_result["dataset_genre"])
    return build_genre_defaults(extract_candidate_fallback_genres(candidate))


def build_candidate_genre_transfer_preview(candidate: dict) -> dict:
    """Собирает read-only диагностику жанров для preview переноса candidate -> dataset."""
    genre_keys = _normalize_candidate_genre_keys(candidate)
    mapper_status = "missing"
    mapped_genre_keys: list[str] = []
    unmapped_genre_keys: list[str] = []
    used_fallback = False
    dataset_genre = {feature: 0 for feature in constant.GENRE}

    if len(genre_keys) > 0:
        genre_result = candidate_genre_keys_to_dataset_genres(genre_keys)
        mapper_status = genre_result["status"]
        mapped_genre_keys = list(genre_result["mapped_genre_keys"])
        unmapped_genre_keys = list(genre_result["unmapped_genre_keys"])
        if mapper_status != "missing":
            dataset_genre = dict(genre_result["dataset_genre"])

    if mapper_status == "missing":
        used_fallback = True
        dataset_genre = build_genre_defaults(extract_candidate_fallback_genres(candidate))

    active_has_features = [
        feature_name
        for feature_name in constant.GENRE
        if dataset_genre.get(feature_name) == 1
    ]
    genre_labels = genre_tags.get_genre_labels()
    active_has_labels = [
        genre_labels.get(feature_name, feature_name)
        for feature_name in active_has_features
    ]
    has_raw_genre_signals = _candidate_has_raw_genre_signals(candidate)

    return {
        "genre_keys": genre_keys,
        "mapper_status": mapper_status,
        "mapped_genre_keys": mapped_genre_keys,
        "unmapped_genre_keys": unmapped_genre_keys,
        "dataset_genre": dataset_genre,
        "active_has_features": active_has_features,
        "active_has_labels": active_has_labels,
        "used_fallback": used_fallback,
        "raw_genres": _extract_raw_genre_strings(candidate),
        "has_raw_genre_signals": has_raw_genre_signals,
        "warn_all_genres_zero": has_raw_genre_signals and len(active_has_features) == 0,
    }


def build_candidate_transfer_payload(candidate: dict) -> dict:
    """Собирает defaults и meta для переноса кандидата из общего пула в dataset."""
    defaults = build_api_defaults(candidate)
    defaults[scheme.MAIN_INFO]["country"] = extract_country_value(candidate)
    defaults[scheme.GENRE] = build_candidate_transfer_genre_defaults(candidate)
    meta_payload = build_candidate_meta_payload(candidate)
    return {
        "defaults": defaults,
        "meta_payload": meta_payload,
    }

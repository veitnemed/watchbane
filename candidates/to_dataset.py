"""Maps candidate-pool canonical fields to dataset/model payload shapes."""

from __future__ import annotations

from typing import Any

from config import constant
from candidates import genre_schema


GENRE_KEY_TO_DATASET_FEATURE: dict[str, str] = {
    "drama": "has_drama",
    "crime": "has_crime",
    "thriller": "has_thriller",
    "comedy": "has_comedy",
    "mystery": "has_detective",
    "romance": "has_romance",
    "action_adventure": "has_action",
    "sci_fi_fantasy": "has_fantasy",
}


def _normalize_genre_keys(genre_keys: Any) -> list[str]:
    if not isinstance(genre_keys, list):
        return []

    normalized: list[str] = []
    seen: set[str] = set()
    for key in genre_keys:
        text = str(key).strip().casefold()
        if text == "" or text in seen:
            continue
        seen.add(text)
        normalized.append(text)
    return normalized


def candidate_genre_keys_to_dataset_genres(genre_keys: Any) -> dict[str, Any]:
    """Translates canonical pool genre keys into the current dataset genre vector."""
    dataset_genre = {feature: 0 for feature in constant.GENRE}
    mapped_genre_keys: list[str] = []
    unmapped_genre_keys: list[str] = []

    for key in _normalize_genre_keys(genre_keys):
        feature_name = GENRE_KEY_TO_DATASET_FEATURE.get(key)
        if feature_name is None or feature_name not in dataset_genre:
            unmapped_genre_keys.append(key)
            continue

        dataset_genre[feature_name] = 1
        mapped_genre_keys.append(key)

    if len(mapped_genre_keys) == 0:
        status = "missing"
    elif len(unmapped_genre_keys) == 0:
        status = "ok"
    else:
        status = "partial"

    return {
        "dataset_genre": dataset_genre,
        "mapped_genre_keys": mapped_genre_keys,
        "unmapped_genre_keys": unmapped_genre_keys,
        "status": status,
    }


def _normalize_raw_genre_list(raw_genres: Any) -> list[str]:
    if raw_genres is None:
        return []
    if isinstance(raw_genres, list) is False:
        raw_genres = [raw_genres]

    normalized: list[str] = []
    seen: set[str] = set()
    for item in raw_genres:
        if isinstance(item, dict) and item.get("name"):
            text = str(item["name"]).strip()
        elif isinstance(item, str):
            text = item.strip()
        else:
            text = str(item or "").strip()
        if text == "" or text in seen:
            continue
        seen.add(text)
        normalized.append(text)
    return normalized


def raw_genres_to_dataset_genres(raw_genres: Any) -> dict[str, Any]:
    """Translates EN/RU raw genre labels into the current dataset genre vector."""
    raw_list = _normalize_raw_genre_list(raw_genres)
    genre_keys: list[str] = []
    mapped_raw_genres: list[str] = []
    unmapped_raw_genres: list[str] = []
    seen_keys: set[str] = set()

    for raw_genre in raw_list:
        genre_key = genre_schema.normalize_genre_to_key(raw_genre)
        if genre_key is None:
            unmapped_raw_genres.append(raw_genre)
            continue

        mapped_raw_genres.append(raw_genre)
        if genre_key in seen_keys:
            continue
        seen_keys.add(genre_key)
        genre_keys.append(genre_key)

    key_result = candidate_genre_keys_to_dataset_genres(genre_keys)
    if len(key_result["mapped_genre_keys"]) == 0:
        status = "missing"
    elif len(unmapped_raw_genres) == 0 and len(key_result["unmapped_genre_keys"]) == 0:
        status = "ok"
    else:
        status = "partial"

    return {
        "dataset_genre": key_result["dataset_genre"],
        "genre_keys": genre_keys,
        "mapped_raw_genres": mapped_raw_genres,
        "unmapped_raw_genres": unmapped_raw_genres,
        "mapped_genre_keys": key_result["mapped_genre_keys"],
        "unmapped_genre_keys": key_result["unmapped_genre_keys"],
        "status": status,
    }

"""Genre extraction and defaults for title resolve."""

from dataset.genres.mapping import (
    normalize_genre_label_to_key,
    raw_genres_to_dataset_genres,
)
from dataset.resolve.helpers import unique_preserve_order


def extract_api_genres(series: dict) -> list:
    """Извлекает список жанров из ответа API или плоского кандидата."""
    genres = []
    for item in series.get("genres", []) or []:
        if isinstance(item, dict) and item.get("name"):
            genres.append(str(item["name"]).strip())
        elif isinstance(item, str):
            genres.append(item.strip())
    return genres


def extract_candidate_fallback_genres(candidate: dict) -> list:
    """Собирает raw-жанры для fallback переноса из genres и genres_tmdb."""
    merged: list[str] = []
    for field_name in ("genres", "genres_tmdb"):
        if field_name == "genres":
            merged.extend(extract_api_genres(candidate))
            continue
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
            if text != "":
                merged.append(text)
    return unique_preserve_order(merged)


def split_known_genres(genres: list) -> tuple[list, list]:
    """Разделяет жанры на известные dataset и неизвестные подсказки."""
    mapping = raw_genres_to_dataset_genres(genres)
    unmapped_keys = set(mapping["unmapped_genre_keys"])
    known: list[str] = []
    unknown = list(mapping["unmapped_raw_genres"])

    for raw_genre in unique_preserve_order(mapping["mapped_raw_genres"]):
        genre_key = normalize_genre_label_to_key(raw_genre)
        if genre_key is None or genre_key in unmapped_keys:
            if raw_genre not in unknown:
                unknown.append(raw_genre)
            continue
        known.append(raw_genre)

    return known, unknown


def build_genre_defaults(genres: list) -> dict:
    """Собирает значения genre по списку жанров."""
    return dict(raw_genres_to_dataset_genres(genres)["dataset_genre"])


def extract_tmdb_genres(series: dict | None) -> list:
    """Достаёт список жанров из нормализованного TMDb-объекта."""
    if not isinstance(series, dict):
        return []
    return unique_preserve_order(series.get("genres_tmdb", []) or [])

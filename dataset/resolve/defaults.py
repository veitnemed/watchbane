"""Default values built from SQL, KP API, and TMDb candidates."""

from config import constant
from config import scheme
from dataset.resolve.countries import extract_country_value
from dataset.resolve.genres import build_genre_defaults, extract_api_genres
from dataset.resolve.helpers import unique_preserve_order
from apis import kp_api as api


def extract_api_title(series: dict) -> str:
    """Достаёт лучшее доступное название из сырого ответа API."""
    for key in ("title", "name", "alternativeName", "enName"):
        value = series.get(key)
        if str(value or "").strip() != "":
            return str(value).strip()
    return ""


def extract_api_raw_scores(series: dict) -> dict:
    """Собирает рейтинги и голоса из ответа API в плоский словарь."""
    tmdb_raw_scores = {
        key: series.get(key)
        for key in ("tmdb_score", "tmdb_votes", "tmdb_popularity")
        if series.get(key) not in (None, "")
    }
    if tmdb_raw_scores:
        return tmdb_raw_scores

    return {
        "kp_score": series.get("kp_score", api.safe_nested(series, "rating", "kp")),
        "kp_votes": series.get("kp_votes", api.safe_nested(series, "votes", "kp")),
        "imdb_score": series.get("imdb_score", api.safe_nested(series, "rating", "imdb")),
        "imdb_votes": series.get("imdb_votes", api.safe_nested(series, "votes", "imdb")),
    }


def has_api_imdb_values(series: dict | None) -> bool:
    """Проверяет, дал ли API хотя бы часть IMDb score/votes."""
    if not isinstance(series, dict):
        return False
    raw_scores = extract_api_raw_scores(series)
    return raw_scores.get("imdb_score") not in (None, "") or raw_scores.get("imdb_votes") not in (None, "")


def extract_api_description(series: dict) -> str:
    """Возвращает лучшее доступное описание из KP API."""
    return str(series.get("description") or series.get("shortDescription") or "").strip()


def build_empty_add_defaults(input_title: str) -> dict:
    """Собирает минимальные defaults для ручного добавления без внешних данных."""
    return {
        scheme.MAIN_INFO: {
            "title": input_title,
            "user_score": None,
            "year": None,
            "country": "",
        },
        scheme.RAW_SCORES: {},
        scheme.TAGS_VIBE: {feature: 0 for feature in constant.TAGS_VIBE},
        scheme.GENRE: {feature: 0 for feature in constant.GENRE},
    }


def build_sql_defaults(series: dict) -> dict:
    """Собирает значения по умолчанию из локального SQL-результата."""
    genres = unique_preserve_order(series.get("genres", []) or [])
    genre_defaults = build_genre_defaults(genres)

    return {
        scheme.MAIN_INFO: {
            "title": series.get("title") or series.get("original_title"),
            "user_score": None,
            "year": series.get("year"),
            "country": extract_country_value(series),
        },
        scheme.RAW_SCORES: {
            "kp_score": None,
            "kp_votes": None,
            "imdb_score": series.get("imdb_rating"),
            "imdb_votes": series.get("imdb_votes"),
        },
        scheme.TAGS_VIBE: {},
        scheme.GENRE: genre_defaults,
    }


def merge_defaults(base: dict, extra: dict) -> dict:
    """Объединяет defaults из нескольких источников с приоритетом extra."""
    merged = {
        scheme.MAIN_INFO: {},
        scheme.RAW_SCORES: {},
        scheme.TAGS_VIBE: {},
        scheme.GENRE: {},
    }

    for section_name in merged.keys():
        base_section = base.get(section_name, {}) if isinstance(base, dict) else {}
        extra_section = extra.get(section_name, {}) if isinstance(extra, dict) else {}

        if section_name == scheme.GENRE:
            keys = set(base_section.keys()) | set(extra_section.keys())
            for key in keys:
                merged[section_name][key] = max(
                    int(base_section.get(key, 0) or 0),
                    int(extra_section.get(key, 0) or 0),
                )
            continue

        merged[section_name].update(base_section)
        for key, value in extra_section.items():
            if value is not None and value != "":
                merged[section_name][key] = value
            elif key not in merged[section_name]:
                merged[section_name][key] = value

    return merged


def build_api_defaults(series: dict, genres: list | None = None) -> dict:
    """Собирает значения API для подстановки в ручную форму."""
    if genres is None:
        genres = extract_api_genres(series)

    genre_defaults = build_genre_defaults(genres)
    raw_scores = extract_api_raw_scores(series)

    return {
        scheme.MAIN_INFO: {
            "title": extract_api_title(series),
            "user_score": None,
            "year": series.get("year"),
            "country": extract_country_value(series),
        },
        scheme.RAW_SCORES: raw_scores,
        scheme.TAGS_VIBE: {},
        scheme.GENRE: genre_defaults,
    }

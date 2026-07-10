"""Приводит данные фильма к актуальной схеме."""

from common import valid
from dataset.models.media_type import normalize_media_type

LEGACY_PAYLOAD_SECTIONS = ("tags_vibe", "genre")


def normalize_movie_tags(movie: dict) -> dict:
    """Strip legacy watched payload sections during persistence."""
    for section_name in LEGACY_PAYLOAD_SECTIONS:
        movie.pop(section_name, None)
    return movie


def normalize_csv_row(row: dict) -> dict:
    """Приводит строку таблицы к актуальным полям."""
    normalized = dict(row)
    normalized.setdefault("country", "")
    normalized["media_type"] = normalize_media_type(normalized.get("media_type"))
    return normalized


def is_supported_csv_fields(fieldnames: list) -> bool:
    """Проверяет заголовки табличного файла."""
    from config import constant

    normalized = normalize_csv_row({field: "" for field in fieldnames})
    return all(field in normalized for field in constant.CSV_FIELDS)


def normalize_main_info(main_info: dict) -> dict:
    """Приводит основные данные фильма к нужным типам."""
    from config import constant

    normalized = {}
    for feature in constant.MAIN_INFO:
        if feature == "title":
            normalized[feature] = str(main_info[feature]).strip()
        elif feature == "year":
            normalized[feature] = int(main_info[feature])
        elif feature == "country":
            normalized[feature] = str(main_info.get(feature, "") or "").strip()
        else:
            normalized[feature] = valid.parse_float(main_info[feature])
    normalized["media_type"] = normalize_media_type(main_info.get("media_type"))
    return normalized


def normalize_raw_scores(raw: dict) -> dict:
    """Приводит сырые оценки и голоса к нужным типам."""
    from config import constant

    if isinstance(raw, dict) is False:
        return {}
    normalized = {}
    supported_fields = set(constant.RAW_SCORES)
    for feature, value in raw.items():
        if feature not in supported_fields or value in (None, ""):
            continue
        if feature.endswith("_votes"):
            normalized[feature] = valid.parse_int(value)
        else:
            normalized[feature] = valid.parse_float(value)
    return normalized

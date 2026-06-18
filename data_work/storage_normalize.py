"""Приводит данные фильма, тегов и строк таблицы к актуальной схеме."""

from config import constant
from config import genre_tags
from config import scheme
from common import valid


LEGACY_TAG_FIELDS = {
    "has_psyhology": "has_psychology",
    "has_relationship_focus": "has_relationships",
    "has_romantic_tension": "has_romantic_pursuit",
    "has_love_tension": "has_romantic_pursuit",
}

REMOVED_TAG_FIELDS = {"has_mystic"}


def normalize_tags_vibe(tags_vibe: dict) -> dict:
    """Приводит теги фильма к актуальной схеме."""
    normalized = {feature: 0 for feature in constant.TAGS_VIBE}
    for feature, value in tags_vibe.items():
        if feature in normalized:
            normalized[feature] = value
    for old_feature, active_feature in LEGACY_TAG_FIELDS.items():
        if old_feature in tags_vibe and active_feature in normalized and active_feature not in tags_vibe:
            normalized[active_feature] = tags_vibe[old_feature]
    return normalized


def normalize_genre_tags(movie_genre_tags: dict) -> dict:
    """Приводит жанровую разметку фильма к актуальной схеме."""
    normalized = {feature: 0 for feature in constant.GENRE}
    for feature, value in movie_genre_tags.items():
        active_feature = genre_tags.map_feature_name(feature)
        if active_feature in normalized:
            normalized[active_feature] = value
    return normalized


def normalize_movie_tags(movie: dict) -> dict:
    """Нормализует теги внутри записи фильма."""
    if constant.TAGS_VIBE_SECTION in movie:
        movie[constant.TAGS_VIBE_SECTION] = normalize_tags_vibe(movie[constant.TAGS_VIBE_SECTION])
    movie[constant.GENRE_SECTION] = normalize_genre_tags(movie.get(constant.GENRE_SECTION, {}))
    return movie


def normalize_csv_row(row: dict) -> dict:
    """Приводит строку таблицы к актуальным полям."""
    normalized = {feature: value for feature, value in row.items() if feature not in REMOVED_TAG_FIELDS}
    for old_feature, active_feature in LEGACY_TAG_FIELDS.items():
        if active_feature in constant.TAGS_VIBE and active_feature not in normalized and old_feature in normalized:
            normalized[active_feature] = normalized[old_feature]
        normalized.pop(old_feature, None)
    for feature in constant.TAGS_VIBE:
        normalized.setdefault(feature, "0")
    for feature in constant.GENRE:
        normalized.setdefault(feature, "0")
    return normalized


def is_supported_csv_fields(fieldnames: list) -> bool:
    """Проверяет заголовки табличного файла."""
    normalized = normalize_csv_row({field: "" for field in fieldnames})
    return all(field in normalized for field in constant.CSV_FIELDS)


def normalize_main_info(main_info: dict) -> dict:
    """Приводит основные данные фильма к нужным типам."""
    normalized = {}
    for feature in constant.MAIN_INFO:
        if feature == "title":
            normalized[feature] = str(main_info[feature]).strip()
        elif feature == "year":
            normalized[feature] = int(main_info[feature])
        else:
            normalized[feature] = valid.parse_float(main_info[feature])
    return normalized


def normalize_raw_scores(raw: dict) -> dict:
    """Приводит сырые оценки и голоса к нужным типам."""
    normalized = {}
    for feature in constant.RAW_SCORES:
        if feature.endswith("_votes"):
            normalized[feature] = int(raw[feature])
        else:
            normalized[feature] = valid.parse_float(raw[feature])
    return normalized


def is_valid_tags_vibe(tags_vibe: dict) -> bool:
    """Проверяет секцию тегов фильма."""
    tags_schema = scheme.get_schema(scheme.TAGS_VIBE)
    if set(tags_vibe.keys()) != set(tags_schema.keys()):
        return False

    for feature, value in tags_vibe.items():
        max_value = tags_schema[feature].get("max_value", 1)
        if valid.is_tags_score(value, max_value) is False:
            return False
    return True


def is_valid_genre_tags(genre_tags: dict) -> bool:
    """Проверяет секцию жанровой разметки фильма."""
    genre_schema = scheme.get_schema(scheme.GENRE)
    if set(genre_tags.keys()) != set(genre_schema.keys()):
        return False

    for feature, value in genre_tags.items():
        max_value = genre_schema[feature].get("max_value", 1)
        if valid.is_tags_score(value, max_value) is False:
            return False
    return True

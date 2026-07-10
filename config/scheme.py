"""Описывает секции данных фильма и правила полей."""

import copy

MAIN_INFO = "main_info"
RAW_SCORES = "raw_scores"

SHEME_VALIDATORS = {
    MAIN_INFO: {
        "title": {
            "tag": ["title"],
            "type": str
        },
        "user_score": {
            "tag": ["score"],
            "type": float
        },
        "year": {
            "tag": ["year"],
            "type": int
        },
        "country": {
            "tag": ["country"],
            "type": str
        }
    },
    RAW_SCORES: {
        "tmdb_score": {
            "tag": ["score"],
            "type": float,
            "formated": None
        },
        "tmdb_votes": {
            "tag": ["votes"],
            "type": int,
            "formated": None
        },
        "tmdb_popularity": {
            "tag": [],
            "type": float,
            "formated": None
        }
    },
}

SHEME_ADD = copy.deepcopy(SHEME_VALIDATORS)
SHEME_ADD[MAIN_INFO]["title"]["tag"].append("origin_title")


def get_fields(selection_name: str) -> list:
    """Возвращает поля секции схемы."""
    sheme_copy = get_schema(selection_name)
    return list(sheme_copy.keys())


def get_schema(selection_name: str) -> dict:
    """Возвращает схему секции."""
    sheme_copy = copy.deepcopy(SHEME_VALIDATORS)
    return sheme_copy[selection_name]


def get_computed_fields() -> list:
    """Возвращает вычисляемые поля raw-секции."""
    computed_fields = []
    for feature, settings in SHEME_VALIDATORS[RAW_SCORES].items():
        if settings["formated"] is None:
            computed_fields.append(feature)
        else:
            computed_fields.append(settings["formated"])
    return computed_fields

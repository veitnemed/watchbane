"""Описывает секции данных фильма и правила полей."""

import copy
from config import genre_tags
from config import tags_work


MAIN_INFO = "main_info"
RAW_SCORES = "raw_scores"
GENRE = "genre"
TAGS_VIBE = "tags_vibe"

TAG_FIELDS = tags_work.get_tag_fields()

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
        }
    },
    RAW_SCORES: {
        "kp_score": {
            "tag": ["score"],
            "type": float,
            "formated": None
        },
        "kp_votes": {
            "tag": ["votes"],
            "type": int,
            "formated": "kp_popularity"
        },
        "imdb_score": {
            "tag": ["score"],
            "type": float,
            "formated": None
        },
        "imdb_votes": {
            "tag": ["votes"],
            "type": int,
            "formated": "imdb_popularity"
        }
    },
    GENRE: {},
    TAGS_VIBE: {
        feature: {
            "tag": ["tags_score"],
            "type": int,
            "max_value": 1
        } for feature in TAG_FIELDS
    }
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
    if selection_name == GENRE:
        return {
            feature: {
                "tag": ["tags_score"],
                "type": int,
                "max_value": 1
            } for feature in genre_tags.get_genre_fields()
        }
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

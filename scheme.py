import copy


MAIN_INFO = "main_info"
RAW_SCORES = "raw_scores"
TAGS_VIBE = "tags_vibe"


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
    TAGS_VIBE: {
        "has_crime": {
            "tag": ["tags_score"],
            "type": int,
            "max_value": 1
        },
        "has_psyhology": {
            "tag": ["tags_score"],
            "type": int,
            "max_value": 1
        },
        "has_comedy": {
            "tag": ["tags_score"],
            "type": int,
            "max_value": 1
        },
        "has_mystic": {
            "tag": ["tags_score"],
            "type": int,
            "max_value": 1
        },
        "has_romantic_tension": {
            "tag": ["tags_score"],
            "type": int,
            "max_value": 1
        }
    }
}

SHEME_ADD = copy.deepcopy(SHEME_VALIDATORS)
SHEME_ADD[MAIN_INFO]["title"]["tag"].append("origin_title")


def get_fields(selection_name: str) -> list:
    sheme_copy = copy.deepcopy(SHEME_VALIDATORS)
    return list(sheme_copy[selection_name].keys())


def get_schema(selection_name: str) -> dict:
    sheme_copy = copy.deepcopy(SHEME_VALIDATORS)
    return sheme_copy[selection_name]


def get_computed_fields() -> list:
    computed_fields = []
    for feature, settings in SHEME_VALIDATORS[RAW_SCORES].items():
        if settings["formated"] is None:
            computed_fields.append(feature)
        else:
            computed_fields.append(settings["formated"])
    return computed_fields

import math

import constant
import scheme


def clip_0_10(value: float) -> float:
    return max(0, min(10, value))


def popularity_by_votes(votes: int, year: int, min_votes: int, max_votes: int) -> float:
    age = max(1, constant.NOW_YEAR - year)
    adjusted_votes = votes / (age ** 0.5)

    score = (
        math.log1p(adjusted_votes / min_votes)
        / math.log1p(max_votes / min_votes)
        * 10
    )

    return clip_0_10(score)


def popularity_kp(kp_votes: int, year: int) -> float:
    return popularity_by_votes(
        votes=kp_votes,
        year=year,
        min_votes=5000,
        max_votes=5000000
    )


def popularity_score(imdb_votes: int, year: int) -> float:
    return popularity_by_votes(
        votes=imdb_votes,
        year=year,
        min_votes=50,
        max_votes=5000
    )


FORMATTERS = {
    "kp_popularity": lambda raw, main_info: popularity_kp(raw["kp_votes"], main_info["year"]),
    "imdb_popularity": lambda raw, main_info: popularity_score(raw["imdb_votes"], main_info["year"])
}


def raw_to_struct(raw: dict, main_info: dict):
    computed_scores = {}
    raw_schema = scheme.get_schema(scheme.RAW_SCORES)

    for raw_feature, settings in raw_schema.items():
        formated = settings["formated"]
        if formated is None:
            computed_scores[raw_feature] = raw[raw_feature]
        else:
            computed_scores[formated] = FORMATTERS[formated](raw, main_info)

    return computed_scores


def tag_to_score(value: int, max_value: int = 1) -> float:
    if max_value is None:
        return clip_0_10(value)
    if max_value <= 0:
        return 0
    return value / max_value * 10


def tags_to_features(tags_vibe: dict) -> dict:
    tags_schema = scheme.get_schema(scheme.TAGS_VIBE)
    features = {}
    for feature, value in tags_vibe.items():
        max_value = tags_schema[feature].get("max_value", 1)
        features[feature] = tag_to_score(value, max_value)
    return features

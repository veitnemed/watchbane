"""Преобразует оценки, голоса и теги в числовые признаки модели."""

import math

from config import constant
from config import scheme


def clip_0_10(value: float) -> float:
    """Ограничивает число диапазоном от 0 до 10."""
    return max(0, min(10, value))


def popularity_by_votes(votes: int, year: int, min_votes: int, max_votes: int) -> float:
    """Считает популярность по количеству голосов и году выхода."""
    age = max(1, constant.NOW_YEAR - year)
    adjusted_votes = votes / (age ** 0.25)

    score = (
        math.log1p(adjusted_votes / min_votes)
        / math.log1p(max_votes / min_votes)
        * 10
    )

    return clip_0_10(score)


def raw_to_struct(raw: dict, main_info: dict):
    """Преобразует сырые оценки в вычисленные признаки модели."""
    computed_scores = {}
    raw = raw if isinstance(raw, dict) else {}

    for raw_feature in ("tmdb_score", "tmdb_votes", "tmdb_popularity"):
        if raw_feature in raw:
            computed_scores[raw_feature] = raw[raw_feature]

    return computed_scores


def tag_to_score(value: int, max_value: int = 1) -> float:
    """Переводит значение тега в шкалу от 0 до 10."""
    if max_value is None:
        return clip_0_10(value)
    if max_value <= 0:
        return 0
    return value / max_value * 10


def tags_to_features(tags_vibe: dict, section_name: str = scheme.TAGS_VIBE) -> dict:
    """Преобразует теги фильма в признаки модели."""
    tags_schema = scheme.get_schema(section_name)
    features = {}
    for feature, value in tags_vibe.items():
        max_value = tags_schema[feature].get("max_value", 1)
        features[feature] = tag_to_score(value, max_value)
    return features

"""Feature vector assembly for watched records."""

from config import constant
from common import format_score


def build_computed_scores(raw_scores: dict, main_info: dict) -> dict:
    """Build computed_scores from raw_scores and main_info."""
    return format_score.raw_to_struct(raw_scores, main_info)


def build_feature_vector(computed_scores: dict, genre_tags: dict) -> dict:
    """Assemble the full ML feature vector for a watched record."""
    features = {
        constant.BIAS_FEATURE: 1.0,
    }
    for feature in computed_scores:
        features[feature] = computed_scores[feature]
    for feature, value in format_score.tags_to_features(genre_tags, constant.GENRE_SECTION).items():
        features[feature] = value
    return features

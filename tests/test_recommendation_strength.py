from candidates.scoring.recommendation_strength import (
    RECOMMENDATION_PROMISING_THRESHOLD,
    RECOMMENDATION_STRONG_THRESHOLD,
    resolve_recommendation_strength,
)


def test_recommendation_strength_thresholds() -> None:
    assert RECOMMENDATION_STRONG_THRESHOLD == 0.72
    assert RECOMMENDATION_PROMISING_THRESHOLD == 0.58
    assert resolve_recommendation_strength(0.72) == "strong"
    assert resolve_recommendation_strength(0.58) == "promising"
    assert resolve_recommendation_strength(0.5799) == "explore"
    assert resolve_recommendation_strength(None) == "insufficient_data"
    assert resolve_recommendation_strength(0.99, rating_confidence="unknown") == "insufficient_data"

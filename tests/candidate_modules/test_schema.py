"""Tests for candidate schema normalization."""

from candidates.schema import normalize_candidate_record


def test_normalize_candidate_record_preserves_unknown_fields() -> None:
    candidate = {"title": "Test", "year": 2020, "custom_field": "keep"}
    normalized = normalize_candidate_record(candidate)
    assert normalized["custom_field"] == "keep"


def test_normalize_candidate_record_sets_is_complete() -> None:
    candidate = {
        "title": "Complete",
        "year": 2020,
        "kp_score": 8.0,
        "kp_votes": 100,
        "imdb_score": 7.5,
        "imdb_votes": 200,
    }
    normalized = normalize_candidate_record(candidate)
    assert normalized["is_complete"] is True

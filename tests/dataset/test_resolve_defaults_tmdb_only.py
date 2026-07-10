"""Tests for TMDb-only add-title defaults."""

from config import scheme
from dataset.resolve.defaults import build_empty_add_defaults, build_tmdb_add_defaults, extract_tmdb_raw_scores


def test_tmdb_data_builds_defaults_with_tmdb_raw_scores() -> None:
    defaults = build_tmdb_add_defaults(
        {
            "title": "TMDb Show",
            "year": 2024,
            "country": "США",
            "genres_tmdb": ["Drama"],
            "tmdb_score": 7.8,
            "tmdb_votes": 456,
            "tmdb_popularity": 12.3,
        }
    )

    assert defaults[scheme.MAIN_INFO]["title"] == "TMDb Show"
    assert defaults[scheme.MAIN_INFO]["year"] == 2024
    assert defaults[scheme.MAIN_INFO]["country"] == "США"
    assert defaults[scheme.RAW_SCORES] == {
        "tmdb_score": 7.8,
        "tmdb_votes": 456,
        "tmdb_popularity": 12.3,
    }
    assert defaults["genres_tmdb"] == ["Drama"]


def test_tmdb_defaults_do_not_create_kp_or_imdb_fields() -> None:
    defaults = build_tmdb_add_defaults(
        {
            "title": "TMDb Show",
            "kp_score": 9.9,
            "kp_votes": 1000,
            "imdb_score": 8.8,
            "imdb_votes": 2000,
            "tmdb_score": 7.8,
        }
    )
    raw_scores = defaults[scheme.RAW_SCORES]

    assert raw_scores == {"tmdb_score": 7.8}
    assert "kp_score" not in raw_scores
    assert "kp_votes" not in raw_scores
    assert "imdb_score" not in raw_scores
    assert "imdb_votes" not in raw_scores


def test_extract_tmdb_raw_scores_returns_only_tmdb_fields() -> None:
    assert extract_tmdb_raw_scores(
        {
            "tmdb_score": 7.8,
            "tmdb_votes": 456,
            "tmdb_popularity": 12.3,
            "kp_score": 9.9,
            "imdb_score": 8.8,
        }
    ) == {
        "tmdb_score": 7.8,
        "tmdb_votes": 456,
        "tmdb_popularity": 12.3,
    }


def test_empty_defaults_stay_valid_for_manual_add() -> None:
    defaults = build_empty_add_defaults("Manual Title")

    assert defaults[scheme.MAIN_INFO]["title"] == "Manual Title"
    assert defaults[scheme.MAIN_INFO]["user_score"] is None
    assert defaults[scheme.RAW_SCORES] == {}
    assert "genres_tmdb" not in defaults

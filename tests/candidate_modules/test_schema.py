"""Tests for candidate schema normalization."""

from candidates.models.schema import (
    normalize_candidate_record,
    resolve_canonical_year,
    strip_external_rating_fields,
)


def test_normalize_candidate_record_preserves_unknown_fields() -> None:
    candidate = {"title": "Test", "year": 2020, "custom_field": "keep"}
    normalized = normalize_candidate_record(candidate)
    assert normalized["custom_field"] == "keep"


def test_tmdb_candidate_is_complete_without_kp_imdb_fields() -> None:
    candidate = {
        "title": "Complete",
        "year": 2020,
        "tmdb_id": 123,
        "tmdb_score": 7.5,
        "tmdb_votes": 200,
        "genres_tmdb": ["Drama"],
        "country_codes": ["US"],
    }
    normalized = normalize_candidate_record(candidate)
    assert normalized["is_complete"] is True
    assert normalized["missing_fields"] == []


def test_tmdb_candidate_without_tmdb_id_is_incomplete() -> None:
    candidate = {
        "title": "No TMDb",
        "year": 2020,
        "tmdb_score": 7.5,
        "tmdb_votes": 200,
        "genres": ["Drama"],
        "countries": ["US"],
    }
    normalized = normalize_candidate_record(candidate)
    assert normalized["is_complete"] is False
    assert normalized["missing_fields"] == ["tmdb_id"]


def test_tmdb_candidate_without_genres_and_countries_is_incomplete() -> None:
    candidate = {
        "title": "No Taxonomy",
        "year": 2020,
        "tmdb_id": 123,
        "tmdb_score": 7.5,
        "tmdb_votes": 200,
    }
    normalized = normalize_candidate_record(candidate)
    assert normalized["is_complete"] is False
    assert normalized["missing_fields"] == ["genres", "countries"]


def test_ensure_candidate_defaults_does_not_create_kp_imdb_rating_fields() -> None:
    candidate = {
        "title": "TMDb Only",
        "first_air_date": "2022-03-04",
        "tmdb_id": 123,
        "tmdb_score": 7.5,
        "tmdb_votes": 200,
        "genre_keys": ["drama"],
        "origin_country": ["US"],
    }
    normalized = normalize_candidate_record(candidate)
    for field_name in (
        "kp_score",
        "kp_votes",
        "kp_rating",
        "kp_id",
        "kp_status",
        "imdb_score",
        "imdb_votes",
        "imdb_rating",
    ):
        assert field_name not in normalized
    assert normalized["source"] == "tmdb"
    assert normalized["source_provider"] == "tmdb"
    assert normalized["source_version"] == 2
    assert normalized["tmdb_popularity"] is None
    assert normalized["quality_score"] is None
    assert normalized["hidden_gem_score"] is None
    assert normalized["final_score"] is None
    assert normalized["is_complete"] is True
    assert normalized["missing_fields"] == []
    assert "imdb_id" in normalized["optional_missing_fields"]


def test_resolve_canonical_year_uses_year_then_first_air_date_only() -> None:
    assert resolve_canonical_year({"imdb_start_year": 2016, "year": 2015}) == 2015
    assert resolve_canonical_year({"kp_year": 2017, "first_air_date": "2021-09-10"}) == 2021


def test_strip_external_rating_fields_preserves_imdb_id_and_tmdb_fields() -> None:
    stripped = strip_external_rating_fields({
        "title": "Strip",
        "kp_score": 8.0,
        "kp_votes": 100,
        "kp_rating": 8.1,
        "kp_id": 123,
        "kp_status": "done",
        "kp_year": 2020,
        "imdb_score": 7.5,
        "imdb_rating": 7.6,
        "imdb_votes": 200,
        "imdb_start_year": 2020,
        "imdb_end_year": 2024,
        "imdb_genres": ["Drama"],
        "imdb_title_type": "tvSeries",
        "imdb_is_adult": 0,
        "imdb_found_in_sql": True,
        "imdb_id": "tt123",
        "tmdb_id": 456,
        "tmdb_score": 7.7,
        "tmdb_votes": 300,
        "tmdb_popularity": 12.3,
    })
    for field_name in (
        "kp_score",
        "kp_votes",
        "kp_rating",
        "kp_id",
        "kp_status",
        "kp_year",
        "imdb_score",
        "imdb_rating",
        "imdb_votes",
        "imdb_start_year",
        "imdb_end_year",
        "imdb_genres",
        "imdb_title_type",
        "imdb_is_adult",
        "imdb_found_in_sql",
    ):
        assert field_name not in stripped
    assert stripped["imdb_id"] == "tt123"
    assert stripped["tmdb_id"] == 456
    assert stripped["tmdb_score"] == 7.7
    assert stripped["tmdb_votes"] == 300
    assert stripped["tmdb_popularity"] == 12.3

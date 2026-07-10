"""Tests for dataset.transfer.candidate."""

import copy

from config import scheme
from dataset.transfer.candidate import (
    build_candidate_genre_transfer_preview,
    build_candidate_transfer_payload,
)


def test_transfer_payload_exposes_tmdb_genres_from_genre_keys() -> None:
    candidate = {
        "title": "Mapped Transfer",
        "year": 2021,
        "genres": ["Mystery"],
        "genre_keys": ["mystery", "drama"],
    }
    payload = build_candidate_transfer_payload(candidate)

    assert "genre" not in payload["defaults"]
    assert payload["defaults"]["genres_tmdb"] == ["Mystery"]


def test_transfer_payload_falls_back_to_raw_genres() -> None:
    candidate = {
        "title": "Legacy Transfer",
        "genres": ["драма", "криминал"],
    }
    payload = build_candidate_transfer_payload(candidate)

    assert payload["defaults"]["genres_tmdb"] == ["драма", "криминал"]


def test_transfer_payload_uses_tmdb_candidate_fields_without_kp_imdb() -> None:
    candidate = {
        "title": "TMDb Transfer",
        "first_air_date": "2022-03-10",
        "countries": ["Россия"],
        "genre_keys": ["drama"],
        "description": "Main description.",
        "poster_url": "https://example.com/poster.jpg",
        "tmdb_id": 100,
        "tmdb_score": 8.2,
        "tmdb_votes": 1234,
        "tmdb_popularity": 55.5,
        "kp_score": 9.9,
        "imdb_score": 9.1,
    }

    payload = build_candidate_transfer_payload(candidate)
    defaults = payload["defaults"]

    assert defaults[scheme.MAIN_INFO]["title"] == "TMDb Transfer"
    assert defaults[scheme.MAIN_INFO]["media_type"] == "tv"
    assert defaults[scheme.MAIN_INFO]["year"] == 2022
    assert defaults[scheme.MAIN_INFO]["country"] == "Россия"
    assert defaults[scheme.RAW_SCORES] == {
        "tmdb_score": 8.2,
        "tmdb_votes": 1234,
        "tmdb_popularity": 55.5,
    }
    assert "kp_score" not in defaults[scheme.RAW_SCORES]
    assert "imdb_score" not in defaults[scheme.RAW_SCORES]
    assert payload["meta_payload"]["description"] == "Main description."
    assert payload["meta_payload"]["poster_url"] == "https://example.com/poster.jpg"


def test_transfer_payload_preserves_movie_media_type_and_release_date_year() -> None:
    payload = build_candidate_transfer_payload({
        "title": "Watchmen",
        "media_type": "movie",
        "release_date": "2009-03-06",
    })

    assert payload["defaults"][scheme.MAIN_INFO]["media_type"] == "movie"
    assert payload["defaults"][scheme.MAIN_INFO]["year"] == 2009


def test_transfer_payload_coerces_string_year_to_int() -> None:
    payload = build_candidate_transfer_payload({
        "title": "String Year",
        "year": "2021",
    })

    assert payload["defaults"][scheme.MAIN_INFO]["year"] == 2021


def test_transfer_payload_falls_back_to_first_air_date_when_year_invalid() -> None:
    payload = build_candidate_transfer_payload({
        "title": "Date Year",
        "year": "unknown",
        "first_air_date": "2020-05-01",
    })

    assert payload["defaults"][scheme.MAIN_INFO]["year"] == 2020


def test_transfer_payload_uses_genres_field_when_present() -> None:
    payload = build_candidate_transfer_payload({
        "title": "By Genres",
        "genres": ["комедия"],
        "genres_tmdb": ["криминал"],
    })

    assert payload["defaults"]["genres_tmdb"] == ["комедия", "криминал"]


def test_transfer_payload_description_uses_overview_fallback_and_poster_hint() -> None:
    candidate = {
        "title": "Overview Transfer",
        "overview": "Overview fallback.",
        "poster_path": "/poster.jpg",
    }

    payload = build_candidate_transfer_payload(candidate)

    assert payload["meta_payload"]["description"] == "Overview fallback."
    assert payload["meta_payload"]["poster_path"] == "/poster.jpg"


def test_transfer_payload_does_not_mutate_candidate() -> None:
    candidate = {
        "title": "Immutable",
        "genre_keys": ["mystery"],
        "genres": ["Mystery"],
    }
    before = copy.deepcopy(candidate)
    build_candidate_transfer_payload(candidate)
    assert candidate == before


def test_genre_preview_reports_raw_genres() -> None:
    preview = build_candidate_genre_transfer_preview({
        "genre_keys": ["mystery", "drama"],
        "genres": ["Mystery"],
    })

    assert preview["genre_keys"] == ["mystery", "drama"]
    assert preview["raw_genres"] == ["Mystery"]
    assert preview["warn_missing_genres"] is False


def test_genre_preview_warns_when_raw_signals_present_but_unparsed() -> None:
    preview = build_candidate_genre_transfer_preview({
        "genres": ["TotallyUnknownGenreXYZ"],
    })

    assert preview["has_raw_genre_signals"] is True
    assert preview["warn_missing_genres"] is False
    assert preview["raw_genres"] == ["TotallyUnknownGenreXYZ"]

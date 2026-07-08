"""Tests for dataset.transfer.candidate."""

import copy

from config import constant
from config import scheme
from dataset.transfer.candidate import (
    build_candidate_genre_transfer_preview,
    build_candidate_transfer_genre_defaults,
    build_candidate_transfer_payload,
)


def test_transfer_payload_uses_genre_keys_mapper() -> None:
    candidate = {
        "title": "Mapped Transfer",
        "year": 2021,
        "genres": ["Mystery"],
        "genre_keys": ["mystery", "drama"],
    }
    payload = build_candidate_transfer_payload(candidate)
    genre_defaults = payload["defaults"][scheme.GENRE]

    assert genre_defaults["has_detective"] == 1
    assert genre_defaults["has_drama"] == 1
    assert "has_mystery" not in genre_defaults
    assert set(genre_defaults.keys()) == set(constant.GENRE)


def test_transfer_payload_falls_back_to_raw_genres() -> None:
    candidate = {
        "title": "Legacy Transfer",
        "genres": ["драма", "криминал"],
    }
    payload = build_candidate_transfer_payload(candidate)
    genre_defaults = payload["defaults"][scheme.GENRE]

    assert genre_defaults["has_drama"] == 1
    assert genre_defaults["has_crime"] == 1


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


def test_transfer_payload_genre_priority_genre_keys_then_genres_then_genres_tmdb() -> None:
    by_keys = build_candidate_transfer_payload({
        "title": "By Keys",
        "genre_keys": ["drama"],
        "genres": ["комедия"],
        "genres_tmdb": ["криминал"],
    })["defaults"][scheme.GENRE]
    by_genres = build_candidate_transfer_payload({
        "title": "By Genres",
        "genres": ["комедия"],
        "genres_tmdb": ["криминал"],
    })["defaults"][scheme.GENRE]
    by_tmdb = build_candidate_transfer_payload({
        "title": "By TMDb Genres",
        "genres_tmdb": ["криминал"],
    })["defaults"][scheme.GENRE]

    assert by_keys["has_drama"] == 1
    assert by_keys["has_comedy"] == 0
    assert by_genres["has_comedy"] == 1
    assert by_genres["has_crime"] == 0
    assert by_tmdb["has_crime"] == 1


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


def test_genre_preview_maps_genre_keys() -> None:
    preview = build_candidate_genre_transfer_preview({
        "genre_keys": ["mystery", "drama"],
        "genres": ["Mystery"],
    })

    assert preview["mapper_status"] == "ok"
    assert preview["used_fallback"] is False
    assert "has_detective" in preview["active_has_features"]
    assert preview["dataset_genre"] == build_candidate_transfer_genre_defaults({
        "genre_keys": ["mystery", "drama"],
        "genres": ["Mystery"],
    })


def test_genre_preview_warns_when_all_zero_with_raw_signals() -> None:
    preview = build_candidate_genre_transfer_preview({
        "genres": ["TotallyUnknownGenreXYZ"],
    })

    assert preview["has_raw_genre_signals"] is True
    assert preview["warn_all_genres_zero"] is True
    assert preview["active_has_features"] == []

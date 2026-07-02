"""Tests for the TMDb-only candidate normalizer."""

from candidates.sources.tmdb.normalizer import prepare_tmdb_candidate


def _raw_details(**overrides) -> dict:
    payload = {
        "id": 101,
        "name": "Метод",
        "original_name": "Metod",
        "first_air_date": "2015-10-18",
        "last_air_date": "2021-02-28",
        "overview": "Русское описание",
        "genres": [
            {"id": 18, "name": "Drama"},
            {"id": 80, "name": "Crime"},
        ],
        "origin_country": ["RU"],
        "production_countries": [
            {"iso_3166_1": "RU", "name": "Russia"},
        ],
        "original_language": "ru",
        "networks": [
            {"id": 1, "name": "Channel One"},
        ],
        "production_companies": [
            {"id": 2, "name": "Sreda"},
        ],
        "vote_average": 7.4,
        "vote_count": 20,
        "popularity": 14.5,
        "external_ids": {"imdb_id": "tt5135336"},
        "poster_path": "/poster.jpg",
        "backdrop_path": "/backdrop.jpg",
        "content_ratings": {
            "results": [
                {"iso_3166_1": "RU", "rating": "18+"},
            ],
        },
        "watch/providers": {
            "results": {
                "RU": {
                    "flatrate": [
                        {"provider_name": "Kinopoisk"},
                    ],
                },
            },
        },
        "aggregate_credits": {
            "cast": [
                {
                    "id": 10,
                    "name": "Константин Хабенский",
                    "roles": [
                        {"character": "Меглин", "episode_count": 16},
                    ],
                },
            ],
            "crew": [
                {
                    "id": 20,
                    "name": "Юрий Быков",
                    "jobs": [
                        {"job": "Director", "episode_count": 8},
                    ],
                },
            ],
        },
        "keywords": {
            "results": [
                {"id": 1, "name": "detective"},
            ],
        },
        "imdb_score": 9.9,
        "imdb_votes": 999999,
        "kp_score": 9.9,
        "kp_votes": 999999,
        "kp_id": 123,
        "kp_status": "done",
        "imdb_rating": 9.9,
        "imdb_genres": ["Drama"],
    }
    payload.update(overrides)
    return payload


def test_ru_show_with_20_tmdb_votes_is_complete() -> None:
    candidate = prepare_tmdb_candidate(
        _raw_details(),
        country="RU",
        source_query={"sort_by": "vote_count.desc"},
        source_trace=[{"slice_name": "origin_votes"}],
    )

    assert candidate["is_complete"] is True
    assert candidate["missing_fields"] == []
    assert candidate["tmdb_id"] == 101
    assert candidate["title"] == "Метод"
    assert candidate["year"] == 2015
    assert candidate["tmdb_score"] == 7.4
    assert candidate["tmdb_votes"] == 20
    assert candidate["source"] == "tmdb"
    assert candidate["source_provider"] == "tmdb"
    assert candidate["source_version"] == 2
    assert candidate["source_trace"] == [{"slice_name": "origin_votes"}]


def test_imdb_id_is_preserved_without_imdb_rating_fields() -> None:
    candidate = prepare_tmdb_candidate(_raw_details())

    assert candidate["imdb_id"] == "tt5135336"
    for field_name in (
        "imdb_score",
        "imdb_votes",
        "imdb_rating",
        "imdb_genres",
        "kp_score",
        "kp_votes",
        "kp_id",
        "kp_status",
    ):
        assert field_name not in candidate


def test_empty_overview_falls_back_to_translations() -> None:
    candidate = prepare_tmdb_candidate(_raw_details(
        overview="",
        translations={
            "translations": [
                {
                    "iso_639_1": "en",
                    "iso_3166_1": "US",
                    "data": {"overview": "English fallback"},
                },
            ],
        },
    ))

    assert candidate["overview"] == "English fallback"
    assert candidate["description"] == "English fallback"


def test_genres_and_countries_are_filled() -> None:
    candidate = prepare_tmdb_candidate(_raw_details())

    assert candidate["genres"] == ["Drama", "Crime"]
    assert candidate["genre_keys"] == ["drama", "crime"]
    assert candidate["countries"] == ["RU", "Russia"]
    assert candidate["country_codes"] == ["RU"]
    assert candidate["original_language"] == "ru"
    assert candidate["networks"] == ["Channel One"]
    assert candidate["production_companies"] == ["Sreda"]


def test_media_people_keywords_and_providers_are_mapped() -> None:
    candidate = prepare_tmdb_candidate(_raw_details())

    assert candidate["poster_path"] == "/poster.jpg"
    assert candidate["poster_url"].endswith("/poster.jpg")
    assert candidate["backdrop_url"].endswith("/backdrop.jpg")
    assert candidate["content_rating"] == "18+"
    assert candidate["watch_providers"] == ["Kinopoisk"]
    assert candidate["actors_top"][0]["name"] == "Константин Хабенский"
    assert candidate["crew_top"][0]["role"] == "Director"
    assert candidate["keywords"] == ["detective"]

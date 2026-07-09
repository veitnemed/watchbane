"""Tests for TMDb details helpers."""

from apis import tmdb_api


def _details_payload(**overrides) -> dict:
    payload = {
        "id": 101,
        "name": "Show",
        "overview": "Русское описание",
        "poster_path": "/poster.jpg",
        "external_ids": {
            "imdb_id": "tt123",
            "tvdb_id": 456,
        },
        "aggregate_credits": {
            "cast": [
                {
                    "id": 1,
                    "name": "Actor One",
                    "roles": [
                        {"character": "Hero", "episode_count": 12},
                    ],
                },
                {
                    "id": 2,
                    "name": "Actor Two",
                    "roles": [
                        {"character": "Friend", "episode_count": 3},
                    ],
                },
            ],
            "crew": [
                {
                    "id": 3,
                    "name": "Writer One",
                    "jobs": [
                        {"job": "Writer", "episode_count": 8},
                    ],
                },
            ],
        },
    }
    payload.update(overrides)
    return payload


def test_get_tv_details_uses_default_tv_detail_appends(monkeypatch, tmp_path) -> None:
    calls = []
    monkeypatch.setattr(tmdb_api, "DETAILS_CACHE_DIR", tmp_path)

    def fake_cached_tmdb_get(path, params, cache_path, *, force_refresh=False, token=None):
        calls.append((path, params, cache_path, force_refresh, token))
        return {"id": 101}

    monkeypatch.setattr(tmdb_api, "cached_tmdb_get", fake_cached_tmdb_get)

    result = tmdb_api.get_tv_details(101, token="token")

    assert result == {"id": 101}
    assert calls[0][0] == "/tv/101"
    assert calls[0][1]["append_to_response"] == ",".join(tmdb_api.DEFAULT_TV_DETAIL_APPENDS)
    assert "aggregate_credits" in calls[0][1]["append_to_response"]
    assert str(calls[0][2]).endswith(".json")


def test_get_movie_details_uses_movie_endpoint_and_default_appends(monkeypatch, tmp_path) -> None:
    calls = []
    monkeypatch.setattr(tmdb_api, "DETAILS_CACHE_DIR", tmp_path)

    def fake_cached_tmdb_get(path, params, cache_path, *, force_refresh=False, token=None):
        calls.append((path, params, cache_path, force_refresh, token))
        return {"id": 202}

    monkeypatch.setattr(tmdb_api, "cached_tmdb_get", fake_cached_tmdb_get)

    result = tmdb_api.get_movie_details(202, token="token")

    assert result == {"id": 202}
    assert calls[0][0] == "/movie/202"
    assert calls[0][1]["append_to_response"] == ",".join(tmdb_api.DEFAULT_MOVIE_DETAIL_APPENDS)
    assert "release_dates" in calls[0][1]["append_to_response"]
    assert "movie_202" in str(calls[0][2])


def test_search_movie_by_title_uses_movie_search(monkeypatch) -> None:
    calls = []

    def fake_tmdb_get(path, params, *, token=None):
        calls.append((path, params, token))
        return {"results": [{"id": 202, "title": "Movie"}]}

    monkeypatch.setattr(tmdb_api, "tmdb_get", fake_tmdb_get)

    assert tmdb_api.search_movie_by_title("Movie", token="token") == [{"id": 202, "title": "Movie"}]
    assert calls[0][0] == "/search/movie"
    assert calls[0][1]["include_adult"] == "false"


def test_get_movie_genre_list_uses_movie_genre_cache(monkeypatch, tmp_path) -> None:
    calls = []
    monkeypatch.setattr(tmdb_api, "GENRE_CACHE_DIR", tmp_path)

    def fake_cached_tmdb_get(path, params, cache_path, *, force_refresh=False, token=None):
        calls.append((path, params, cache_path, force_refresh, token))
        return {"genres": [{"id": 18, "name": "Drama"}]}

    monkeypatch.setattr(tmdb_api, "cached_tmdb_get", fake_cached_tmdb_get)

    assert tmdb_api.get_movie_genre_list("en-US", token="token") == [{"id": 18, "name": "Drama"}]
    assert calls[0][0] == "/genre/movie/list"
    assert calls[0][1] == {"language": "en-US"}
    assert str(calls[0][2]).endswith("movie_en_US.json")


def test_extract_best_overview_prefers_raw_ru_overview() -> None:
    assert tmdb_api.extract_best_overview(_details_payload()) == "Русское описание"


def test_extract_best_overview_falls_back_to_translation_en() -> None:
    details = _details_payload(
        overview="",
        translations={
            "translations": [
                {
                    "iso_639_1": "en",
                    "iso_3166_1": "US",
                    "data": {"overview": "English overview"},
                },
            ],
        },
    )

    assert tmdb_api.extract_best_overview(details) == "English overview"


def test_extract_best_poster_path_uses_direct_poster() -> None:
    assert tmdb_api.extract_best_poster_path(_details_payload()) == "/poster.jpg"


def test_extract_external_ids_preserves_imdb_id() -> None:
    assert tmdb_api.extract_external_ids(_details_payload())["imdb_id"] == "tt123"
    assert tmdb_api.normalize_tmdb_tv(_details_payload())["imdb_id"] == "tt123"


def test_normalize_tmdb_movie_maps_movie_fields() -> None:
    movie = tmdb_api.normalize_tmdb_movie({
        "id": 202,
        "title": "Movie",
        "original_title": "Original Movie",
        "release_date": "2009-03-06",
        "runtime": 162,
        "overview": "Overview",
        "poster_path": "/movie.jpg",
        "external_ids": {"imdb_id": "tt0409459"},
        "production_countries": [{"iso_3166_1": "US", "name": "United States"}],
        "genres": [{"id": 18, "name": "Drama"}],
        "vote_average": 7.3,
        "vote_count": 9000,
        "popularity": 55.5,
        "release_dates": {
            "results": [
                {"iso_3166_1": "RU", "release_dates": [{"certification": "18+"}]},
            ],
        },
        "credits": {
            "cast": [{"id": 1, "name": "Actor", "character": "Hero"}],
            "crew": [{"id": 2, "name": "Director", "job": "Director"}],
        },
    })

    assert movie["media_type"] == "movie"
    assert movie["tmdb_id"] == 202
    assert movie["imdb_id"] == "tt0409459"
    assert movie["title"] == "Movie"
    assert movie["year"] == 2009
    assert movie["runtime"] == 162
    assert movie["runtime_minutes"] == 162
    assert "imdb_runtime_minutes" not in movie
    assert "imdb_rating" not in movie
    assert "imdb_votes" not in movie
    assert "imdb_genres" not in movie
    assert movie["genres_tmdb"] == ["Drama"]
    assert movie["tmdb_country_codes"] == ["US"]
    assert movie["content_rating"] == "18+"
    assert movie["actors_top"][0]["role"] == "Hero"


def test_extract_aggregate_credits_top_parses_people() -> None:
    credits = tmdb_api.extract_aggregate_credits_top(_details_payload(), limit=1)

    assert credits["actors_top"] == [
        {
            "name": "Actor One",
            "role": "Hero",
            "episode_count": 12,
            "tmdb_person_id": 1,
        }
    ]
    assert credits["crew_top"] == [
        {
            "name": "Writer One",
            "role": "Writer",
            "episode_count": 8,
            "tmdb_person_id": 3,
        }
    ]

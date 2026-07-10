from tests.fixtures.filter_replenish_tmdb import SCENARIOS, build_mock_tmdb_client, scenario_names


def test_fixture_contains_required_scenarios() -> None:
    assert scenario_names() == [
        "ru_dark_tv_enough",
        "anime_jp_enough",
        "k_drama_kr_live_tv",
        "us_gb_new_movies_balanced",
        "sparse_tr_underfilled",
        "duplicate_heavy",
        "watched_hidden_overlap",
    ]
    for scenario in SCENARIOS.values():
        assert scenario.name
        assert scenario.description
        assert scenario.pages


def test_mock_client_records_request_params_and_counts_pages() -> None:
    client = build_mock_tmdb_client("ru_dark_tv_enough")

    first = client.discover("tv", {"with_origin_country": "RU", "page": 1, "without_genres": "16,10764"})
    second = client.discover("tv", {"with_origin_country": "RU", "page": 2, "without_genres": "16,10764"})
    empty = client.discover("tv", {"with_origin_country": "RU", "page": 3, "without_genres": "16,10764"})

    assert len(first["results"]) == 20
    assert len(second["results"]) == 20
    assert empty["results"] == []
    assert len(client.discover_requests) == 3
    assert client.api_request_count == 3
    assert client.discover_requests[0]["params"]["without_genres"] == "16,10764"


def test_anime_jp_fixture_returns_animation_candidates_for_movie_and_tv() -> None:
    client = build_mock_tmdb_client("anime_jp_enough")

    movie = client.discover("movie", {"with_origin_country": "JP", "page": 1, "with_genres": "16"})
    tv = client.discover("tv", {"with_origin_country": "JP", "page": 1, "with_genres": "16"})

    assert len(movie["results"]) == 20
    assert len(tv["results"]) == 20
    assert all(16 in row["genre_ids"] for row in movie["results"])
    assert all(16 in row["genre_ids"] for row in tv["results"])


def test_us_gb_new_movies_fixture_is_balanced_by_country() -> None:
    client = build_mock_tmdb_client("us_gb_new_movies_balanced")

    us = client.discover("movie", {"with_origin_country": "US", "page": 1})
    gb = client.discover("movie", {"with_origin_country": "GB", "page": 1})

    assert len(us["results"]) == 20
    assert len(gb["results"]) == 20
    assert {row["origin_country"][0] for row in us["results"]} == {"US"}
    assert {row["origin_country"][0] for row in gb["results"]} == {"GB"}


def test_sparse_tr_fixture_underfills_without_fallback_data() -> None:
    client = build_mock_tmdb_client("sparse_tr_underfilled")

    tr = client.discover("tv", {"with_origin_country": "TR", "page": 1})
    any_country = client.discover("tv", {"page": 1})

    assert len(tr["results"]) == 5
    assert any_country["results"] == []
    assert client.discover_requests[-1]["params"] == {"page": 1}


def test_duplicate_heavy_fixture_contains_duplicate_tmdb_ids() -> None:
    client = build_mock_tmdb_client("duplicate_heavy")

    first = client.discover("movie", {"with_origin_country": "US", "page": 1})["results"]
    second = client.discover("movie", {"with_origin_country": "US", "page": 2})["results"]
    first_ids = {row["id"] for row in first}
    second_ids = {row["id"] for row in second}

    assert first_ids & second_ids
    assert len(second) == 12


def test_watched_hidden_overlap_fixture_exposes_skip_sets() -> None:
    client = build_mock_tmdb_client("watched_hidden_overlap")

    results = client.discover("movie", {"with_origin_country": "US", "page": 1})["results"]

    assert {9001, 9002}.issubset(client.scenario.watched_tmdb_ids)
    assert client.scenario.hidden_tmdb_ids == frozenset({9003})
    assert client.scenario.existing_tmdb_ids == frozenset({9004, 9005})
    assert {row["id"] for row in results} & client.scenario.watched_tmdb_ids


def test_details_requests_are_counted() -> None:
    client = build_mock_tmdb_client("k_drama_kr_live_tv")

    details = client.details("tv", 3001, language="en-US")

    assert details["id"] == 3001
    assert details["name"] == "Details 3001"
    assert client.details_requests == [{"media_type": "tv", "tmdb_id": 3001, "language": "en-US"}]
    assert client.api_request_count == 1

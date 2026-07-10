from candidates.replenish.filter_intent import FilterReplenishIntent
from candidates.replenish.filter_replenisher import replenish_candidates_for_filters
from tests.fixtures.filter_replenish_tmdb import build_mock_tmdb_client


FORBIDDEN_DISCOVER_KEYS = {
    "vote_count.gte",
    "vote_average.gte",
    "vote_count_gte",
    "vote_average_gte",
    "fallback",
    "broad_origin",
    "broad_origin_fallback",
    "without_origin_country",
}


def test_blocking_compatibility_returns_without_tmdb_calls() -> None:
    client = build_mock_tmdb_client("anime_jp_enough")

    result = replenish_candidates_for_filters(
        FilterReplenishIntent(
            preset_id="anime",
            countries=["RU"],
            animation_mode="live_action_only",
        ),
        tmdb_client=client,
        dry_run=True,
    )

    assert result["ok"] is False
    assert result["blocked"] is True
    assert result["created_count"] == 0
    assert result["api_requests"] == 0
    assert client.discover_requests == []


def test_ru_dark_tv_dry_run_selects_30_candidates() -> None:
    client = build_mock_tmdb_client("ru_dark_tv_enough")

    result = replenish_candidates_for_filters(
        FilterReplenishIntent(
            countries=["RU"],
            media_type="tv",
            animation_mode="live_action_only",
            include_genres=["Drama", "Crime"],
            target_add_count=30,
        ),
        tmdb_client=client,
        dry_run=True,
    )

    assert result["ok"] is True
    assert result["dry_run"] is True
    assert result["requested_count"] == 30
    assert result["created_count"] == 30
    assert result["saved_count"] == 0
    assert result["duplicate_count"] == 0
    assert result["api_requests"] == 2
    assert result["details_requests"] == 30
    assert len(result["candidates"]) == 30
    assert {candidate["media_type"] for candidate in result["candidates"]} == {"tv"}
    assert {candidate["target_country"] for candidate in result["candidates"]} == {"RU"}
    for params in result["discover_params_sample"]:
        assert FORBIDDEN_DISCOVER_KEYS.isdisjoint(params)
        assert params["with_origin_country"] == "RU"


def test_replenish_details_replace_discover_genre_ids_with_names_and_posters() -> None:
    client = build_mock_tmdb_client("ru_dark_tv_enough")

    result = replenish_candidates_for_filters(
        FilterReplenishIntent(
            countries=["RU"],
            media_type="tv",
            include_genres=["Drama"],
            target_add_count=1,
        ),
        tmdb_client=client,
        dry_run=True,
    )

    candidate = result["candidates"][0]

    assert result["details_requests"] == 1
    assert candidate["genre_ids"]
    assert candidate["genres"] == ["Drama"]
    assert candidate["genres_tmdb"] == ["Drama"]
    assert candidate["genre_keys"] == ["drama"]
    assert all(str(value).isdigit() is False for value in candidate["genres"])
    assert candidate["poster_path"] == f"/poster-{candidate['tmdb_id']}.jpg"
    assert candidate["poster_url"].endswith(f"/poster-{candidate['tmdb_id']}.jpg")


def test_anime_jp_selects_animation_candidates_across_movie_and_tv() -> None:
    client = build_mock_tmdb_client("anime_jp_enough")

    result = replenish_candidates_for_filters(
        FilterReplenishIntent(
            preset_id="anime",
            countries=["JP"],
            media_type="both",
            animation_mode="animation_only",
            target_add_count=12,
        ),
        tmdb_client=client,
        dry_run=True,
    )

    assert result["created_count"] == 12
    assert {candidate["media_type"] for candidate in result["candidates"]} == {"movie", "tv"}
    assert all(16 in candidate["genre_ids"] for candidate in result["candidates"])
    assert all(sample["with_genres"].split("|")[0] == "16" for sample in result["discover_params_sample"])


def test_duplicate_heavy_scenario_dedupes_by_tmdb_id_and_title() -> None:
    client = build_mock_tmdb_client("duplicate_heavy")

    result = replenish_candidates_for_filters(
        FilterReplenishIntent(
            countries=["US"],
            media_type="movie",
            target_add_count=30,
        ),
        tmdb_client=client,
        dry_run=True,
    )

    tmdb_ids = [candidate["tmdb_id"] for candidate in result["candidates"]]

    assert result["created_count"] == 14
    assert result["duplicate_count"] == 8
    assert len(tmdb_ids) == len(set(tmdb_ids))
    assert result["bucket_results"][0]["duplicate_count"] == 8


def test_sparse_tr_underfills_without_broad_origin_fallback() -> None:
    client = build_mock_tmdb_client("sparse_tr_underfilled")

    result = replenish_candidates_for_filters(
        FilterReplenishIntent(
            countries=["TR"],
            media_type="tv",
            target_add_count=30,
        ),
        tmdb_client=client,
        dry_run=True,
    )

    assert result["created_count"] == 5
    assert result["raw_seen_count"] == 5
    assert result["api_requests"] == 1
    assert all(request["params"].get("with_origin_country") == "TR" for request in client.discover_requests)
    assert all(FORBIDDEN_DISCOVER_KEYS.isdisjoint(request["params"]) for request in client.discover_requests)


def test_watched_hidden_and_existing_ids_are_skipped() -> None:
    client = build_mock_tmdb_client("watched_hidden_overlap")

    result = replenish_candidates_for_filters(
        FilterReplenishIntent(
            countries=["US"],
            media_type="movie",
            target_add_count=20,
        ),
        tmdb_client=client,
        dry_run=True,
    )

    selected_ids = {candidate["tmdb_id"] for candidate in result["candidates"]}

    assert result["created_count"] == 15
    assert result["watched_skipped"] == 2
    assert result["hidden_skipped"] == 1
    assert result["existing_skipped"] == 2
    assert selected_ids.isdisjoint({9001, 9002, 9003, 9004, 9005})


def test_existing_pool_argument_skips_current_candidates() -> None:
    client = build_mock_tmdb_client("us_gb_new_movies_balanced")
    existing_pool = {
        "us-new-movie-1": {
            "title": "US New Movie 1",
            "year": 2024,
            "media_type": "movie",
            "tmdb_id": 4000,
        }
    }

    result = replenish_candidates_for_filters(
        FilterReplenishIntent(
            countries=["US"],
            media_type="movie",
            target_add_count=10,
        ),
        tmdb_client=client,
        dry_run=True,
        existing_pool=existing_pool,
    )

    assert result["created_count"] == 10
    assert result["existing_skipped"] == 1
    assert 4000 not in {candidate["tmdb_id"] for candidate in result["candidates"]}


def test_progress_callback_receives_bucket_page_events() -> None:
    client = build_mock_tmdb_client("ru_dark_tv_enough")
    events = []

    result = replenish_candidates_for_filters(
        FilterReplenishIntent(
            countries=["RU"],
            media_type="tv",
            target_add_count=21,
        ),
        tmdb_client=client,
        progress_callback=events.append,
        dry_run=True,
    )

    assert result["created_count"] == 21
    assert [event["page"] for event in events] == [1, 2]
    assert all(event["bucket_id"].startswith("RU:tv") for event in events)

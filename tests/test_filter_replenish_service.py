from candidates import service as candidate_service
from candidates.repositories import pool_repository
from candidates.replenish.filter_intent import FilterReplenishIntent
from candidates.search.fts_index import search_fts
from storage.sqlite.connection import connect
from tests.fixtures.filter_replenish_tmdb import build_mock_tmdb_client


def _existing_candidate() -> dict:
    return {
        "title": "Existing Movie",
        "year": 2020,
        "media_type": "movie",
        "tmdb_id": 111,
        "tmdb_score": 8.0,
        "tmdb_votes": 1000,
        "tmdb_popularity": 20,
        "genres": ["Drama"],
        "genre_keys": ["drama"],
        "countries": ["US"],
        "country_codes": ["US"],
        "overview": "Existing record must be preserved.",
        "final_score": 0.8,
    }


def test_service_replenish_merges_without_deleting_existing_and_rebuilds_fts(monkeypatch) -> None:
    monkeypatch.setattr("storage.data.load_dataset", lambda: {})
    pool_repository.save_candidate_pool({"existing": _existing_candidate()})
    client = build_mock_tmdb_client("ru_dark_tv_enough")

    result = candidate_service.replenish_candidate_pool_for_filters(
        FilterReplenishIntent(
            countries=["RU"],
            media_type="tv",
            animation_mode="live_action_only",
            target_add_count=30,
        ).to_dict(),
        tmdb_client=client,
        dry_run=False,
    )
    loaded = pool_repository.load_candidate_pool()

    assert result["ok"] is True
    assert result["before_pool_count"] == 1
    assert result["after_pool_count"] == 31
    assert result["saved_count"] == 30
    assert len(result["added_pool_keys"]) == 30
    assert any(candidate["title"] == "Existing Movie" for candidate in loaded.values())
    assert any(candidate["title"].startswith("RU Dark TV") for candidate in loaded.values())
    assert result["save_stats"]["added"] == 30

    conn = connect()
    try:
        hits = search_fts(conn, "Dark TV")
    finally:
        conn.close()
    assert hits


def test_service_dry_run_does_not_mutate_pool(monkeypatch) -> None:
    monkeypatch.setattr("storage.data.load_dataset", lambda: {})
    pool_repository.save_candidate_pool({"existing": _existing_candidate()})
    client = build_mock_tmdb_client("us_gb_new_movies_balanced")

    result = candidate_service.replenish_candidate_pool_for_filters(
        FilterReplenishIntent(
            countries=["US"],
            media_type="movie",
            target_add_count=10,
        ).to_dict(),
        tmdb_client=client,
        dry_run=True,
    )

    assert result["ok"] is True
    assert result["created_count"] == 10
    assert result["saved_count"] == 0
    assert result["before_pool_count"] == 1
    assert result["after_pool_count"] == 1
    assert len(pool_repository.load_candidate_pool()) == 1


def test_service_second_run_skips_existing_candidates(monkeypatch) -> None:
    monkeypatch.setattr("storage.data.load_dataset", lambda: {})
    client = build_mock_tmdb_client("us_gb_new_movies_balanced")
    intent = FilterReplenishIntent(
        countries=["US"],
        media_type="movie",
        target_add_count=10,
    ).to_dict()

    first = candidate_service.replenish_candidate_pool_for_filters(
        intent,
        tmdb_client=client,
        dry_run=False,
    )
    second = candidate_service.replenish_candidate_pool_for_filters(
        intent,
        tmdb_client=build_mock_tmdb_client("us_gb_new_movies_balanced"),
        dry_run=False,
    )

    assert first["saved_count"] == 10
    assert second["created_count"] == 10
    assert second["existing_skipped"] == 10
    assert second["saved_count"] == 10
    assert second["before_pool_count"] == 10
    assert second["after_pool_count"] == 20


def test_service_blocked_result_does_not_save(monkeypatch) -> None:
    monkeypatch.setattr("storage.data.load_dataset", lambda: {})
    pool_repository.save_candidate_pool({"existing": _existing_candidate()})
    client = build_mock_tmdb_client("anime_jp_enough")

    result = candidate_service.replenish_candidate_pool_for_filters(
        FilterReplenishIntent(
            preset_id="anime",
            countries=["RU"],
            animation_mode="live_action_only",
        ).to_dict(),
        tmdb_client=client,
        dry_run=False,
    )

    assert result["ok"] is False
    assert result["blocked"] is True
    assert result["saved_count"] == 0
    assert result["before_pool_count"] == 1
    assert result["after_pool_count"] == 1
    assert len(pool_repository.load_candidate_pool()) == 1
    assert client.discover_requests == []

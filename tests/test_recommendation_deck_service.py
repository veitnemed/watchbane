from __future__ import annotations

from datetime import datetime, timedelta, timezone

from candidates.models.keys import candidate_state_identity_key
from candidates.recommendation_deck_service import (
    DEFAULT_UNKNOWN_RATING_LIMIT,
    EXPANDED_UNKNOWN_RATING_LIMIT,
    RecommendationDeckService,
    _base_score,
    _rank_candidates,
)
from candidates.scoring.rating_confidence import has_unknown_rating
from candidates import title_state_service
from storage.sqlite.impression_repository import get_impression, record_impressions


NOW = datetime(2026, 7, 11, 12, 0, tzinfo=timezone.utc)


def _candidate(index: int, *, title: str | None = None, media_type: str | None = None) -> dict:
    return {
        "title": title or f"Title {index:03d}",
        "year": 1980 + index % 45,
        "media_type": media_type or ("movie" if index % 3 == 0 else "tv"),
        "tmdb_id": 10_000 + index,
        "final_score": 100 - index % 70,
        "tmdb_score": 8.0 - (index % 10) / 10,
        "country": ("US", "RU", "JP", "GB")[index % 4],
        "genres_tmdb": [("Drama", "Comedy", "Action", "Sci-Fi")[index % 4]],
    }


def _pool(count: int) -> dict[str, dict]:
    return {f"candidate-{index}": _candidate(index) for index in range(count)}


def _unrated(index: int) -> dict:
    return {
        **_candidate(500 + index, title=f"Unrated {index:02d}"),
        "year": 2026,
        "tmdb_score": 0,
        "tmdb_votes": 0,
        "tmdb_popularity": 25,
        "country": "RU",
        "country_codes": ["RU"],
        "description": "Complete overview",
        "poster_path": f"/unrated-{index}.jpg",
        "genres": ["Drama"],
        "final_score": 99,
    }


def _service(pool: dict, db_path) -> RecommendationDeckService:
    return RecommendationDeckService(pool_loader=lambda: pool, db_path=db_path)


def _identities(items: list[dict]) -> list[str]:
    return [candidate_state_identity_key(item) for item in items]


def test_deck_caps_active_and_reserve(tmp_path) -> None:
    deck = _service(_pool(150), tmp_path / "deck.sqlite3").build_deck({}, NOW)

    assert len(deck["active"]) == 30
    assert len(deck["reserve"]) == 70
    assert deck["refill_needed"] is False
    assert deck["underfilled_reason"] is None


def test_user_states_and_recent_impressions_are_excluded(tmp_path) -> None:
    db_path = tmp_path / "deck.sqlite3"
    pool = _pool(20)
    watched = pool["candidate-0"]
    deferred = pool["candidate-1"]
    hidden = pool["candidate-2"]
    recent = pool["candidate-3"]
    title_state_service.mark_watched(watched, path=db_path)
    title_state_service.add_to_watchlist(deferred, path=db_path)
    title_state_service.hide_candidate(hidden, path=db_path)
    record_impressions(
        [recent],
        deck_id="previous",
        shown_at=(NOW - timedelta(days=2)).isoformat(timespec="seconds"),
        path=db_path,
    )

    deck = _service(pool, db_path).build_deck({}, NOW, limit_active=30, reserve_size=70)

    shown = set(_identities(deck["active"] + deck["reserve"]))
    assert candidate_state_identity_key(watched) not in shown
    assert candidate_state_identity_key(deferred) not in shown
    assert candidate_state_identity_key(hidden) not in shown
    assert candidate_state_identity_key(recent) not in shown


def test_apply_action_promotes_closest_quality_at_removed_position(tmp_path) -> None:
    service = _service(_pool(8), tmp_path / "deck.sqlite3")
    deck = service.build_deck({}, NOW, limit_active=3, reserve_size=4)
    removed_index = 1
    removed = deck["active"][removed_index]
    expected_promotion = min(
        deck["reserve"],
        key=lambda item: abs(_base_score(item) - _base_score(removed)),
    )

    updated = service.apply_action_and_refill(deck["deck_id"], removed, "hidden")

    assert len(updated["active"]) == 3
    assert candidate_state_identity_key(removed) not in _identities(updated["active"])
    assert candidate_state_identity_key(updated["active"][removed_index]) == candidate_state_identity_key(
        expected_promotion
    )
    assert len(updated["reserve"]) == 3
    promotion_identity = candidate_state_identity_key(expected_promotion).rsplit("|", 1)[0]
    assert get_impression(promotion_identity, expected_promotion["media_type"], path=tmp_path / "deck.sqlite3")


def test_empty_reserve_shrinks_active_and_requests_refill(tmp_path) -> None:
    service = _service(_pool(3), tmp_path / "deck.sqlite3")
    deck = service.build_deck({}, NOW, limit_active=3, reserve_size=0)

    updated = service.apply_action_and_refill(deck["deck_id"], deck["active"][0], "watchlist")

    assert len(updated["active"]) == 2
    assert updated["reserve"] == []
    assert updated["refill_needed"] is True
    assert updated["underfilled_reason"] == "reserve_exhausted"


def test_daily_seed_is_stable_within_day(tmp_path) -> None:
    pool = _pool(120)
    first = _service(pool, tmp_path / "first.sqlite3").build_deck({}, NOW)
    second = _service(pool, tmp_path / "second.sqlite3").build_deck({}, NOW + timedelta(hours=8))

    assert _identities(first["active"] + first["reserve"]) == _identities(
        second["active"] + second["reserve"]
    )


def test_next_day_changes_order_without_changing_eligible_set(tmp_path) -> None:
    pool = _pool(100)
    first = _service(pool, tmp_path / "first.sqlite3").build_deck({}, NOW)
    second = _service(pool, tmp_path / "second.sqlite3").build_deck({}, NOW + timedelta(days=1))
    first_items = _identities(first["active"] + first["reserve"])
    second_items = _identities(second["active"] + second["reserve"])

    assert set(first_items) == set(second_items)
    assert first_items != second_items


def test_duplicate_identity_media_is_emitted_once(tmp_path) -> None:
    pool = _pool(5)
    duplicate = dict(pool["candidate-0"])
    pool["duplicate"] = duplicate
    pool["same-title-movie"] = {
        **duplicate,
        "media_type": "movie" if duplicate["media_type"] == "tv" else "tv",
        "tmdb_id": 99_999,
    }

    deck = _service(pool, tmp_path / "deck.sqlite3").build_deck(
        {}, NOW, limit_active=20, reserve_size=0
    )
    identities = _identities(deck["active"])

    assert len(identities) == len(set(identities))
    assert len(deck["active"]) == 6


def test_impressions_are_recorded_for_active_but_not_reserve(tmp_path) -> None:
    db_path = tmp_path / "deck.sqlite3"
    deck = _service(_pool(10), db_path).build_deck({}, NOW, limit_active=3, reserve_size=5)

    for candidate in deck["active"]:
        identity_key = candidate_state_identity_key(candidate).rsplit("|", 1)[0]
        assert get_impression(identity_key, candidate["media_type"], path=db_path) is not None
    for candidate in deck["reserve"]:
        identity_key = candidate_state_identity_key(candidate).rsplit("|", 1)[0]
        assert get_impression(identity_key, candidate["media_type"], path=db_path) is None


def test_underfilled_deck_reports_reason_and_counts(tmp_path) -> None:
    deck = _service(_pool(4), tmp_path / "deck.sqlite3").build_deck(
        {}, NOW, limit_active=30, reserve_size=70
    )

    assert len(deck["active"]) == 4
    assert len(deck["reserve"]) == 0
    assert deck["refill_needed"] is True
    assert deck["underfilled_reason"] == "active_underfilled"
    assert deck["eligible_count"] == 4


def test_future_release_is_not_eligible(tmp_path) -> None:
    pool = {
        "released": _candidate(1),
        "future": {**_candidate(2), "year": NOW.year + 1},
    }

    deck = _service(pool, tmp_path / "deck.sqlite3").build_deck(
        {}, NOW, limit_active=10, reserve_size=0
    )

    assert [candidate["title"] for candidate in deck["active"]] == [pool["released"]["title"]]
    assert deck["excluded"]["future_release"] == 1


def test_refresh_reuses_same_daily_deck_until_forced(tmp_path) -> None:
    db_path = tmp_path / "deck.sqlite3"
    service = _service(_pool(80), db_path)

    first = service.refresh_deck({}, NOW)
    second = service.refresh_deck({}, NOW + timedelta(hours=1))
    forced = service.refresh_deck({}, NOW + timedelta(hours=2), force_new=True)

    assert second["deck_id"] == first["deck_id"]
    first_candidate = first["active"][0]
    impression_key = candidate_state_identity_key(first_candidate).rsplit("|", 1)[0]
    assert get_impression(impression_key, first_candidate["media_type"], path=db_path)["shown_count"] == 1
    assert forced["deck_id"] != first["deck_id"]


def test_known_rating_candidate_continues_to_rank_by_rating() -> None:
    lower = {"title": "Lower", "year": 2024, "media_type": "movie", "tmdb_score": 6.5, "tmdb_votes": 100}
    higher = {"title": "Higher", "year": 2024, "media_type": "movie", "tmdb_score": 8.4, "tmdb_votes": 100}

    assert _rank_candidates([lower, higher], "2026-07-11")[0]["title"] == "Higher"


def test_default_deck_caps_unknown_ratings(tmp_path) -> None:
    pool = {**_pool(40), **{f"unrated-{index}": _unrated(index) for index in range(20)}}

    deck = _service(pool, tmp_path / "default.sqlite3").build_deck({}, NOW)

    assert deck["unknown_rating_limit"] == DEFAULT_UNKNOWN_RATING_LIMIT
    assert sum(has_unknown_rating(item) for item in deck["active"]) <= DEFAULT_UNKNOWN_RATING_LIMIT


def test_new_releases_in_an_explicit_market_expand_unknown_rating_quota(tmp_path) -> None:
    pool = {**_pool(40), **{f"unrated-{index}": _unrated(index) for index in range(20)}}
    preferences = {"country": ["RU"], "_recommendation_collection": "new"}

    deck = _service(pool, tmp_path / "expanded.sqlite3").build_deck(preferences, NOW)
    unknown_count = sum(has_unknown_rating(item) for item in deck["active"])

    assert deck["unknown_rating_limit"] == EXPANDED_UNKNOWN_RATING_LIMIT
    assert DEFAULT_UNKNOWN_RATING_LIMIT < unknown_count <= EXPANDED_UNKNOWN_RATING_LIMIT

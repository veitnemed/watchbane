from __future__ import annotations

from datetime import datetime, timedelta, timezone

from candidates.models.keys import candidate_state_identity_key
from candidates.recommendation_deck_service import (
    ACTIVE_DECK_SIZE,
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

    assert ACTIVE_DECK_SIZE == 10
    assert len(deck["active"]) == ACTIVE_DECK_SIZE
    assert len(deck["reserve"]) == 70
    assert deck["refill_needed"] is False
    assert deck["underfilled_reason"] is None


def test_action_promotes_from_reserve_to_keep_active_full(tmp_path) -> None:
    """C3-09: with reserve available, hide keeps active at the deck limit."""
    service = _service(_pool(20), tmp_path / "deck.sqlite3")
    deck = service.build_deck({}, NOW)
    removed = deck["active"][0]
    reserve_before = len(deck["reserve"])

    updated = service.apply_action_and_refill(
        deck["deck_id"],
        removed,
        "hidden",
        refill_active=True,
    )

    assert len(updated["active"]) == ACTIVE_DECK_SIZE
    assert len(updated["reserve"]) == reserve_before - 1
    assert updated["last_action"]["promoted_identity"] is not None
    assert candidate_state_identity_key(removed) not in _identities(updated["active"])


def test_refill_active_false_still_shrinks_without_promote(tmp_path) -> None:
    """API opt-out: refill_active=False keeps finite shrink behavior."""
    service = _service(_pool(20), tmp_path / "deck.sqlite3")
    deck = service.build_deck({}, NOW)
    removed = deck["active"][0]

    updated = service.apply_action_and_refill(
        deck["deck_id"],
        removed,
        "hidden",
        refill_active=False,
    )

    assert len(updated["active"]) == ACTIVE_DECK_SIZE - 1
    assert len(updated["reserve"]) == len(deck["reserve"])
    assert updated["last_action"]["promoted_identity"] is None


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


def test_recent_impressions_are_reused_when_fresh_pool_is_exhausted(tmp_path) -> None:
    db_path = tmp_path / "deck.sqlite3"
    pool = _pool(40)
    record_impressions(
        pool.values(),
        deck_id="previous",
        shown_at=(NOW - timedelta(days=2)).isoformat(timespec="seconds"),
        path=db_path,
    )

    deck = _service(pool, db_path).build_deck({}, NOW, limit_active=30, reserve_size=70)

    assert len(deck["active"]) == 30
    assert len(deck["reserve"]) == 10
    assert deck["recently_seen_reused"] == 40
    assert deck["excluded"]["recently_seen"] == 40


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
    assert get_impression(
        promotion_identity,
        expected_promotion["media_type"],
        path=tmp_path / "deck.sqlite3",
    ) is None


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


def test_same_title_year_media_with_different_tmdb_ids_is_emitted_once(tmp_path) -> None:
    first = _candidate(1, title="Shared title", media_type="tv")
    second = {**first, "tmdb_id": 99_002, "final_score": first["final_score"] - 1}
    deck = _service(
        {"first": first, "second": second},
        tmp_path / "deck.sqlite3",
    ).build_deck({}, NOW, limit_active=10, reserve_size=10)

    assert len(deck["active"] + deck["reserve"]) == 1
    assert deck["excluded"]["duplicate"] == 1


def test_same_title_and_tmdb_id_stays_distinct_between_movie_and_tv(tmp_path) -> None:
    movie = _candidate(1, title="Shared title", media_type="movie")
    tv = {**movie, "media_type": "tv"}
    deck = _service(
        {"movie": movie, "tv": tv},
        tmp_path / "deck.sqlite3",
    ).build_deck({}, NOW, limit_active=10, reserve_size=10)

    shown = deck["active"] + deck["reserve"]
    assert len(shown) == 2
    assert {item["media_type"] for item in shown} == {"movie", "tv"}


def test_remakes_with_same_title_and_different_years_are_preserved(tmp_path) -> None:
    original = _candidate(1, title="The Thing", media_type="movie")
    remake = {**original, "year": original["year"] + 20, "tmdb_id": 99_003}
    deck = _service(
        {"original": original, "remake": remake},
        tmp_path / "deck.sqlite3",
    ).build_deck({}, NOW, limit_active=10, reserve_size=10)

    assert {item["year"] for item in deck["active"] + deck["reserve"]} == {
        original["year"],
        remake["year"],
    }


def test_localized_aliases_cannot_duplicate_active_or_reserve(tmp_path) -> None:
    english = {
        **_candidate(1, title="Squid Game", media_type="tv"),
        "localized": {"ru": {"title": "Игра в кальмара"}},
    }
    russian = {
        **_candidate(2, title="Игра в кальмара", media_type="tv"),
        "year": english["year"],
        "localized": {"en": {"title": "Squid Game"}},
    }
    deck = _service(
        {"english": english, "russian": russian},
        tmp_path / "deck.sqlite3",
    ).build_deck({}, NOW, limit_active=1, reserve_size=10)

    assert len(deck["active"] + deck["reserve"]) == 1


def test_top_up_removes_alias_duplicate_between_active_and_reserve(tmp_path) -> None:
    pool = _pool(8)
    service = _service(pool, tmp_path / "deck.sqlite3")
    deck = service.build_deck({}, NOW, limit_active=3, reserve_size=5)
    duplicate = {
        **deck["active"][0],
        "tmdb_id": 88_888,
        "pool_entry_key": "duplicate-alias",
    }
    deck["reserve"].append(duplicate)
    service._decks[deck["deck_id"]] = deck

    updated = service.top_up_deck(deck["deck_id"], NOW)
    identities = _identities(updated["active"] + updated["reserve"])

    assert len(identities) == len(set(identities))
    titles = [
        (item["title"].casefold(), item["year"], item["media_type"])
        for item in updated["active"] + updated["reserve"]
    ]
    assert len(titles) == len(set(titles))


def test_impressions_are_recorded_only_when_active_detail_is_revealed(tmp_path) -> None:
    db_path = tmp_path / "deck.sqlite3"
    service = _service(_pool(10), db_path)
    deck = service.build_deck({}, NOW, limit_active=3, reserve_size=5)

    for candidate in deck["active"]:
        identity_key = candidate_state_identity_key(candidate).rsplit("|", 1)[0]
        assert get_impression(identity_key, candidate["media_type"], path=db_path) is None
    for candidate in deck["reserve"]:
        identity_key = candidate_state_identity_key(candidate).rsplit("|", 1)[0]
        assert get_impression(identity_key, candidate["media_type"], path=db_path) is None

    revealed = deck["active"][0]
    assert service.record_detail_reveal(deck["deck_id"], revealed, shown_at=NOW.isoformat()) is True
    assert service.record_detail_reveal(deck["deck_id"], revealed, shown_at=NOW.isoformat()) is False
    identity_key = candidate_state_identity_key(revealed).rsplit("|", 1)[0]
    assert get_impression(identity_key, revealed["media_type"], path=db_path)["shown_count"] == 1


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


def test_full_release_date_distinguishes_today_from_tomorrow(tmp_path) -> None:
    now = datetime(2026, 7, 13, 12, 0, tzinfo=timezone.utc)
    pool = {
        "today": {**_candidate(1), "year": None, "release_date": "2026-07-13"},
        "tomorrow": {**_candidate(2), "year": None, "release_date": "2026-07-14"},
        "month-only": {**_candidate(3), "year": None, "release_date": "2026-07"},
    }
    deck = _service(pool, tmp_path / "deck.sqlite3").build_deck(
        {}, now, limit_active=10, reserve_size=0
    )

    assert {item["title"] for item in deck["active"]} == {
        pool["today"]["title"],
        pool["month-only"]["title"],
    }
    assert deck["excluded"]["future_release"] == 1


def test_unknown_string_and_zero_year_do_not_crash_or_look_future(tmp_path) -> None:
    pool = {
        "unknown": {**_candidate(1), "year": None},
        "text": {**_candidate(2), "year": "unknown"},
        "zero": {**_candidate(3), "year": 0},
        "string": {**_candidate(4), "year": "2026"},
    }
    deck = _service(pool, tmp_path / "deck.sqlite3").build_deck(
        {}, NOW, limit_active=10, reserve_size=0
    )

    assert len(deck["active"]) == 4
    assert deck["excluded"]["future_release"] == 0


def test_same_instant_across_midnight_and_timezones_has_same_daily_order(tmp_path) -> None:
    pool = _pool(60)
    local_before_midnight = datetime.fromisoformat("2026-12-31T23:30:00-02:00")
    utc_after_midnight = datetime.fromisoformat("2027-01-01T01:30:00+00:00")

    first = _service(pool, tmp_path / "first.sqlite3").build_deck({}, local_before_midnight)
    second = _service(pool, tmp_path / "second.sqlite3").build_deck({}, utc_after_midnight)

    assert _identities(first["active"] + first["reserve"]) == _identities(
        second["active"] + second["reserve"]
    )


def test_leap_day_and_new_year_boundaries_use_utc_calendar(tmp_path) -> None:
    pool = {
        "leap": {**_candidate(1), "year": None, "release_date": "2028-02-29"},
        "next-year": {**_candidate(2), "year": None, "release_date": "2029-01-01"},
    }
    leap_day = datetime(2028, 2, 29, 0, 0, tzinfo=timezone.utc)
    deck = _service(pool, tmp_path / "deck.sqlite3").build_deck(
        {}, leap_day, limit_active=10, reserve_size=0
    )

    assert [item["title"] for item in deck["active"]] == [pool["leap"]["title"]]
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
    assert get_impression(impression_key, first_candidate["media_type"], path=db_path) is None
    assert forced["deck_id"] != first["deck_id"]


def test_refresh_restores_same_deck_order_across_restart_and_next_day(tmp_path) -> None:
    db_path = tmp_path / "deck.sqlite3"
    pool = _pool(120)
    first = _service(pool, db_path).refresh_deck({}, NOW)

    restored = _service(pool, db_path).refresh_deck({}, NOW + timedelta(days=1))

    assert restored["deck_id"] == first["deck_id"]
    assert _identities(restored["active"]) == _identities(first["active"])
    assert _identities(restored["reserve"]) == _identities(first["reserve"])


def test_persisted_deck_restart_skips_full_build_rerank(tmp_path) -> None:
    db_path = tmp_path / "deck.sqlite3"
    pool = _pool(120)
    first = _service(pool, db_path).refresh_deck({}, NOW)
    restarted = _service(pool, db_path)
    restarted.build_deck = lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("persisted deck triggered a full build")
    )

    restored = restarted.refresh_deck({}, NOW + timedelta(hours=1))

    assert restored["deck_id"] == first["deck_id"]
    assert _identities(restored["active"]) == _identities(first["active"])


def test_reveal_idempotence_survives_service_restart(tmp_path) -> None:
    db_path = tmp_path / "deck.sqlite3"
    pool = _pool(30)
    service = _service(pool, db_path)
    deck = service.refresh_deck({}, NOW)
    candidate = deck["active"][0]
    assert service.record_detail_reveal(deck["deck_id"], candidate) is True

    restarted = _service(pool, db_path)
    restored = restarted.refresh_deck({}, NOW + timedelta(hours=1))

    assert restarted.record_detail_reveal(restored["deck_id"], candidate) is False
    impression_key = candidate_state_identity_key(candidate).rsplit("|", 1)[0]
    assert get_impression(impression_key, candidate["media_type"], path=db_path)["shown_count"] == 1


def test_deck_snapshot_respects_interrupted_external_transaction(tmp_path) -> None:
    from storage.sqlite.connection import connect
    from storage.sqlite.migrations import apply_migrations
    from storage.sqlite.recommendation_deck_repository import load_current_deck, save_current_deck

    db_path = tmp_path / "deck.sqlite3"
    original = {"deck_id": "stable-deck", "active": [_candidate(1)], "reserve": []}
    save_current_deck(original, path=db_path)

    conn = connect(db_path)
    apply_migrations(conn)
    try:
        conn.execute("BEGIN")
        save_current_deck(
            {"deck_id": "interrupted-deck", "active": [_candidate(2)], "reserve": []},
            conn=conn,
        )
        conn.rollback()
    finally:
        conn.close()

    assert load_current_deck(path=db_path) == original


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

    assert deck["unknown_rating_limit"] == min(EXPANDED_UNKNOWN_RATING_LIMIT, ACTIVE_DECK_SIZE)
    assert DEFAULT_UNKNOWN_RATING_LIMIT < unknown_count <= ACTIVE_DECK_SIZE


def test_mood_any_hard_drops_junk_format_genres(tmp_path) -> None:
    """C3-01: reality/talk/news/game_show/soap never enter the inbox deck."""
    good = {
        **_candidate(1, title="Solid Drama"),
        "genres": ["Drama"],
        "genre_keys": ["drama"],
        "final_score": 95,
        "tmdb_score": 8.2,
        "tmdb_votes": 500,
    }
    junk_titles = {
        "Reality Junk": ("reality", 10764),
        "Talk Junk": ("talk_show", 10767),
        "News Junk": ("news", 10763),
        "Game Junk": ("game_show", None),
        "Soap Junk": ("soap", 10766),
    }
    pool = {"good": good}
    for index, (title, (genre_key, genre_id)) in enumerate(junk_titles.items(), start=10):
        row = {
            **_candidate(index, title=title, media_type="tv"),
            "genres": [genre_key],
            "genre_keys": [genre_key],
            "final_score": 99,
            "tmdb_score": 9.5,
            "tmdb_votes": 9000,
        }
        if genre_id is not None:
            row["genre_ids"] = [genre_id]
        pool[f"junk-{index}"] = row

    deck = _service(pool, tmp_path / "junk.sqlite3").build_deck({}, NOW)
    titles = {item["title"] for item in deck["active"] + deck["reserve"]}

    assert "Solid Drama" in titles
    assert titles.isdisjoint(junk_titles)
    assert int(deck["excluded"]["junk_genre"]) >= len(junk_titles)


def test_genre_affinity_from_watched_saved_hidden_ranks_deck(tmp_path) -> None:
    """C3-02: TOP/saved genres rise; NOT_FOR_ME/hidden genres fall; titles stay excluded."""
    from dataset.models.user_rating import UserRating

    comedy_seed = {
        **_candidate(1, title="Seed Comedy"),
        "genres": ["Comedy"],
        "genre_keys": ["comedy"],
        "genres_tmdb": ["Comedy"],
        "final_score": 50,
        "tmdb_score": 6.0,
        "tmdb_votes": 100,
    }
    drama_seed = {
        **_candidate(2, title="Seed Drama Bad"),
        "genres": ["Drama"],
        "genre_keys": ["drama"],
        "genres_tmdb": ["Drama"],
        "final_score": 50,
        "tmdb_score": 6.0,
        "tmdb_votes": 100,
    }
    action_seed = {
        **_candidate(3, title="Seed Action Saved"),
        "genres": ["Action"],
        "genre_keys": ["action_adventure"],
        "genres_tmdb": ["Action"],
        "final_score": 50,
        "tmdb_score": 6.0,
        "tmdb_votes": 100,
    }
    scifi_seed = {
        **_candidate(4, title="Seed SciFi Hidden"),
        "genres": ["Sci-Fi"],
        "genre_keys": ["sci_fi_fantasy"],
        "genres_tmdb": ["Sci-Fi"],
        "final_score": 50,
        "tmdb_score": 6.0,
        "tmdb_votes": 100,
    }
    comedy_new = {
        **_candidate(10, title="Fresh Comedy"),
        "genres": ["Comedy"],
        "genre_keys": ["comedy"],
        "genres_tmdb": ["Comedy"],
        "final_score": 70,
        "tmdb_score": 7.0,
        "tmdb_votes": 200,
    }
    drama_new = {
        **_candidate(11, title="Fresh Drama"),
        "genres": ["Drama"],
        "genre_keys": ["drama"],
        "genres_tmdb": ["Drama"],
        "final_score": 95,
        "tmdb_score": 9.0,
        "tmdb_votes": 900,
    }
    action_new = {
        **_candidate(12, title="Fresh Action"),
        "genres": ["Action"],
        "genre_keys": ["action_adventure"],
        "genres_tmdb": ["Action"],
        "final_score": 72,
        "tmdb_score": 7.1,
        "tmdb_votes": 210,
    }
    scifi_new = {
        **_candidate(13, title="Fresh SciFi"),
        "genres": ["Sci-Fi"],
        "genre_keys": ["sci_fi_fantasy"],
        "genres_tmdb": ["Sci-Fi"],
        "final_score": 96,
        "tmdb_score": 9.1,
        "tmdb_votes": 950,
    }
    pool = {
        "comedy_seed": comedy_seed,
        "drama_seed": drama_seed,
        "action_seed": action_seed,
        "scifi_seed": scifi_seed,
        "comedy_new": comedy_new,
        "drama_new": drama_new,
        "action_new": action_new,
        "scifi_new": scifi_new,
    }
    db_path = tmp_path / "affinity.sqlite3"
    title_state_service.mark_watched(comedy_seed, int(UserRating.TOP), path=db_path)
    title_state_service.mark_watched(drama_seed, int(UserRating.NOT_FOR_ME), path=db_path)
    title_state_service.add_to_watchlist(action_seed, path=db_path)
    title_state_service.hide_candidate(scifi_seed, path=db_path)

    service = _service(pool, db_path)
    affinity = service._genre_affinity_profile()
    assert affinity.get("comedy", 0) > 0
    assert affinity.get("drama", 0) < 0
    assert affinity.get("action_adventure", 0) > 0
    assert affinity.get("sci_fi_fantasy", 0) < 0

    deck = service.build_deck({}, NOW)
    titles = [item["title"] for item in deck["active"] + deck["reserve"]]
    assert "Seed Comedy" not in titles
    assert "Seed Drama Bad" not in titles
    assert "Seed Action Saved" not in titles
    assert "Seed SciFi Hidden" not in titles

    ranked = _rank_candidates(
        [comedy_new, drama_new, action_new, scifi_new],
        "affinity-test",
        affinity=affinity,
    )
    ranked_titles = [item["title"] for item in ranked]
    assert ranked_titles.index("Fresh Comedy") < ranked_titles.index("Fresh Drama")
    assert ranked_titles.index("Fresh Action") < ranked_titles.index("Fresh SciFi")

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from candidates import title_state_service
from candidates.pool.storage import candidate_tmdb_identity
from candidates.preferences import SimpleRecommendationPreferences
from candidates.recommendation_deck_service import (
    RecommendationDeckService,
    RelevanceTier,
    _relevance_tier,
)
from storage.sqlite.impression_repository import record_impressions


NOW = datetime(2026, 7, 11, 12, 0, tzinfo=timezone.utc)


def _dark_preferences() -> dict:
    return SimpleRecommendationPreferences(
        media="tv",
        origin="russia",
        mood="dark",
    ).to_candidate_filters()


def _candidate(
    index: int,
    *,
    genres: tuple[str, ...],
    final_score: float,
    title: str | None = None,
    tmdb_id: int | None = None,
) -> dict:
    return {
        "title": title or f"Candidate {index:03d}",
        "year": 2018 + index % 8,
        "media_type": "tv",
        "tmdb_id": tmdb_id if tmdb_id is not None else 50_000 + index,
        "final_score": final_score,
        "quality_score": max(0.0, final_score - 0.04),
        "tmdb_score": 6.0 + final_score * 3.0,
        "tmdb_votes": 100 + index,
        "tmdb_popularity": 10.0 + index,
        "country_codes": ["RU"],
        "countries": ["RU"],
        "genre_keys": list(genres),
        "genres": list(genres),
        "description": "Complete overview",
        "poster_path": f"/candidate-{index}.jpg",
    }


def _service(pool: dict[str, dict], db_path) -> RecommendationDeckService:
    return RecommendationDeckService(pool_loader=lambda: pool, db_path=db_path)


def _tmdb_identities(items: list[dict]) -> list[tuple[str, int]]:
    identities = [candidate_tmdb_identity(item) for item in items]
    assert all(identity is not None for identity in identities)
    return [identity for identity in identities if identity is not None]


def test_ru_dark_intent_is_available_to_local_relevance_ranking(tmp_path) -> None:
    preferences = _dark_preferences()
    exact = _candidate(1, genres=("crime",), final_score=0.51, title="Exact dark crime")
    adjacent = _candidate(2, genres=("drama",), final_score=0.62, title="Adjacent dark drama")
    exploratory = _candidate(3, genres=("history",), final_score=0.81, title="Exploratory history")
    catalog = _candidate(4, genres=("comedy",), final_score=0.99, title="High quality comedy")
    pool = {item["title"]: item for item in (exact, adjacent, exploratory, catalog)}

    assert _relevance_tier(exact, preferences) is RelevanceTier.A
    assert _relevance_tier(adjacent, preferences) is RelevanceTier.B
    assert _relevance_tier(exploratory, preferences) is RelevanceTier.C
    assert _relevance_tier(catalog, preferences) is RelevanceTier.D

    deck = _service(pool, tmp_path / "dark-ranking.sqlite3").build_deck(
        preferences,
        NOW,
        limit_active=2,
        reserve_size=10,
    )

    assert [item["title"] for item in deck["active"]] == [
        "Exact dark crime",
        "Adjacent dark drama",
    ]
    assert all(
        item["title"] != "High quality comedy"
        for item in deck["active"] + deck["reserve"]
    )


def test_diversity_stays_inside_tier_and_exploration_is_capped(tmp_path) -> None:
    preferences = _dark_preferences()
    candidates = [
        *[
            _candidate(index, genres=("crime",), final_score=0.40 + index / 100)
            for index in range(1, 4)
        ],
        *[
            _candidate(index, genres=("drama",), final_score=0.50 + index / 100)
            for index in range(10, 13)
        ],
        *[
            _candidate(index, genres=("history",), final_score=0.70 + index / 1000)
            for index in range(20, 28)
        ],
        *[
            _candidate(index, genres=("comedy",), final_score=0.90 + index / 1000)
            for index in range(30, 36)
        ],
    ]
    pool = {item["title"]: item for item in candidates}

    deck = _service(pool, tmp_path / "tier-diversity.sqlite3").build_deck(
        preferences,
        NOW,
        limit_active=10,
        reserve_size=30,
    )
    active_tiers = [_relevance_tier(item, preferences) for item in deck["active"]]
    tier_order = {
        RelevanceTier.A: 0,
        RelevanceTier.B: 1,
        RelevanceTier.C: 2,
        RelevanceTier.D: 3,
    }

    assert active_tiers == sorted(active_tiers, key=tier_order.__getitem__)
    assert active_tiers.count(RelevanceTier.C) == 1
    assert RelevanceTier.D not in active_tiers
    assert len(deck["active"]) == 7
    assert deck["underfilled_reason"] == "active_underfilled"


def test_tier_a_action_promotes_tier_a_before_closer_quality_tier_b(tmp_path) -> None:
    preferences = _dark_preferences()
    tier_a = [
        _candidate(1, genres=("crime",), final_score=0.95, title="A 0.95"),
        _candidate(2, genres=("crime",), final_score=0.90, title="A 0.90"),
        _candidate(3, genres=("crime",), final_score=0.85, title="A removed"),
        _candidate(4, genres=("crime",), final_score=0.40, title="A reserve"),
    ]
    closer_tier_b = _candidate(
        5,
        genres=("drama",),
        final_score=0.84,
        title="B closer quality",
    )
    pool = {item["title"]: item for item in (*tier_a, closer_tier_b)}
    service = _service(pool, tmp_path / "tier-replacement.sqlite3")
    deck = service.build_deck(preferences, NOW, limit_active=3, reserve_size=10)
    removed = next(item for item in deck["active"] if item["title"] == "A removed")

    updated = service.apply_action_and_refill(deck["deck_id"], removed, "hidden")

    active_titles = {item["title"] for item in updated["active"]}
    assert "A reserve" in active_titles
    assert "B closer quality" not in active_titles
    assert all(
        _relevance_tier(item, preferences) is RelevanceTier.A
        for item in updated["active"]
    )


def test_large_general_pool_does_not_hide_small_relevant_reserve_after_13_watched(tmp_path) -> None:
    db_path = tmp_path / "watched-exhaustion.sqlite3"
    preferences = _dark_preferences()
    watched = [
        _candidate(
            index,
            genres=("crime",),
            final_score=0.80 - index / 1000,
            title=f"Watched {index}",
        )
        for index in range(1, 14)
    ]
    relevant = [
        *[
            _candidate(100 + index, genres=("crime",), final_score=0.70 - index / 1000)
            for index in range(5)
        ],
        *[
            _candidate(120 + index, genres=("drama",), final_score=0.66 - index / 1000)
            for index in range(3)
        ],
    ]
    general_catalog = [
        _candidate(
            200 + index,
            genres=(("comedy", "family", "reality")[index % 3],),
            final_score=0.99 - index / 1000,
        )
        for index in range(60)
    ]
    all_candidates = [*watched, *relevant, *general_catalog]
    pool = {item["title"]: item for item in all_candidates}
    for candidate in watched:
        title_state_service.mark_watched(candidate, path=db_path)

    deck = _service(pool, db_path).build_deck(
        preferences,
        NOW,
        limit_active=6,
        reserve_size=20,
    )
    shown = deck["active"] + deck["reserve"]
    watched_ids = set(_tmdb_identities(watched))

    assert len(pool) > 30
    assert len(deck["active"]) == 6
    assert len(deck["reserve"]) == 2
    assert deck["eligible_count"] == 8
    assert deck["refill_needed"] is True
    assert deck["excluded"]["watched"] == 13
    assert not watched_ids.intersection(_tmdb_identities(shown))
    assert all(
        _relevance_tier(item, preferences) in {RelevanceTier.A, RelevanceTier.B}
        for item in shown
    )


def test_top_up_after_pool_mutation_fills_empty_slots_without_state_or_identity_leaks(tmp_path) -> None:
    db_path = tmp_path / "top-up.sqlite3"
    preferences = _dark_preferences()
    initial = [
        _candidate(
            index,
            genres=("crime",),
            final_score=0.90 - index / 100,
            title=f"Initial {index}",
        )
        for index in range(1, 4)
    ]
    pool = {item["title"]: item for item in initial}
    service = _service(pool, db_path)
    deck = service.build_deck(preferences, NOW, limit_active=3, reserve_size=4)
    removed = deck["active"][0]
    after_action = service.apply_action_and_refill(deck["deck_id"], removed, "watched")
    retained_ids = set(_tmdb_identities(after_action["active"]))
    assert len(after_action["active"]) == 2

    exact_new = _candidate(20, genres=("mystery",), final_score=0.72, title="New exact")
    adjacent_new = _candidate(21, genres=("drama",), final_score=0.71, title="New adjacent")
    reserve_new = _candidate(22, genres=("crime",), final_score=0.69, title="New reserve")
    hidden_new = _candidate(23, genres=("crime",), final_score=0.98, title="Hidden new")
    catalog_new = _candidate(24, genres=("comedy",), final_score=0.99, title="Catalog new")
    localized_duplicate = {
        **exact_new,
        "title": "Localized alias of new exact",
        "year": exact_new["year"] + 1,
    }
    pool.update(
        {
            item["title"]: item
            for item in (
                exact_new,
                adjacent_new,
                reserve_new,
                hidden_new,
                catalog_new,
                localized_duplicate,
            )
        }
    )
    title_state_service.hide_candidate(hidden_new, path=db_path)

    topped_up = service.top_up_deck(deck["deck_id"], NOW + timedelta(minutes=1))
    shown = topped_up["active"] + topped_up["reserve"]
    shown_ids = _tmdb_identities(shown)

    assert len(topped_up["active"]) == 3
    assert retained_ids.issubset(set(shown_ids))
    assert candidate_tmdb_identity(removed) not in shown_ids
    assert candidate_tmdb_identity(hidden_new) not in shown_ids
    assert candidate_tmdb_identity(catalog_new) not in shown_ids
    assert len(shown_ids) == len(set(shown_ids))
    assert shown_ids.count(candidate_tmdb_identity(exact_new)) == 1


def test_invalid_localized_alias_does_not_shadow_valid_mandatory_match(tmp_path) -> None:
    preferences = _dark_preferences()
    invalid_alias = {
        **_candidate(30, genres=("crime",), final_score=0.95, tmdb_id=77_777),
        "title": "US alias",
        "country_codes": ["US"],
        "countries": ["US"],
    }
    valid_alias = {
        **_candidate(31, genres=("crime",), final_score=0.70, tmdb_id=77_777),
        "title": "RU canonical",
    }
    pool = {"first-invalid": invalid_alias, "second-valid": valid_alias}

    deck = _service(pool, tmp_path / "alias-filter.sqlite3").build_deck(
        preferences,
        NOW,
        limit_active=2,
        reserve_size=0,
    )

    assert [item["title"] for item in deck["active"]] == ["RU canonical"]


def test_fresh_catalog_tier_d_does_not_block_recent_tier_a_fallback(tmp_path) -> None:
    db_path = tmp_path / "recent-relevance.sqlite3"
    preferences = _dark_preferences()
    recent_exact = _candidate(40, genres=("crime",), final_score=0.70, title="Recent exact")
    fresh_catalog = _candidate(41, genres=("comedy",), final_score=0.99, title="Fresh catalog")
    record_impressions([recent_exact], deck_id="old", shown_at=NOW.isoformat(), path=db_path)

    deck = _service(
        {"recent": recent_exact, "catalog": fresh_catalog},
        db_path,
    ).build_deck(preferences, NOW + timedelta(minutes=1), limit_active=2, reserve_size=0)

    assert [item["title"] for item in deck["active"]] == ["Recent exact"]
    assert deck["recently_seen_reused"] == 1


def test_underfilled_active_requests_refill_even_with_large_unpromotable_reserve(tmp_path) -> None:
    preferences = _dark_preferences()
    known = [
        _candidate(index, genres=("crime",), final_score=0.90 - index / 1000)
        for index in range(1, 25)
    ]
    unknown = [
        {
            **_candidate(100 + index, genres=("crime",), final_score=0.50 - index / 1000),
            "year": NOW.year,
            "tmdb_score": 0,
            "tmdb_votes": 0,
            "tmdb_popularity": 25,
        }
        for index in range(76)
    ]
    pool = {item["title"]: item for item in (*known, *unknown)}
    service = _service(pool, tmp_path / "unpromotable-reserve.sqlite3")
    deck = service.build_deck(preferences, NOW)
    removed = next(item for item in deck["active"] if item["tmdb_score"] > 0)

    updated = service.apply_action_and_refill(deck["deck_id"], removed, "hidden")

    assert len(updated["active"]) == 29
    assert len(updated["reserve"]) == 70
    assert updated["refill_needed"] is True
    assert updated["underfilled_reason"] == "active_underfilled"


def test_quality_precedes_diversity_inside_same_tier(tmp_path) -> None:
    preferences = _dark_preferences()
    lower = _candidate(50, genres=("crime",), final_score=0.80, title="Lower")
    higher = _candidate(51, genres=("crime",), final_score=0.89, title="Higher")

    deck = _service(
        {"lower": lower, "higher": higher},
        tmp_path / "quality-before-diversity.sqlite3",
    ).build_deck(preferences, NOW, limit_active=2, reserve_size=0)

    assert [item["title"] for item in deck["active"]] == ["Higher", "Lower"]


def test_configured_light_genre_extends_instead_of_replacing_mood_profile() -> None:
    preferences = SimpleRecommendationPreferences(mood="light").to_candidate_filters()
    family = _candidate(60, genres=("family",), final_score=0.50)

    assert _relevance_tier(family, preferences) is RelevanceTier.A

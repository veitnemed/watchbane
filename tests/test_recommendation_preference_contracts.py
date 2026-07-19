from candidates.preferences import (
    CandidateDiscoveryPreferences,
    RecommendationVector,
    resolve_diversity_window,
    resolve_exploration_ratio,
    resolve_rarity_weights,
)
from candidates.recommendation_deck_service import RecommendationDeckService
from datetime import datetime, timezone


def test_discovery_and_vector_serialize_independently() -> None:
    discovery = CandidateDiscoveryPreferences(
        preset_id="anime",
        media_type="tv",
        animation_mode="animation_only",
        countries=("jp",),
        include_genres=("Animation",),
        year_min=2020,
    ).normalized()
    vector = RecommendationVector(openness_level=4, rarity_level=3, mood="dark").normalized()

    assert discovery.to_dict()["countries"] == ["JP"]
    assert discovery.to_candidate_filters()["animation_mode"] == "animation_only"
    assert "openness_level" not in discovery.to_dict()
    assert vector.to_dict() == {
        "openness_level": 4,
        "rarity_level": 3,
        "diversity_level": 2,
        "mood": "dark",
    }
    assert "countries" not in vector.to_dict()


def test_vector_resolvers_keep_default_behavior_contract() -> None:
    assert [resolve_exploration_ratio(level) for level in range(5)] == [0.0, 0.1, 0.2, 0.3, 0.4]
    assert resolve_rarity_weights(2) == (1.0, 0.0, 0.0)
    assert resolve_rarity_weights(3) == (0.75, 0.25, 0.0)
    assert resolve_rarity_weights(4) == (0.55, 0.45, 0.0)
    assert resolve_diversity_window(0) == 1
    assert resolve_diversity_window(4) > resolve_diversity_window(2)


def test_legacy_preferences_migrate_once_to_separate_settings(monkeypatch) -> None:
    from desktop.settings import recommendation_preferences as store

    settings = {
        store.SETTINGS_KEY: {
            "media": "movie",
            "collection": "unusual",
            "origin": "russia",
            "mood": "dark",
        }
    }
    monkeypatch.setattr(store.app_settings_store, "load_sqlite_settings_dict", lambda: dict(settings))
    monkeypatch.setattr(store.app_settings_store, "save_sqlite_settings_dict", lambda payload: settings.update(payload))

    discovery, vector = store.load_recommendation_preferences()
    assert discovery.media_type == "movie"
    assert discovery.countries == ("RU",)
    assert vector.rarity_level == 3
    assert vector.mood == "dark"
    assert store.DISCOVERY_SETTINGS_KEY in settings
    assert store.VECTOR_SETTINGS_KEY in settings

    settings.pop(store.SETTINGS_KEY)
    again_discovery, again_vector = store.load_recommendation_preferences()
    assert again_discovery == discovery
    assert again_vector == vector


def test_corrupt_preferences_are_normalized_persisted_and_keep_future_fields(monkeypatch) -> None:
    from desktop.settings import recommendation_preferences as store

    settings = {
        store.DISCOVERY_SETTINGS_KEY: {
            "preset_id": "removed-preset",
            "media_type": "unknown",
            "year_min": 2030,
            "year_max": 1990,
            "include_genres": ["Drama", "Comedy"],
            "exclude_genres": ["Drama"],
            "future_filter": {"keep": True},
        },
        store.VECTOR_SETTINGS_KEY: {
            "openness_level": 999,
            "mood": "unknown",
            "future_vector": "keep",
        },
        "unknown_global_setting": {"keep": True},
    }
    writes = []
    monkeypatch.setattr(store.app_settings_store, "load_sqlite_settings_dict", lambda: dict(settings))
    monkeypatch.setattr(
        store.app_settings_store,
        "save_sqlite_settings_dict",
        lambda payload: writes.append(dict(payload)) or settings.update(payload),
    )
    monkeypatch.setattr(
        RecommendationDeckService,
        "refresh_deck",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("settings repair rebuilt deck")),
    )

    discovery, vector = store.load_recommendation_preferences()

    assert discovery.preset_id == "manual"
    assert discovery.media_type == "both"
    assert (discovery.year_min, discovery.year_max) == (1990, 2030)
    assert discovery.include_genres == ("comedy",)
    assert discovery.exclude_genres == ("drama",)
    assert vector.openness_level == 2
    assert vector.mood == "any"
    assert writes
    assert settings[store.DISCOVERY_SETTINGS_KEY]["future_filter"] == {"keep": True}
    assert settings[store.VECTOR_SETTINGS_KEY]["future_vector"] == "keep"
    assert settings["unknown_global_setting"] == {"keep": True}


def _candidate(index: int, *, score: float = 0.8, hidden: float = 0.5) -> dict:
    return {
        "title": f"Title {index}",
        "year": 2024,
        "media_type": "movie",
        "tmdb_id": 10_000 + index,
        "tmdb_score": 7.5,
        "tmdb_votes": 500,
        "final_score": score,
        "hidden_gem_score": hidden,
        "genre_keys": ["drama"],
        "country_codes": ["US"],
    }


def _service(pool: dict, db_path) -> RecommendationDeckService:
    return RecommendationDeckService(pool_loader=lambda: pool, db_path=db_path)


def test_rarity_vector_changes_runtime_order_without_rewriting_score(tmp_path) -> None:
    hit = _candidate(1, score=0.9, hidden=0.1)
    gem = _candidate(2, score=0.75, hidden=1.0)
    pool = {item["title"]: item for item in (hit, gem)}
    now = datetime(2026, 7, 11, tzinfo=timezone.utc)

    balanced = _service(pool, tmp_path / "balanced.sqlite3").build_deck(
        {}, now, vector=RecommendationVector(rarity_level=2), limit_active=2, reserve_size=0
    )
    hidden = _service(pool, tmp_path / "hidden.sqlite3").build_deck(
        {}, now, vector=RecommendationVector(rarity_level=4), limit_active=2, reserve_size=0
    )

    assert balanced["active"][0]["title"] == "Title 1"
    assert hidden["active"][0]["title"] == "Title 2"
    assert hidden["active"][0]["final_score"] == 0.75


def test_variation_seed_changes_order_not_eligibility(tmp_path) -> None:
    pool = {str(index): _candidate(index) for index in range(20)}
    service = _service(pool, tmp_path / "variation.sqlite3")
    now = datetime(2026, 7, 11, tzinfo=timezone.utc)
    first = service.refresh_deck({}, now, vector=RecommendationVector(), variation_seed=1)
    second = service.refresh_deck({}, now, vector=RecommendationVector(), variation_seed=2)

    first_ids = [item["tmdb_id"] for item in first["active"]]
    second_ids = [item["tmdb_id"] for item in second["active"]]
    first_deck_ids = {item["tmdb_id"] for item in first["active"] + first["reserve"]}
    second_deck_ids = {item["tmdb_id"] for item in second["active"] + second["reserve"]}
    assert first_deck_ids == second_deck_ids
    assert first_ids != second_ids
    assert first["candidate_filters"] == second["candidate_filters"] == {}

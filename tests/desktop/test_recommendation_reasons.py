from __future__ import annotations

from desktop.candidates import presenters


def _keys(monkeypatch, candidate: dict, filters: dict, vector: dict) -> list[str]:
    monkeypatch.setattr(
        presenters,
        "tr",
        lambda key, **kwargs: key + (":" + str(next(iter(kwargs.values()))) if kwargs else ""),
    )
    return presenters.build_recommendation_reasons(
        candidate,
        filters,
        vector,
        current_year=2026,
    )


def test_reasons_only_claim_matching_country_genre_media_and_year(monkeypatch) -> None:
    candidate = {
        "title": "Truthful",
        "year": 2024,
        "media_type": "movie",
        "country_codes": ["US"],
        "genre_keys": ["drama", "animation"],
        "tmdb_score": 8.0,
        "tmdb_votes": 1000,
        "tmdb_popularity": 60,
    }
    reasons = _keys(
        monkeypatch,
        candidate,
        {
            "country": ["US"],
            "include_genres": ["drama"],
            "media_type": "movie",
            "year_min": 2020,
            "year_max": 2025,
        },
        {"mood": "drama", "rarity_level": 0},
    )

    assert reasons == [
        "recommendations.reason.country_match",
        "recommendations.reason.genre_match:drama",
        "recommendations.reason.media_movie",
    ]
    assert len(reasons) == len(set(reasons))


def test_reasons_do_not_invent_mismatched_filter_or_rarity_claim(monkeypatch) -> None:
    candidate = {
        "title": "Contradiction guard",
        "year": 2010,
        "media_type": "movie",
        "country_codes": ["US"],
        "genre_keys": ["drama"],
        "tmdb_popularity": 100,
    }
    reasons = _keys(
        monkeypatch,
        candidate,
        {
            "country": ["RU"],
            "include_genres": ["comedy"],
            "media_type": "tv",
            "year_min": 2020,
        },
        {"mood": "light", "rarity_level": 4},
    )

    assert reasons == ["recommendations.reason.local_fallback"]


def test_popular_and_rare_reasons_follow_vector_and_metadata(monkeypatch) -> None:
    popular = _keys(
        monkeypatch,
        {"title": "Hit", "year": 2010, "tmdb_popularity": 80},
        {},
        {"rarity_level": 0},
    )
    rare = _keys(
        monkeypatch,
        {"title": "Niche", "year": 2010, "tmdb_popularity": 8},
        {},
        {"rarity_level": 4},
    )

    assert popular == ["recommendations.reason.popular"]
    assert rare == ["recommendations.reason.rare"]
    assert "recommendations.reason.rare" not in popular
    assert "recommendations.reason.popular" not in rare


def test_reason_output_changes_with_intent_without_stale_values(monkeypatch) -> None:
    candidate = {
        "title": "Mutable intent",
        "year": 2010,
        "genre_keys": ["drama"],
        "tmdb_popularity": 10,
    }
    first = _keys(monkeypatch, candidate, {}, {"mood": "drama", "rarity_level": 2})
    second = _keys(monkeypatch, candidate, {}, {"mood": "light", "rarity_level": 4})

    assert first == ["recommendations.reason.mood_match:drama"]
    assert second == ["recommendations.reason.rare"]

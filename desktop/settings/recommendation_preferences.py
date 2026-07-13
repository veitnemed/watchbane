"""Persistence adapter for discovery and local recommendation preferences."""

from __future__ import annotations

from candidates.preferences import (
    CandidateDiscoveryPreferences,
    RecommendationVector,
    SimpleRecommendationPreferences,
)
from candidates.preferences.simple import ORIGIN_COUNTRIES
from config import app_settings_store


SETTINGS_KEY = "simple_recommendation_preferences"
DISCOVERY_SETTINGS_KEY = "recommendation_discovery_preferences"
VECTOR_SETTINGS_KEY = "recommendation_vector"


def load_simple_recommendation_preferences() -> SimpleRecommendationPreferences:
    payload = app_settings_store.load_sqlite_settings_dict().get(SETTINGS_KEY)
    return SimpleRecommendationPreferences.from_dict(payload if isinstance(payload, dict) else None)


def save_simple_recommendation_preferences(preferences: SimpleRecommendationPreferences) -> None:
    app_settings_store.save_sqlite_settings_dict({SETTINGS_KEY: preferences.to_dict()})


def _migrate_legacy_preferences(payload: dict | None) -> tuple[CandidateDiscoveryPreferences, RecommendationVector]:
    legacy = SimpleRecommendationPreferences.from_dict(payload)
    discovery = CandidateDiscoveryPreferences(
        media_type=legacy.media,
        release_preference=legacy.collection if legacy.collection in {"new", "classic", "mixed"} else "mixed",
        countries=tuple(ORIGIN_COUNTRIES[legacy.origin]),
    ).normalized()
    vector = RecommendationVector(
        rarity_level=3 if legacy.collection == "unusual" else 2,
        mood=legacy.mood,
    ).normalized()
    return discovery, vector


def load_recommendation_preferences() -> tuple[CandidateDiscoveryPreferences, RecommendationVector]:
    settings = app_settings_store.load_sqlite_settings_dict()
    discovery_payload = settings.get(DISCOVERY_SETTINGS_KEY)
    vector_payload = settings.get(VECTOR_SETTINGS_KEY)
    if isinstance(discovery_payload, dict) and isinstance(vector_payload, dict):
        discovery = CandidateDiscoveryPreferences.from_dict(discovery_payload)
        vector = RecommendationVector.from_dict(vector_payload)
        normalized_discovery = {**discovery_payload, **discovery.to_dict()}
        normalized_vector = {**vector_payload, **vector.to_dict()}
        corrections = {}
        if normalized_discovery != discovery_payload:
            corrections[DISCOVERY_SETTINGS_KEY] = normalized_discovery
        if normalized_vector != vector_payload:
            corrections[VECTOR_SETTINGS_KEY] = normalized_vector
        if corrections:
            app_settings_store.save_sqlite_settings_dict(corrections)
        return discovery, vector
    discovery, vector = _migrate_legacy_preferences(
        settings.get(SETTINGS_KEY) if isinstance(settings.get(SETTINGS_KEY), dict) else None
    )
    save_recommendation_preferences(discovery, vector)
    return discovery, vector


def save_recommendation_preferences(
    discovery: CandidateDiscoveryPreferences,
    vector: RecommendationVector,
) -> None:
    app_settings_store.save_sqlite_settings_dict({
        DISCOVERY_SETTINGS_KEY: discovery.to_dict(),
        VECTOR_SETTINGS_KEY: vector.to_dict(),
    })


def save_discovery_preferences(preferences: CandidateDiscoveryPreferences) -> None:
    app_settings_store.save_sqlite_settings_dict({DISCOVERY_SETTINGS_KEY: preferences.to_dict()})


def save_recommendation_vector(vector: RecommendationVector) -> None:
    app_settings_store.save_sqlite_settings_dict({VECTOR_SETTINGS_KEY: vector.to_dict()})

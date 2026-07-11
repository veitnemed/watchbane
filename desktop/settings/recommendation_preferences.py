"""Persistence adapter for simple recommendation preferences."""

from __future__ import annotations

from candidates.preferences import SimpleRecommendationPreferences
from config import app_settings_store


SETTINGS_KEY = "simple_recommendation_preferences"


def load_simple_recommendation_preferences() -> SimpleRecommendationPreferences:
    payload = app_settings_store.load_sqlite_settings_dict().get(SETTINGS_KEY)
    return SimpleRecommendationPreferences.from_dict(payload if isinstance(payload, dict) else None)


def save_simple_recommendation_preferences(preferences: SimpleRecommendationPreferences) -> None:
    app_settings_store.save_sqlite_settings_dict({SETTINGS_KEY: preferences.to_dict()})

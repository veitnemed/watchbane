"""Simple recommendation preferences mapped to the existing replenish intent."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from candidates.replenish.filter_intent import FilterReplenishIntent


MEDIA_VALUES = frozenset({"both", "movie", "tv"})
COLLECTION_VALUES = frozenset({"mixed", "new", "classic", "unusual"})
ORIGIN_VALUES = frozenset({"any", "russia", "west", "asia"})
MOOD_VALUES = frozenset({"any", "light", "dark", "dynamic", "drama"})

ORIGIN_COUNTRIES = {
    "any": [],
    "russia": ["RU"],
    "west": ["US", "GB", "FR", "DE"],
    "asia": ["JP", "KR"],
}
MOOD_GENRE_GROUPS = {
    "any": [],
    "light": ["comedy"],
    "dark": ["crime", "mystery", "thriller"],
    "dynamic": ["action_adventure"],
    "drama": ["drama"],
}


def _choice(value: Any, allowed: frozenset[str], default: str) -> str:
    text = str(value or "").strip().casefold()
    return text if text in allowed else default


@dataclass(frozen=True)
class SimpleRecommendationPreferences:
    media: str = "both"
    collection: str = "mixed"
    origin: str = "any"
    mood: str = "any"

    def normalized(self) -> "SimpleRecommendationPreferences":
        return SimpleRecommendationPreferences(
            media=_choice(self.media, MEDIA_VALUES, "both"),
            collection=_choice(self.collection, COLLECTION_VALUES, "mixed"),
            origin=_choice(self.origin, ORIGIN_VALUES, "any"),
            mood=_choice(self.mood, MOOD_VALUES, "any"),
        )

    def to_dict(self) -> dict[str, str]:
        return asdict(self.normalized())

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "SimpleRecommendationPreferences":
        source = dict(payload or {})
        allowed = cls.__dataclass_fields__
        return cls(**{key: value for key, value in source.items() if key in allowed}).normalized()

    def to_candidate_filters(self, defaults: dict | None = None) -> dict:
        preferences = self.normalized()
        genre_groups = list(MOOD_GENRE_GROUPS[preferences.mood])
        if preferences.collection == "unusual":
            genre_groups.extend(["mystery", "sci_fi_fantasy"])
        return {
            **dict(defaults or {}),
            "country": list(ORIGIN_COUNTRIES[preferences.origin]),
            "media_type": None if preferences.media == "both" else preferences.media,
            "year_min": None,
            "year_max": None,
            "include_genres": [],
            "exclude_genres": [],
            "min_tmdb_score": None,
            "min_tmdb_votes": None,
            "_recommendation_collection": preferences.collection,
            "_recommendation_origin": preferences.origin,
            "_recommendation_mood": preferences.mood,
            "_recommendation_genre_groups": list(dict.fromkeys(genre_groups)),
        }

    def to_replenish_intent(
        self,
        *,
        data_language: str = "ru",
        target_add_count: int = 30,
    ) -> dict:
        preferences = self.normalized()
        vibe = preferences.mood if preferences.mood in {"light", "dark"} else "mixed"
        release = preferences.collection if preferences.collection in {"new", "classic"} else "mixed"
        genre_groups = list(MOOD_GENRE_GROUPS[preferences.mood])
        if preferences.collection == "unusual":
            genre_groups.extend(["mystery", "sci_fi_fantasy"])
        return FilterReplenishIntent(
            preset_id="manual",
            countries=list(ORIGIN_COUNTRIES[preferences.origin]),
            media_type=preferences.media,
            vibe=vibe,
            release_preference=release,
            origin_preference="any",
            genre_groups=genre_groups,
            target_add_count=target_add_count,
            data_language=data_language,
        ).to_dict()

"""Candidate discovery preferences independent from recommendation ranking."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from candidates.models import genre_schema
from candidates.models.country_schema import normalize_country_filter_list
from candidates.onboarding.taste_presets import (
    ANIMATION_MODES,
    MEDIA_TYPES,
    PRESET_MANUAL,
    RELEASE_PREFERENCES,
    get_taste_preset,
)
from candidates.replenish.filter_intent import FilterReplenishIntent


def _choice(value: Any, allowed: frozenset[str], default: str) -> str:
    text = str(value or "").strip()
    return text if text in allowed else default


def _texts(values: Any) -> tuple[str, ...]:
    raw_values = values if isinstance(values, (list, tuple, set)) else (() if values in (None, "") else (values,))
    result: list[str] = []
    for value in raw_values:
        text = str(value or "").strip()
        if text and text not in result:
            result.append(text)
    return tuple(result)


def _year(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class CandidateDiscoveryPreferences:
    """Serializable hard-filter and TMDb discovery intent."""

    preset_id: str = PRESET_MANUAL
    media_type: str = "both"
    animation_mode: str = "any"
    release_preference: str = "mixed"
    countries: tuple[str, ...] = ()
    include_genres: tuple[str, ...] = ()
    exclude_genres: tuple[str, ...] = ()
    year_min: int | None = None
    year_max: int | None = None
    min_tmdb_score: float | None = None
    min_tmdb_votes: int | None = None
    only_complete: bool = False
    only_unwatched: bool = True
    hide_hidden: bool = False

    def normalized(self) -> "CandidateDiscoveryPreferences":
        preset_id = str(self.preset_id or PRESET_MANUAL).strip()
        if preset_id != PRESET_MANUAL and get_taste_preset(preset_id) is None:
            preset_id = PRESET_MANUAL
        year_min = _year(self.year_min)
        year_max = _year(self.year_max)
        if year_min is not None and year_max is not None and year_min > year_max:
            year_min, year_max = year_max, year_min
        score = None
        if self.min_tmdb_score not in (None, ""):
            try:
                score = max(0.0, min(10.0, float(self.min_tmdb_score)))
            except (TypeError, ValueError):
                score = None
        votes = _year(self.min_tmdb_votes)
        include_genres = genre_schema.normalize_genre_filter_list(_texts(self.include_genres))
        exclude_genres = genre_schema.normalize_genre_filter_list(_texts(self.exclude_genres))
        excluded = set(exclude_genres)
        include_genres = [genre for genre in include_genres if genre not in excluded]
        return CandidateDiscoveryPreferences(
            preset_id=preset_id,
            media_type=_choice(self.media_type, MEDIA_TYPES, "both"),
            animation_mode=_choice(self.animation_mode, ANIMATION_MODES, "any"),
            release_preference=_choice(self.release_preference, RELEASE_PREFERENCES, "mixed"),
            countries=tuple(normalize_country_filter_list(self.countries)[:5]),
            include_genres=tuple(include_genres),
            exclude_genres=tuple(exclude_genres),
            year_min=year_min,
            year_max=year_max,
            min_tmdb_score=score,
            min_tmdb_votes=None if votes is None else max(0, votes),
            only_complete=bool(self.only_complete),
            only_unwatched=bool(self.only_unwatched),
            hide_hidden=bool(self.hide_hidden),
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self.normalized())
        payload["countries"] = list(payload["countries"])
        payload["include_genres"] = list(payload["include_genres"])
        payload["exclude_genres"] = list(payload["exclude_genres"])
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "CandidateDiscoveryPreferences":
        source = dict(payload or {})
        allowed = cls.__dataclass_fields__
        return cls(**{key: value for key, value in source.items() if key in allowed}).normalized()

    @classmethod
    def from_preset(cls, preset_id: str) -> "CandidateDiscoveryPreferences":
        preset = get_taste_preset(preset_id)
        if preset is None:
            return cls()
        return cls(
            preset_id=preset.preset_id,
            media_type=preset.media_type,
            animation_mode=preset.animation_mode,
            release_preference=preset.release_preference,
            countries=preset.countries,
            include_genres=preset.genre_groups,
        ).normalized()

    def to_candidate_filters(self, defaults: dict | None = None) -> dict:
        current = self.normalized()
        return {
            **dict(defaults or {}),
            "country": list(current.countries),
            "media_type": None if current.media_type == "both" else current.media_type,
            "animation_mode": current.animation_mode,
            "year_min": current.year_min,
            "year_max": current.year_max,
            "include_genres": list(current.include_genres),
            "exclude_genres": list(current.exclude_genres),
            "min_tmdb_score": current.min_tmdb_score,
            "min_tmdb_votes": current.min_tmdb_votes,
            "only_complete": current.only_complete,
            "only_unwatched": current.only_unwatched,
            "hide_hidden": current.hide_hidden,
        }

    def to_replenish_intent(
        self,
        *,
        data_language: str = "ru",
        target_add_count: int = 30,
    ) -> dict:
        current = self.normalized()
        return FilterReplenishIntent(
            preset_id=current.preset_id,
            countries=list(current.countries),
            media_type=current.media_type,
            animation_mode=current.animation_mode,
            release_preference=current.release_preference,
            include_genres=list(current.include_genres),
            exclude_genres=list(current.exclude_genres),
            year_min=current.year_min,
            year_max=current.year_max,
            target_add_count=target_add_count,
            data_language=data_language,
        ).to_dict()

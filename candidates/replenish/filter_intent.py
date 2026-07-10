"""Plain filter intent contract for GUI-driven candidate replenish."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from candidates.models.country_schema import normalize_country_filter_list

MEDIA_TYPE_MOVIE = "movie"
MEDIA_TYPE_TV = "tv"
MEDIA_TYPE_BOTH = "both"
MEDIA_TYPES = frozenset({MEDIA_TYPE_MOVIE, MEDIA_TYPE_TV, MEDIA_TYPE_BOTH})

ANIMATION_MODE_ANY = "any"
ANIMATION_MODE_ANIMATION_ONLY = "animation_only"
ANIMATION_MODE_LIVE_ACTION_ONLY = "live_action_only"
ANIMATION_MODES = frozenset({
    ANIMATION_MODE_ANY,
    ANIMATION_MODE_ANIMATION_ONLY,
    ANIMATION_MODE_LIVE_ACTION_ONLY,
})

VIBE_LIGHT = "light"
VIBE_DARK = "dark"
VIBE_MIXED = "mixed"
VIBES = frozenset({VIBE_LIGHT, VIBE_DARK, VIBE_MIXED})

RELEASE_NEW = "new"
RELEASE_CLASSIC = "classic"
RELEASE_MIXED = "mixed"
RELEASE_PREFERENCES = frozenset({RELEASE_NEW, RELEASE_CLASSIC, RELEASE_MIXED})

ORIGIN_DOMESTIC = "domestic"
ORIGIN_FOREIGN = "foreign"
ORIGIN_MIXED = "mixed"
ORIGIN_ANY = "any"
ORIGIN_PREFERENCES = frozenset({ORIGIN_DOMESTIC, ORIGIN_FOREIGN, ORIGIN_MIXED, ORIGIN_ANY})

TARGET_ADD_MIN = 1
TARGET_ADD_MAX = 30
COUNTRY_LIMIT = 5


def _none_if_empty(value: Any) -> Any:
    if isinstance(value, str):
        text = value.strip()
        return text if text else None
    return value


def _choice(value: Any, allowed: frozenset[str], default: str | None) -> str | None:
    normalized = _none_if_empty(value)
    if normalized is None:
        return default
    text = str(normalized).strip()
    return text if text in allowed else default


def _text_list(values: Any) -> list[str]:
    if values in (None, ""):
        return []
    raw_values = values if isinstance(values, (list, tuple, set)) else [values]
    result: list[str] = []
    seen: set[str] = set()
    for raw_value in raw_values:
        text = str(raw_value or "").strip()
        if text == "":
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(text)
    return result


def _normalize_countries(values: Any) -> list[str]:
    return normalize_country_filter_list(values)[:COUNTRY_LIMIT]


def _int_or_none(value: Any) -> int | None:
    value = _none_if_empty(value)
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _clamp_target(value: Any) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = TARGET_ADD_MAX
    return max(TARGET_ADD_MIN, min(TARGET_ADD_MAX, number))


@dataclass
class FilterReplenishIntent:
    """Normalized, JSON-safe intent collected from Candidates filters."""

    preset_id: str | None = None
    countries: list[str] = field(default_factory=list)
    media_type: str | None = MEDIA_TYPE_BOTH
    animation_mode: str = ANIMATION_MODE_ANY
    vibe: str | None = VIBE_MIXED
    release_preference: str | None = RELEASE_MIXED
    origin_preference: str | None = None
    include_genres: list[str] = field(default_factory=list)
    exclude_genres: list[str] = field(default_factory=list)
    genre_groups: list[str] = field(default_factory=list)
    year_min: int | None = None
    year_max: int | None = None
    target_add_count: int = TARGET_ADD_MAX
    ui_language: str = "ru"
    data_language: str = "ru"
    allow_advanced_override: bool = False

    def __post_init__(self) -> None:
        preset_id = _none_if_empty(self.preset_id)
        year_min = _int_or_none(self.year_min)
        year_max = _int_or_none(self.year_max)
        if year_min is not None and year_max is not None and year_min > year_max:
            year_min, year_max = year_max, year_min

        self.preset_id = str(preset_id).strip() if preset_id is not None else None
        self.countries = _normalize_countries(self.countries)
        self.media_type = _choice(self.media_type, MEDIA_TYPES, MEDIA_TYPE_BOTH)
        self.animation_mode = _choice(self.animation_mode, ANIMATION_MODES, ANIMATION_MODE_ANY) or ANIMATION_MODE_ANY
        self.vibe = _choice(self.vibe, VIBES, VIBE_MIXED)
        self.release_preference = _choice(
            self.release_preference,
            RELEASE_PREFERENCES,
            RELEASE_MIXED,
        )
        self.origin_preference = _choice(self.origin_preference, ORIGIN_PREFERENCES, None)
        self.include_genres = _text_list(self.include_genres)
        self.exclude_genres = _text_list(self.exclude_genres)
        self.genre_groups = _text_list(self.genre_groups)
        self.year_min = year_min
        self.year_max = year_max
        self.target_add_count = _clamp_target(self.target_add_count)
        self.ui_language = str(_none_if_empty(self.ui_language) or "ru").strip()
        self.data_language = str(_none_if_empty(self.data_language) or "ru").strip()
        self.allow_advanced_override = bool(self.allow_advanced_override)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe dict with normalized list instances."""
        return {
            "preset_id": self.preset_id,
            "countries": list(self.countries),
            "media_type": self.media_type,
            "animation_mode": self.animation_mode,
            "vibe": self.vibe,
            "release_preference": self.release_preference,
            "origin_preference": self.origin_preference,
            "include_genres": list(self.include_genres),
            "exclude_genres": list(self.exclude_genres),
            "genre_groups": list(self.genre_groups),
            "year_min": self.year_min,
            "year_max": self.year_max,
            "target_add_count": self.target_add_count,
            "ui_language": self.ui_language,
            "data_language": self.data_language,
            "allow_advanced_override": self.allow_advanced_override,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "FilterReplenishIntent":
        """Build intent from a serialized payload."""
        return cls(**dict(payload or {}))

    @classmethod
    def from_filters(
        cls,
        filters: dict[str, Any] | None,
        *,
        preset_id: str | None = None,
        animation_mode: str | None = None,
        vibe: str | None = None,
        release_preference: str | None = None,
        origin_preference: str | None = None,
        genre_groups: list[str] | tuple[str, ...] | None = None,
        target_add_count: int = TARGET_ADD_MAX,
        ui_language: str = "ru",
        data_language: str = "ru",
        allow_advanced_override: bool = False,
    ) -> "FilterReplenishIntent":
        """Translate the current Candidates GUI filter dict into replenish intent."""
        payload = dict(filters or {})
        return cls(
            preset_id=preset_id if preset_id is not None else payload.get("preset_id"),
            countries=payload.get("country") or payload.get("countries") or [],
            media_type=payload.get("media_type"),
            animation_mode=animation_mode if animation_mode is not None else payload.get("animation_mode"),
            vibe=vibe if vibe is not None else payload.get("vibe"),
            release_preference=(
                release_preference if release_preference is not None else payload.get("release_preference")
            ),
            origin_preference=origin_preference if origin_preference is not None else payload.get("origin_preference"),
            include_genres=payload.get("include_genres") or [],
            exclude_genres=payload.get("exclude_genres") or [],
            genre_groups=genre_groups if genre_groups is not None else payload.get("genre_groups") or [],
            year_min=payload.get("year_min"),
            year_max=payload.get("year_max"),
            target_add_count=payload.get("target_add_count", target_add_count),
            ui_language=payload.get("ui_language", ui_language),
            data_language=payload.get("data_language", data_language),
            allow_advanced_override=payload.get("allow_advanced_override", allow_advanced_override),
        )

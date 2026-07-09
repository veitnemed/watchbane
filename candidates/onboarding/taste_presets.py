"""Serializable onboarding taste preset contract."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from candidates.onboarding.autofill import (
    COUNTRY_SELECTION_MODE_CUSTOM,
    DEFAULT_HOME_COUNTRY,
    INCLUDE_GENRE_MODE_OR,
    MAX_MANUAL_COUNTRIES,
    country_selection_for_manual,
)

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

RELEASE_CLASSIC = "classic"
RELEASE_NEW = "new"
RELEASE_MIXED = "mixed"
RELEASE_PREFERENCES = frozenset({RELEASE_CLASSIC, RELEASE_NEW, RELEASE_MIXED})

GENRE_GROUP_ACTION_ADVENTURE = "action_adventure"
GENRE_GROUP_ADVENTURE = "adventure"
GENRE_GROUP_ANIME = "anime"
GENRE_GROUP_DRAMA = "drama"
GENRE_GROUP_ROMANCE = "romance"
GENRE_GROUP_COMEDY = "comedy"
GENRE_GROUP_CRIME = "crime"
GENRE_GROUP_DETECTIVE = "detective"
GENRE_GROUP_FAMILY = "family"
GENRE_GROUP_FANTASY = "fantasy"
GENRE_GROUP_HORROR = "horror"
GENRE_GROUP_MYSTERY = "mystery"
GENRE_GROUP_THRILLER = "thriller"
GENRE_GROUPS = frozenset({
    GENRE_GROUP_ACTION_ADVENTURE,
    GENRE_GROUP_ADVENTURE,
    GENRE_GROUP_ANIME,
    GENRE_GROUP_DRAMA,
    GENRE_GROUP_ROMANCE,
    GENRE_GROUP_COMEDY,
    GENRE_GROUP_CRIME,
    GENRE_GROUP_DETECTIVE,
    GENRE_GROUP_FAMILY,
    GENRE_GROUP_FANTASY,
    GENRE_GROUP_HORROR,
    GENRE_GROUP_MYSTERY,
    GENRE_GROUP_THRILLER,
})

PRESET_HOLLYWOOD_MAINSTREAM = "hollywood_mainstream"
PRESET_RUSSIAN_MAINSTREAM = "russian_mainstream"
PRESET_ANIME = "anime"
PRESET_K_DRAMA = "k_drama"
PRESET_TURKISH_DRAMAS = "turkish_dramas"
PRESET_BRITISH_EUROPEAN_DETECTIVE = "british_european_detective"
PRESET_FAMILY_ANIMATION = "family_animation"
PRESET_DARK_THRILLER_CRIME = "dark_thriller_crime"
PRESET_MANUAL = "manual"


def normalize_country_codes(
    countries: list[str] | tuple[str, ...] | None,
    *,
    home_country: str = DEFAULT_HOME_COUNTRY,
    max_countries: int = MAX_MANUAL_COUNTRIES,
) -> tuple[str, ...]:
    """Normalize manual country codes with the current onboarding cap."""
    limit = max(1, min(MAX_MANUAL_COUNTRIES, int(max_countries or MAX_MANUAL_COUNTRIES)))
    normalized: list[str] = []
    for value in countries or ():
        code = str(value or "").strip().upper()
        if len(code) == 2 and code.isascii() and code.isalpha() and code not in normalized:
            normalized.append(code)
        if len(normalized) >= limit:
            break
    if normalized:
        return tuple(normalized)

    fallback = str(home_country or DEFAULT_HOME_COUNTRY).strip().upper()
    if len(fallback) == 2 and fallback.isascii() and fallback.isalpha():
        return (fallback,)
    return (DEFAULT_HOME_COUNTRY,)


def _choice(value: Any, allowed: frozenset[str], default: str) -> str:
    text = str(value or "").strip()
    return text if text in allowed else default


def _normalize_genre_groups(values: tuple[str, ...] | list[str] | None) -> tuple[str, ...]:
    result: list[str] = []
    for value in values or ():
        group = str(value or "").strip()
        if group in GENRE_GROUPS and group not in result:
            result.append(group)
    return tuple(result)


@dataclass(frozen=True)
class TastePreset:
    """Small domain contract for onboarding starter-pool taste axes."""

    preset_id: str
    media_type: str = MEDIA_TYPE_BOTH
    animation_mode: str = ANIMATION_MODE_ANY
    countries: tuple[str, ...] = ("US",)
    genre_groups: tuple[str, ...] = ()
    vibe: str = VIBE_MIXED
    release_preference: str = RELEASE_MIXED
    home_country: str = DEFAULT_HOME_COUNTRY

    def normalized(self) -> "TastePreset":
        countries = normalize_country_codes(
            self.countries,
            home_country=self.home_country,
            max_countries=MAX_MANUAL_COUNTRIES,
        )
        return TastePreset(
            preset_id=str(self.preset_id or "").strip() or "manual",
            media_type=_choice(self.media_type, MEDIA_TYPES, MEDIA_TYPE_BOTH),
            animation_mode=_choice(self.animation_mode, ANIMATION_MODES, ANIMATION_MODE_ANY),
            countries=countries,
            genre_groups=_normalize_genre_groups(self.genre_groups),
            vibe=_choice(self.vibe, VIBES, VIBE_MIXED),
            release_preference=_choice(self.release_preference, RELEASE_PREFERENCES, RELEASE_MIXED),
            home_country=normalize_country_codes((self.home_country,), home_country=DEFAULT_HOME_COUNTRY, max_countries=1)[0],
        )

    def as_repository_dict(self) -> dict[str, Any]:
        normalized = self.normalized()
        return asdict(normalized)

    def to_profile_kwargs(self, *, ui_language: str = "en") -> dict[str, Any]:
        """Bridge this contract to current OnboardingTasteProfile constructor args."""
        normalized = self.normalized()
        country_selection = country_selection_for_manual(
            normalized.home_country,
            normalized.countries,
            ratio_preset="50/50",
        ).as_repository_dict()
        country_selection["mode"] = COUNTRY_SELECTION_MODE_CUSTOM
        return {
            "taste_preset": normalized.preset_id,
            "media_preference": normalized.media_type,
            "animation_mode": normalized.animation_mode,
            "release_preference": normalized.release_preference,
            "vibe_preference": normalized.vibe,
            "origin_preference": None,
            "ui_language": ui_language,
            "country_selection": country_selection,
            "include_genres": (),
            "include_genre_mode": INCLUDE_GENRE_MODE_OR,
        }


PRESETS: dict[str, TastePreset] = {
    PRESET_HOLLYWOOD_MAINSTREAM: TastePreset(
        preset_id=PRESET_HOLLYWOOD_MAINSTREAM,
        media_type=MEDIA_TYPE_BOTH,
        animation_mode=ANIMATION_MODE_ANY,
        countries=("US",),
        genre_groups=(GENRE_GROUP_ACTION_ADVENTURE, GENRE_GROUP_COMEDY, GENRE_GROUP_DRAMA),
        vibe=VIBE_MIXED,
        release_preference=RELEASE_MIXED,
        home_country="US",
    ),
    PRESET_RUSSIAN_MAINSTREAM: TastePreset(
        preset_id=PRESET_RUSSIAN_MAINSTREAM,
        media_type=MEDIA_TYPE_BOTH,
        animation_mode=ANIMATION_MODE_ANY,
        countries=("RU",),
        genre_groups=(GENRE_GROUP_DRAMA, GENRE_GROUP_COMEDY, GENRE_GROUP_CRIME),
        vibe=VIBE_MIXED,
        release_preference=RELEASE_MIXED,
        home_country="RU",
    ),
    PRESET_ANIME: TastePreset(
        preset_id=PRESET_ANIME,
        media_type=MEDIA_TYPE_BOTH,
        animation_mode=ANIMATION_MODE_ANIMATION_ONLY,
        countries=("JP",),
        genre_groups=(
            GENRE_GROUP_ACTION_ADVENTURE,
            GENRE_GROUP_FANTASY,
            GENRE_GROUP_DRAMA,
            GENRE_GROUP_ROMANCE,
            GENRE_GROUP_COMEDY,
        ),
        vibe=VIBE_MIXED,
        release_preference=RELEASE_MIXED,
        home_country="US",
    ),
    PRESET_K_DRAMA: TastePreset(
        preset_id=PRESET_K_DRAMA,
        media_type=MEDIA_TYPE_TV,
        animation_mode=ANIMATION_MODE_LIVE_ACTION_ONLY,
        countries=("KR",),
        genre_groups=(
            GENRE_GROUP_DRAMA,
            GENRE_GROUP_ROMANCE,
            GENRE_GROUP_COMEDY,
            GENRE_GROUP_CRIME,
            GENRE_GROUP_THRILLER,
        ),
        vibe=VIBE_MIXED,
        release_preference=RELEASE_MIXED,
        home_country="US",
    ),
    PRESET_TURKISH_DRAMAS: TastePreset(
        preset_id=PRESET_TURKISH_DRAMAS,
        media_type=MEDIA_TYPE_TV,
        animation_mode=ANIMATION_MODE_LIVE_ACTION_ONLY,
        countries=("TR",),
        genre_groups=(GENRE_GROUP_DRAMA, GENRE_GROUP_ROMANCE, GENRE_GROUP_FAMILY),
        vibe=VIBE_MIXED,
        release_preference=RELEASE_MIXED,
        home_country="US",
    ),
    PRESET_BRITISH_EUROPEAN_DETECTIVE: TastePreset(
        preset_id=PRESET_BRITISH_EUROPEAN_DETECTIVE,
        media_type=MEDIA_TYPE_TV,
        animation_mode=ANIMATION_MODE_LIVE_ACTION_ONLY,
        countries=("GB", "FR", "DE", "IT", "ES"),
        genre_groups=(GENRE_GROUP_DETECTIVE, GENRE_GROUP_CRIME, GENRE_GROUP_MYSTERY, GENRE_GROUP_THRILLER),
        vibe=VIBE_DARK,
        release_preference=RELEASE_MIXED,
        home_country="US",
    ),
    PRESET_FAMILY_ANIMATION: TastePreset(
        preset_id=PRESET_FAMILY_ANIMATION,
        media_type=MEDIA_TYPE_BOTH,
        animation_mode=ANIMATION_MODE_ANIMATION_ONLY,
        countries=("US", "JP", "RU"),
        genre_groups=(GENRE_GROUP_FAMILY, GENRE_GROUP_COMEDY, GENRE_GROUP_ADVENTURE, GENRE_GROUP_FANTASY),
        vibe=VIBE_LIGHT,
        release_preference=RELEASE_MIXED,
        home_country="US",
    ),
    PRESET_DARK_THRILLER_CRIME: TastePreset(
        preset_id=PRESET_DARK_THRILLER_CRIME,
        media_type=MEDIA_TYPE_BOTH,
        animation_mode=ANIMATION_MODE_ANY,
        countries=("US", "GB", "KR", "JP", "RU"),
        genre_groups=(GENRE_GROUP_CRIME, GENRE_GROUP_MYSTERY, GENRE_GROUP_THRILLER, GENRE_GROUP_HORROR, GENRE_GROUP_DRAMA),
        vibe=VIBE_MIXED,
        release_preference=RELEASE_MIXED,
        home_country="US",
    ),
}


def get_taste_preset(preset_id: str) -> TastePreset | None:
    preset = PRESETS.get(str(preset_id or "").strip())
    return preset.normalized() if preset is not None else None


def taste_preset_to_profile_payload(
    preset_id: str,
    overrides: dict[str, Any] | None = None,
    *,
    ui_language: str = "en",
) -> dict[str, Any]:
    """Return current onboarding profile payload for a preset key."""
    overrides = dict(overrides or {})
    preset = get_taste_preset(preset_id)
    if preset is None or preset.preset_id == PRESET_MANUAL:
        countries = overrides.pop("countries", None) or overrides.pop("selected_countries", None) or ("US",)
        preset = manual_taste_preset(
            countries,
            media_type=overrides.pop("media_type", MEDIA_TYPE_BOTH),
            animation_mode=overrides.pop("animation_mode", ANIMATION_MODE_ANY),
            genre_groups=overrides.pop("genre_groups", ()),
            vibe=overrides.pop("vibe", VIBE_MIXED),
            release_preference=overrides.pop("release_preference", RELEASE_MIXED),
            home_country=overrides.pop("home_country", DEFAULT_HOME_COUNTRY),
        )
    payload = preset.to_profile_kwargs(ui_language=str(overrides.pop("ui_language", ui_language)))
    payload.update(overrides)
    return payload


def manual_taste_preset(
    countries: list[str] | tuple[str, ...],
    *,
    media_type: str = MEDIA_TYPE_BOTH,
    animation_mode: str = ANIMATION_MODE_ANY,
    genre_groups: tuple[str, ...] | list[str] | None = None,
    vibe: str = VIBE_MIXED,
    release_preference: str = RELEASE_MIXED,
    home_country: str = DEFAULT_HOME_COUNTRY,
) -> TastePreset:
    return TastePreset(
        preset_id="manual",
        media_type=media_type,
        animation_mode=animation_mode,
        countries=tuple(countries),
        genre_groups=tuple(genre_groups or ()),
        vibe=vibe,
        release_preference=release_preference,
        home_country=home_country,
    ).normalized()

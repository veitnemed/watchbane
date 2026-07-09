"""Deterministic TMDb onboarding autofill for the starter candidate pool."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
import json
import math
from pathlib import Path
from typing import Any, Callable, Protocol

from apis import tmdb_api
from candidates.models import country_schema
from candidates.models.genre_schema import build_genre_keys
from candidates.models.keys import COMMON_POOL_CRITERIA_NAME, pool_entry_key, title_identity_key
from candidates.models.schema import compute_completeness, normalize_candidate_record
from candidates.pool.dataset_overlap import build_dataset_title_keys
from candidates.pool.existing_index import build_existing_candidate_index, discover_item_existing_reason
from candidates.pool.watched_cleanup import build_watched_signatures, is_watched_candidate
from storage.sqlite import action_repository
from storage.sqlite.candidate_pool_repository import load_candidate_pool_dict, save_candidate_pool_dict
from storage.sqlite.onboarding_repository import (
    complete_onboarding_profile,
    create_onboarding_profile,
    has_completed_onboarding_profile,
    save_autofill_request_audit,
)


STARTER_POOL_TARGET = 120
STARTER_POOL_MIN_ACCEPTABLE = 80
MAX_TMDB_REQUESTS = 180
RESULTS_PER_TMDB_PAGE = 20

ERA_TOP_ALL_TIME = "top_all_time"
ERA_CLASSIC_SWEEP = "classic_sweep"
ERA_NEW_SWEEP = "new_sweep"

CLASSIC_START_YEAR = 2005
CLASSIC_END_YEAR = 2021
NEW_START_YEAR = 2022

MEDIA_MOVIE = "movie"
MEDIA_TV = "tv"
ORIGIN_ANY = "any"
ORIGIN_DOMESTIC = "domestic"
ORIGIN_FOREIGN = "foreign"
VIBE_LIGHT = "light"
VIBE_DARK = "dark"

COUNTRY_SELECTION_MODE_COUNTRY_PAIR = "country_pair"
COUNTRY_SELECTION_MODE_SINGLE = "single_country"
COUNTRY_SELECTION_MODE_PRESET_FOREIGN = "preset_foreign"
COUNTRY_SELECTION_MODE_PRESET_MIXED = "preset_mixed"
COUNTRY_SELECTION_MODE_CUSTOM = "custom"
DEFAULT_HOME_COUNTRY = "RU"
DEFAULT_FOREIGN_COUNTRIES = ("US", "GB")
DEFAULT_EN_COUNTRIES = ("US", "GB")

MOVIE_LIGHT_GENRES = ("Comedy", "Romance", "Fantasy", "Family", "Adventure")
MOVIE_DARK_GENRES = ("Drama", "Thriller", "Action", "Crime", "Mystery")
TV_LIGHT_GENRES = ("Comedy", "Family", "Animation", "Sci-Fi & Fantasy")
TV_DARK_GENRES = ("Drama", "Crime", "Mystery", "Action & Adventure", "War & Politics")

FOREIGN_LANGUAGE_BUCKETS: tuple[tuple[str, float], ...] = (
    ("en", 0.50),
    ("ko", 0.12),
    ("ja", 0.12),
    ("fr", 0.08),
    ("es", 0.08),
    ("de", 0.05),
    ("it", 0.05),
)

DOMESTIC_FILTER = {
    "with_origin_country": "RU",
    "with_original_language": "ru",
}

FALLBACK_BASE = "base"
FALLBACK_RELAX_ORIGIN = "relax_origin"
FALLBACK_RELAX_GENRES = "relax_genres"
FALLBACK_RELAX_VOTES_MID = "relax_votes_mid"
FALLBACK_RELAX_VOTES_LOW = "relax_votes_low"
FALLBACK_RELAX_ERA = "relax_era"
FALLBACK_POPULAR = "popular"

FALLBACK_ORDER = (
    FALLBACK_BASE,
    FALLBACK_RELAX_ORIGIN,
    FALLBACK_RELAX_GENRES,
    FALLBACK_RELAX_VOTES_MID,
    FALLBACK_RELAX_VOTES_LOW,
    FALLBACK_RELAX_ERA,
    FALLBACK_POPULAR,
)

ProgressCallback = Callable[[dict[str, Any]], None]
CancelChecker = Callable[[], bool]


class TmdbClientProtocol(Protocol):
    def discover(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        ...

    def movie_genres(self, language: str = "en") -> list[dict[str, Any]]:
        ...

    def tv_genres(self, language: str = "en") -> list[dict[str, Any]]:
        ...


class TmdbAutofillClient:
    """Small TMDb adapter kept injectable for tests and workers."""

    def __init__(self, token: str | None = None) -> None:
        self._token = token

    def discover(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        return tmdb_api.tmdb_get(endpoint, params=params, token=self._token)

    def movie_genres(self, language: str = "en") -> list[dict[str, Any]]:
        return tmdb_api.get_movie_genre_list(language=language, token=self._token)

    def tv_genres(self, language: str = "en") -> list[dict[str, Any]]:
        return tmdb_api.get_tv_genre_list(language=language, token=self._token)


def _normalize_country_code(value: Any) -> str:
    code = str(value or "").strip().upper()
    if len(code) == 2 and code.isascii() and code.isalpha():
        return code
    return ""


def _normalize_country_weights(countries: list[str], weights: dict[str, Any] | None) -> dict[str, float]:
    if len(countries) == 0:
        return {}
    raw_weights = weights if isinstance(weights, dict) else {}
    normalized: dict[str, float] = {}
    for country in countries:
        try:
            value = float(raw_weights.get(country, 0.0))
        except (TypeError, ValueError):
            value = 0.0
        normalized[country] = max(0.0, value)
    total = sum(normalized.values())
    if total <= 0:
        equal = 1.0 / len(countries)
        return {country: equal for country in countries}
    return {country: value / total for country, value in normalized.items()}


@dataclass(frozen=True)
class CountrySelection:
    mode: str
    home_country: str
    selected_countries: tuple[str, ...]
    country_weights: dict[str, float]
    exclude_home_country: bool
    max_countries: int = 2
    primary_country: str | None = None
    secondary_country: str | None = None

    def normalized(self) -> "CountrySelection":
        max_countries = max(1, int(self.max_countries or 2))
        home_country = _normalize_country_code(self.home_country) or DEFAULT_HOME_COUNTRY
        countries: list[str] = []
        for value in self.selected_countries or ():
            code = _normalize_country_code(value)
            if code and code not in countries:
                countries.append(code)
            if len(countries) >= max_countries:
                break
        if not countries:
            countries = [home_country]

        weights = _normalize_country_weights(countries, self.country_weights)
        primary = _normalize_country_code(self.primary_country) or countries[0]
        if primary not in countries:
            primary = countries[0]
        secondary = _normalize_country_code(self.secondary_country)
        if secondary not in countries or secondary == primary:
            secondary = next((country for country in countries if country != primary), None)
        mode = str(self.mode or COUNTRY_SELECTION_MODE_COUNTRY_PAIR).strip() or COUNTRY_SELECTION_MODE_COUNTRY_PAIR
        if len(countries) == 1 and mode == COUNTRY_SELECTION_MODE_COUNTRY_PAIR:
            mode = COUNTRY_SELECTION_MODE_SINGLE
        return CountrySelection(
            mode=mode,
            home_country=home_country,
            selected_countries=tuple(countries),
            country_weights=weights,
            exclude_home_country=bool(self.exclude_home_country),
            max_countries=max_countries,
            primary_country=primary,
            secondary_country=secondary,
        )

    def as_repository_dict(self) -> dict[str, Any]:
        normalized = self.normalized()
        return {
            "mode": normalized.mode,
            "home_country": normalized.home_country,
            "selected_countries": list(normalized.selected_countries),
            "country_weights": dict(normalized.country_weights),
            "exclude_home_country": normalized.exclude_home_country,
            "max_countries": normalized.max_countries,
            "primary_country": normalized.primary_country,
            "secondary_country": normalized.secondary_country,
        }


def country_selection_for_foreign_ru() -> CountrySelection:
    return CountrySelection(
        mode=COUNTRY_SELECTION_MODE_PRESET_FOREIGN,
        home_country=DEFAULT_HOME_COUNTRY,
        selected_countries=DEFAULT_FOREIGN_COUNTRIES,
        country_weights={"US": 0.90, "GB": 0.10},
        exclude_home_country=True,
        primary_country="US",
        secondary_country="GB",
    ).normalized()


def country_selection_for_mixed_ru() -> CountrySelection:
    return CountrySelection(
        mode=COUNTRY_SELECTION_MODE_PRESET_MIXED,
        home_country=DEFAULT_HOME_COUNTRY,
        selected_countries=("RU", "US"),
        country_weights={"RU": 0.15, "US": 0.85},
        exclude_home_country=False,
        primary_country="RU",
        secondary_country="US",
    ).normalized()


def country_selection_for_single(country: str, *, home_country: str = DEFAULT_HOME_COUNTRY) -> CountrySelection:
    code = _normalize_country_code(country) or _normalize_country_code(home_country) or DEFAULT_HOME_COUNTRY
    return CountrySelection(
        mode=COUNTRY_SELECTION_MODE_SINGLE,
        home_country=home_country,
        selected_countries=(code,),
        country_weights={code: 1.0},
        exclude_home_country=False,
        max_countries=1,
        primary_country=code,
    ).normalized()


def country_selection_for_manual(
    home_country: str,
    countries: list[str] | tuple[str, ...],
    *,
    ratio_preset: str = "70/30",
) -> CountrySelection:
    normalized_countries: list[str] = []
    for value in countries:
        code = _normalize_country_code(value)
        if code and code not in normalized_countries:
            normalized_countries.append(code)
        if len(normalized_countries) >= 2:
            break
    if len(normalized_countries) == 0:
        return country_selection_for_single(home_country, home_country=home_country)
    if len(normalized_countries) == 1:
        return country_selection_for_single(normalized_countries[0], home_country=home_country)

    preset = str(ratio_preset or "70/30").strip()
    if preset == "90/10":
        weights = {normalized_countries[0]: 0.90, normalized_countries[1]: 0.10}
    elif preset == "50/50":
        weights = {normalized_countries[0]: 0.50, normalized_countries[1]: 0.50}
    else:
        weights = {normalized_countries[0]: 0.70, normalized_countries[1]: 0.30}
    return CountrySelection(
        mode=COUNTRY_SELECTION_MODE_COUNTRY_PAIR,
        home_country=home_country,
        selected_countries=tuple(normalized_countries),
        country_weights=weights,
        exclude_home_country=False,
        primary_country=normalized_countries[0],
        secondary_country=normalized_countries[1],
    ).normalized()


def build_country_plan(selection: CountrySelection, pool_size: int) -> dict[str, int]:
    normalized = selection.normalized()
    countries = list(normalized.selected_countries)
    raw = {
        country: int(pool_size) * float(normalized.country_weights.get(country, 0.0))
        for country in countries
    }
    floors = {country: int(value) for country, value in raw.items()}
    remainder = int(pool_size) - sum(floors.values())
    primary = normalized.primary_country or (countries[0] if countries else None)
    if remainder > 0 and primary in floors:
        floors[primary] += remainder
    return floors


def _coerce_country_selection(value: Any, *, ui_language: str, origin_preference: str | None) -> CountrySelection:
    if isinstance(value, CountrySelection):
        return value.normalized()
    if isinstance(value, dict):
        selected = value.get("selected_countries") or value.get("countries") or ()
        if isinstance(selected, str):
            selected = [part.strip() for part in selected.replace(",", " ").split()]
        return CountrySelection(
            mode=value.get("mode") or COUNTRY_SELECTION_MODE_CUSTOM,
            home_country=value.get("home_country") or DEFAULT_HOME_COUNTRY,
            selected_countries=tuple(selected),
            country_weights=value.get("country_weights") or {},
            exclude_home_country=bool(value.get("exclude_home_country")),
            max_countries=int(value.get("max_countries") or 2),
            primary_country=value.get("primary_country"),
            secondary_country=value.get("secondary_country"),
        ).normalized()

    language = str(ui_language or "").strip().casefold()
    if language == "ru":
        if origin_preference == "foreign":
            return country_selection_for_foreign_ru()
        if origin_preference == "domestic":
            return country_selection_for_single(DEFAULT_HOME_COUNTRY)
        return country_selection_for_mixed_ru()
    return CountrySelection(
        mode=COUNTRY_SELECTION_MODE_COUNTRY_PAIR,
        home_country="US",
        selected_countries=DEFAULT_EN_COUNTRIES,
        country_weights={"US": 0.90, "GB": 0.10},
        exclude_home_country=False,
        primary_country="US",
        secondary_country="GB",
    ).normalized()


@dataclass(frozen=True)
class OnboardingTasteProfile:
    media_preference: str
    release_preference: str
    vibe_preference: str
    origin_preference: str | None
    ui_language: str
    country_selection: CountrySelection | dict[str, Any] | None = None

    def normalized(self) -> "OnboardingTasteProfile":
        ui_language = str(self.ui_language or "ru").strip().casefold() or "ru"
        media_preference = _choice(self.media_preference, {"movie", "tv", "both"}, "both")
        release_preference = _choice(self.release_preference, {"classic", "new", "mixed"}, "mixed")
        vibe_preference = _choice(self.vibe_preference, {"light", "dark", "mixed"}, "mixed")
        origin_preference = self.origin_preference
        if ui_language != "ru":
            origin_preference = None
        else:
            origin_preference = _choice(origin_preference, {"foreign", "domestic", "mixed"}, "mixed")
        country_selection = _coerce_country_selection(
            self.country_selection,
            ui_language=ui_language,
            origin_preference=origin_preference,
        )
        return OnboardingTasteProfile(
            media_preference=media_preference,
            release_preference=release_preference,
            vibe_preference=vibe_preference,
            origin_preference=origin_preference,
            ui_language=ui_language,
            country_selection=country_selection,
        )

    def as_repository_dict(self) -> dict[str, Any]:
        normalized = self.normalized()
        data = asdict(normalized)
        selection = normalized.country_selection
        if isinstance(selection, CountrySelection):
            data["country_selection"] = selection.as_repository_dict()
        return data


@dataclass(frozen=True)
class CandidateFetchBucket:
    media_type: str
    era: str
    vibe: str
    origin: str
    original_language: str | None
    quota: int
    quota_weight: float
    target_country: str | None = None
    target_country_weight: float = 0.0
    home_country: str = DEFAULT_HOME_COUNTRY
    exclude_home_country: bool = False
    genre_ids: tuple[int, ...] = ()

    @property
    def bucket_id(self) -> str:
        language = self.original_language or "any"
        country = self.target_country or "any"
        return f"{country}:{self.media_type}:{self.era}:{self.vibe}:{self.origin}:{language}"


@dataclass
class _BucketState:
    bucket: CandidateFetchBucket
    filled: int = 0
    request_index: int = 0
    exhausted: bool = False


@dataclass(frozen=True)
class AutofillResult:
    ok: bool
    profile_id: int
    created_count: int
    pool_size: int
    api_requests: int
    cancelled: bool
    warning: str | None
    candidates: list[dict[str, Any]]
    warnings: list[str]
    planned_counts: dict[str, dict[str, int]]
    actual_counts: dict[str, dict[str, int]]
    rejected_future_count: int = 0
    duplicate_requests_skipped: int = 0


def _choice(value: Any, allowed: set[str], default: str) -> str:
    text = str(value or "").strip().casefold()
    return text if text in allowed else default


def media_weights(media_preference: str) -> dict[str, float]:
    if media_preference == "movie":
        return {MEDIA_MOVIE: 0.70, MEDIA_TV: 0.30}
    if media_preference == "tv":
        return {MEDIA_MOVIE: 0.30, MEDIA_TV: 0.70}
    return {MEDIA_MOVIE: 0.50, MEDIA_TV: 0.50}


def release_weights(release_preference: str) -> dict[str, float]:
    if release_preference == "classic":
        return {ERA_TOP_ALL_TIME: 0.40, ERA_CLASSIC_SWEEP: 0.60}
    if release_preference == "new":
        return {ERA_TOP_ALL_TIME: 0.30, ERA_NEW_SWEEP: 0.70}
    return {ERA_TOP_ALL_TIME: 0.40, ERA_CLASSIC_SWEEP: 0.30, ERA_NEW_SWEEP: 0.30}


def vibe_weights(vibe_preference: str) -> dict[str, float]:
    if vibe_preference == "light":
        return {VIBE_LIGHT: 0.70, VIBE_DARK: 0.30}
    if vibe_preference == "dark":
        return {VIBE_LIGHT: 0.30, VIBE_DARK: 0.70}
    return {VIBE_LIGHT: 0.50, VIBE_DARK: 0.50}


def origin_weights(origin_preference: str | None, *, ui_language: str) -> dict[str, float]:
    if str(ui_language or "").strip().casefold() != "ru":
        return {ORIGIN_ANY: 1.0}
    if origin_preference == "domestic":
        return {ORIGIN_DOMESTIC: 0.70, ORIGIN_FOREIGN: 0.30}
    if origin_preference == "foreign":
        return {ORIGIN_DOMESTIC: 0.30, ORIGIN_FOREIGN: 0.70}
    return {ORIGIN_DOMESTIC: 0.50, ORIGIN_FOREIGN: 0.50}


def stable_bucket_key(bucket: CandidateFetchBucket | tuple[Any, ...]) -> str:
    if isinstance(bucket, CandidateFetchBucket):
        return bucket.bucket_id
    return ":".join(str(part) for part in bucket)


def allocate_integer_quotas(raw_quotas: dict[Any, float], total: int) -> dict[Any, int]:
    floors = {key: int(value) for key, value in raw_quotas.items()}
    remainder = int(total) - sum(floors.values())
    if remainder <= 0:
        return floors

    fractions = sorted(
        raw_quotas.items(),
        key=lambda item: (item[1] - int(item[1]), stable_bucket_key(item[0])),
        reverse=True,
    )
    for bucket, _ in fractions[:remainder]:
        floors[bucket] += 1
    return floors


def _allocate_weighted(weights: dict[Any, float], total: int) -> dict[Any, int]:
    raw = {key: int(total) * float(weight) for key, weight in weights.items()}
    return allocate_integer_quotas(raw, int(total))


def _dimension_targets(
    profile: OnboardingTasteProfile,
    *,
    target: int,
) -> dict[str, dict[Any, int]]:
    profile = profile.normalized()
    media = media_weights(profile.media_preference)
    era = release_weights(profile.release_preference)
    vibe = vibe_weights(profile.vibe_preference)
    origin = origin_weights(profile.origin_preference, ui_language=profile.ui_language)
    targets = {
        "media_type": _allocate_weighted(media, target),
        "era": _allocate_weighted(era, target),
        "vibe": _allocate_weighted(vibe, target),
        "origin": _allocate_weighted(origin, target),
        "original_language": {},
    }
    foreign_quota = targets["origin"].get(ORIGIN_FOREIGN, 0)
    if foreign_quota:
        targets["original_language"] = _allocate_weighted(dict(FOREIGN_LANGUAGE_BUCKETS), foreign_quota)
    return targets


def _bucket_key_value(key: tuple[str, str, str, str, str | None], dimension: str) -> Any:
    media_type, era_name, vibe_name, origin_name, language = key
    if dimension == "media_type":
        return media_type
    if dimension == "era":
        return era_name
    if dimension == "vibe":
        return vibe_name
    if dimension == "origin":
        return origin_name
    if dimension == "original_language":
        return language
    raise KeyError(dimension)


def _allocate_bucket_quotas(
    raw_quotas: dict[tuple[str, str, str, str, str | None], float],
    *,
    profile: OnboardingTasteProfile,
    target: int,
) -> dict[tuple[str, str, str, str, str | None], int]:
    quotas = {key: int(value) for key, value in raw_quotas.items()}
    targets = _dimension_targets(profile, target=target)
    current = {
        "media_type": Counter(),
        "era": Counter(),
        "vibe": Counter(),
        "origin": Counter(),
        "original_language": Counter(),
    }
    for key, quota in quotas.items():
        if quota <= 0:
            continue
        for dimension in ("media_type", "era", "vibe", "origin", "original_language"):
            value = _bucket_key_value(key, dimension)
            if value is not None:
                current[dimension][value] += quota

    ranked_keys = sorted(
        raw_quotas,
        key=lambda key: (raw_quotas[key] - int(raw_quotas[key]), stable_bucket_key(key)),
        reverse=True,
    )

    def can_add(key: tuple[str, str, str, str, str | None], *, enforce_language: bool) -> bool:
        for dimension in ("media_type", "era", "vibe", "origin"):
            value = _bucket_key_value(key, dimension)
            if current[dimension][value] >= targets[dimension].get(value, 0):
                return False
        language = _bucket_key_value(key, "original_language")
        if enforce_language and language is not None:
            if current["original_language"][language] >= targets["original_language"].get(language, 0):
                return False
        return True

    remaining = int(target) - sum(quotas.values())
    while remaining > 0:
        selected = None
        for key in ranked_keys:
            if can_add(key, enforce_language=True):
                selected = key
                break
        if selected is None:
            for key in ranked_keys:
                if can_add(key, enforce_language=False):
                    selected = key
                    break
        if selected is None:
            selected = ranked_keys[0]

        quotas[selected] += 1
        for dimension in ("media_type", "era", "vibe", "origin", "original_language"):
            value = _bucket_key_value(selected, dimension)
            if value is not None:
                current[dimension][value] += 1
        remaining -= 1
    return quotas


def _allocate_country_bucket_quotas(
    raw_quotas: dict[tuple[str, str, str, str], float],
    *,
    country_plan: dict[str, int],
    media_targets: dict[str, int],
    era_targets: dict[str, int],
    vibe_targets: dict[str, int],
    target: int,
) -> dict[tuple[str, str, str, str], int]:
    quotas = {key: int(value) for key, value in raw_quotas.items()}
    current = {
        "country": Counter(),
        "media_type": Counter(),
        "era": Counter(),
        "vibe": Counter(),
    }
    for key, quota in quotas.items():
        if quota <= 0:
            continue
        country, media_type, era_name, vibe_name = key
        current["country"][country] += quota
        current["media_type"][media_type] += quota
        current["era"][era_name] += quota
        current["vibe"][vibe_name] += quota

    ranked_keys = sorted(
        raw_quotas,
        key=lambda key: (raw_quotas[key] - int(raw_quotas[key]), stable_bucket_key(key)),
        reverse=True,
    )
    targets = {
        "country": country_plan,
        "media_type": media_targets,
        "era": era_targets,
        "vibe": vibe_targets,
    }

    def can_add(key: tuple[str, str, str, str], dimensions: tuple[str, ...]) -> bool:
        country, media_type, era_name, vibe_name = key
        values = {
            "country": country,
            "media_type": media_type,
            "era": era_name,
            "vibe": vibe_name,
        }
        for dimension in dimensions:
            value = values[dimension]
            if current[dimension][value] >= int(targets[dimension].get(value, 0)):
                return False
        return True

    remaining = int(target) - sum(quotas.values())
    while remaining > 0 and ranked_keys:
        selected = None
        for dimensions in (
            ("country", "media_type", "era", "vibe"),
            ("country", "media_type", "vibe"),
            ("country", "media_type"),
            ("country",),
        ):
            for key in ranked_keys:
                if can_add(key, dimensions):
                    selected = key
                    break
            if selected is not None:
                break
        if selected is None:
            selected = ranked_keys[0]

        quotas[selected] += 1
        country, media_type, era_name, vibe_name = selected
        current["country"][country] += 1
        current["media_type"][media_type] += 1
        current["era"][era_name] += 1
        current["vibe"][vibe_name] += 1
        remaining -= 1
    return quotas


def _current_year() -> int:
    return datetime.now(timezone.utc).year


def _current_date() -> date:
    return datetime.now(timezone.utc).date()


def _parse_iso_date(value: Any) -> date | None:
    text = str(value or "").strip()
    if len(text) < 10:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _date_lte_field(media_type: str) -> str:
    return "primary_release_date.lte" if media_type == MEDIA_MOVIE else "first_air_date.lte"


def _genre_name_map(items: list[dict[str, Any]]) -> dict[str, int]:
    result: dict[str, int] = {}
    for item in items:
        name = str(item.get("name") or "").strip()
        genre_id = item.get("id")
        if name == "" or genre_id in (None, ""):
            continue
        result[name.casefold()] = int(genre_id)
    return result


def _ids_for_names(mapping: dict[str, int], names: tuple[str, ...]) -> tuple[int, ...]:
    ids: list[int] = []
    for name in names:
        genre_id = mapping.get(name.casefold())
        if genre_id is not None:
            ids.append(genre_id)
    return tuple(ids)


def resolve_tmdb_genre_ids(client: TmdbClientProtocol) -> dict[str, dict[str, tuple[int, ...]]]:
    movie_genres = _genre_name_map(client.movie_genres(language="en"))
    tv_genres = _genre_name_map(client.tv_genres(language="en"))
    return {
        MEDIA_MOVIE: {
            VIBE_LIGHT: _ids_for_names(movie_genres, MOVIE_LIGHT_GENRES),
            VIBE_DARK: _ids_for_names(movie_genres, MOVIE_DARK_GENRES),
        },
        MEDIA_TV: {
            VIBE_LIGHT: _ids_for_names(tv_genres, TV_LIGHT_GENRES),
            VIBE_DARK: _ids_for_names(tv_genres, TV_DARK_GENRES),
        },
    }


def build_fetch_buckets(
    profile: OnboardingTasteProfile,
    *,
    genre_ids: dict[str, dict[str, tuple[int, ...]]] | None = None,
    target: int = STARTER_POOL_TARGET,
) -> list[CandidateFetchBucket]:
    profile = profile.normalized()
    media = media_weights(profile.media_preference)
    era = release_weights(profile.release_preference)
    vibe = vibe_weights(profile.vibe_preference)
    country_selection = profile.country_selection
    if not isinstance(country_selection, CountrySelection):
        country_selection = _coerce_country_selection(
            country_selection,
            ui_language=profile.ui_language,
            origin_preference=profile.origin_preference,
        )
    country_selection = country_selection.normalized()
    country_plan = build_country_plan(country_selection, target)
    genre_ids = genre_ids or {}

    raw_quotas: dict[tuple[str, str, str, str], float] = {}
    quota_weights: dict[tuple[str, str, str, str], float] = {}
    for target_country, country_quota in country_plan.items():
        for media_type, media_weight in media.items():
            for era_name, era_weight in era.items():
                for vibe_name, vibe_weight in vibe.items():
                    key = (target_country, media_type, era_name, vibe_name)
                    country_weight = float(country_selection.country_weights.get(target_country, 0.0))
                    quota_weight = country_weight * media_weight * era_weight * vibe_weight
                    quota_weights[key] = quota_weight
                    raw_quotas[key] = country_quota * media_weight * era_weight * vibe_weight

    quotas = _allocate_country_bucket_quotas(
        raw_quotas,
        country_plan=country_plan,
        media_targets=_allocate_weighted(media, target),
        era_targets=_allocate_weighted(era, target),
        vibe_targets=_allocate_weighted(vibe, target),
        target=target,
    )
    buckets: list[CandidateFetchBucket] = []
    for key, quota in quotas.items():
        if quota <= 0:
            continue
        target_country, media_type, era_name, vibe_name = key
        country_weight = float(country_selection.country_weights.get(target_country, 0.0))
        origin_name = ORIGIN_DOMESTIC if target_country == country_selection.home_country else ORIGIN_FOREIGN
        buckets.append(
            CandidateFetchBucket(
                media_type=media_type,
                era=era_name,
                vibe=vibe_name,
                origin=origin_name,
                original_language=None,
                quota=quota,
                quota_weight=quota_weights[key],
                target_country=target_country,
                target_country_weight=country_weight,
                home_country=country_selection.home_country,
                exclude_home_country=country_selection.exclude_home_country,
                genre_ids=tuple(genre_ids.get(media_type, {}).get(vibe_name, ())),
            )
        )
    buckets.sort(key=lambda bucket: stable_bucket_key(bucket))
    return buckets


def _media_order(profile: OnboardingTasteProfile) -> dict[str, int]:
    if profile.media_preference == "tv":
        return {MEDIA_TV: 0, MEDIA_MOVIE: 1}
    return {MEDIA_MOVIE: 0, MEDIA_TV: 1}


def _vibe_order(profile: OnboardingTasteProfile) -> dict[str, int]:
    if profile.vibe_preference == "dark":
        return {VIBE_DARK: 0, VIBE_LIGHT: 1}
    return {VIBE_LIGHT: 0, VIBE_DARK: 1}


def _origin_order(profile: OnboardingTasteProfile) -> dict[str, int]:
    if profile.origin_preference == "foreign":
        return {ORIGIN_FOREIGN: 0, ORIGIN_DOMESTIC: 1, ORIGIN_ANY: 2}
    if profile.origin_preference == "domestic":
        return {ORIGIN_DOMESTIC: 0, ORIGIN_FOREIGN: 1, ORIGIN_ANY: 2}
    return {ORIGIN_ANY: 0, ORIGIN_DOMESTIC: 1, ORIGIN_FOREIGN: 2}


def bucket_priority_key(bucket: CandidateFetchBucket, profile: OnboardingTasteProfile) -> tuple[Any, ...]:
    era_order = {ERA_TOP_ALL_TIME: 0, ERA_CLASSIC_SWEEP: 1, ERA_NEW_SWEEP: 2}
    language_order = {language: index for index, (language, _) in enumerate(FOREIGN_LANGUAGE_BUCKETS)}
    return (
        -bucket.quota,
        _media_order(profile).get(bucket.media_type, 99),
        era_order.get(bucket.era, 99),
        _vibe_order(profile).get(bucket.vibe, 99),
        _origin_order(profile).get(bucket.origin, 99),
        language_order.get(bucket.original_language or "", 99),
        bucket.bucket_id,
    )


def _ui_language_to_tmdb_locale(ui_language: str) -> str:
    return "ru-RU" if str(ui_language or "").strip().casefold() == "ru" else "en-US"


def _endpoint(media_type: str) -> str:
    return "/discover/movie" if media_type == MEDIA_MOVIE else "/discover/tv"


def _year_field(media_type: str) -> str:
    return "primary_release_year" if media_type == MEDIA_MOVIE else "first_air_date_year"


def _date_field(media_type: str) -> str:
    return "release_date" if media_type == MEDIA_MOVIE else "first_air_date"


def _title_field(media_type: str) -> tuple[str, str]:
    if media_type == MEDIA_MOVIE:
        return "title", "original_title"
    return "name", "original_name"


def _base_vote_count(bucket: CandidateFetchBucket) -> int:
    if bucket.era == ERA_TOP_ALL_TIME:
        return 1000 if bucket.media_type == MEDIA_MOVIE else 300
    if bucket.era == ERA_CLASSIC_SWEEP:
        return 300 if bucket.media_type == MEDIA_MOVIE else 100
    return 100 if bucket.media_type == MEDIA_MOVIE else 50


def _vote_count_for_fallback(bucket: CandidateFetchBucket, fallback: str) -> int | None:
    if fallback == FALLBACK_POPULAR:
        return None
    base = _base_vote_count(bucket)
    if fallback in {FALLBACK_BASE, FALLBACK_RELAX_ORIGIN, FALLBACK_RELAX_GENRES}:
        return base
    if fallback == FALLBACK_RELAX_VOTES_MID:
        if bucket.media_type == MEDIA_MOVIE:
            return min(base, 300)
        return min(base, 100)
    return 100 if bucket.media_type == MEDIA_MOVIE else 50


def _is_hard_origin_bucket(profile: OnboardingTasteProfile, bucket: CandidateFetchBucket) -> bool:
    if bucket.target_country:
        return True
    return (
        str(profile.ui_language or "").strip().casefold() == "ru"
        and bucket.origin in {ORIGIN_DOMESTIC, ORIGIN_FOREIGN}
    )


def _fallback_order_for_bucket(profile: OnboardingTasteProfile, bucket: CandidateFetchBucket) -> tuple[str, ...]:
    if _is_hard_origin_bucket(profile, bucket):
        return tuple(fallback for fallback in FALLBACK_ORDER if fallback != FALLBACK_RELAX_ORIGIN)
    return FALLBACK_ORDER


def _domestic_filter_for_fallback(fallback: str) -> dict[str, str]:
    if fallback in {FALLBACK_RELAX_VOTES_LOW, FALLBACK_RELAX_ERA, FALLBACK_POPULAR}:
        return {"with_origin_country": "RU"}
    return dict(DOMESTIC_FILTER)


def _years_for_bucket(bucket: CandidateFetchBucket, current_year: int) -> list[int]:
    if bucket.era == ERA_CLASSIC_SWEEP:
        return list(range(CLASSIC_START_YEAR, CLASSIC_END_YEAR + 1))
    if bucket.era == ERA_NEW_SWEEP:
        return list(range(max(NEW_START_YEAR, current_year), NEW_START_YEAR - 1, -1))
    return []


def build_discover_request(
    bucket: CandidateFetchBucket,
    *,
    profile: OnboardingTasteProfile,
    fallback: str,
    request_index: int,
    current_year: int | None = None,
    current_date: date | None = None,
) -> tuple[str, dict[str, Any]]:
    current_year = current_year or _current_year()
    current_date = current_date or _current_date()
    params: dict[str, Any] = {
        "include_adult": False,
        "language": _ui_language_to_tmdb_locale(profile.ui_language),
        _date_lte_field(bucket.media_type): current_date.isoformat(),
    }

    effective_popular = fallback == FALLBACK_POPULAR
    effective_relax_era = fallback in {FALLBACK_RELAX_ERA, FALLBACK_POPULAR}
    effective_no_genres = fallback in {
        FALLBACK_RELAX_GENRES,
        FALLBACK_RELAX_VOTES_MID,
        FALLBACK_RELAX_VOTES_LOW,
        FALLBACK_RELAX_ERA,
        FALLBACK_POPULAR,
    }
    effective_any_origin = fallback == FALLBACK_RELAX_ORIGIN and not _is_hard_origin_bucket(profile, bucket)

    years = [] if effective_relax_era else _years_for_bucket(bucket, current_year)
    if years:
        year = years[request_index % len(years)]
        params[_year_field(bucket.media_type)] = year
        params["page"] = 1 + request_index // len(years)
        params["sort_by"] = "popularity.desc"
    else:
        params["page"] = request_index + 1
        if effective_popular or effective_relax_era:
            params["sort_by"] = "popularity.desc"
        elif bucket.era == ERA_TOP_ALL_TIME:
            params["sort_by"] = "vote_average.desc"
        else:
            params["sort_by"] = "popularity.desc"

    if effective_no_genres is False and bucket.genre_ids:
        params["with_genres"] = "|".join(str(genre_id) for genre_id in bucket.genre_ids)

    if bucket.target_country:
        params["with_origin_country"] = bucket.target_country
    elif effective_any_origin is False:
        if bucket.origin == ORIGIN_DOMESTIC:
            params.update(_domestic_filter_for_fallback(fallback))
        elif bucket.origin == ORIGIN_FOREIGN and bucket.original_language:
            params["with_original_language"] = bucket.original_language

    vote_count = _vote_count_for_fallback(bucket, fallback)
    if vote_count is not None:
        params["vote_count.gte"] = vote_count
    return _endpoint(bucket.media_type), params


def canonical_discover_request_key(endpoint: str, params: dict[str, Any]) -> str:
    canonical_params = {
        str(key): value
        for key, value in params.items()
        if not str(key).startswith("_")
    }
    return json.dumps(
        {"endpoint": str(endpoint), "params": canonical_params},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _discover_candidate_stub(result: dict[str, Any], media_type: str) -> dict[str, Any]:
    title_key, original_title_key = _title_field(media_type)
    date_key = _date_field(media_type)
    return {
        "media_type": media_type,
        "tmdb_id": result.get("id"),
        "title": result.get(title_key) or result.get(original_title_key) or "",
        "alternative_title": result.get(original_title_key) or "",
        "year": tmdb_api.get_year(result.get(date_key)),
        date_key: result.get(date_key),
    }


def _load_hidden_or_rejected_identities(path: str | Path | None = None) -> set[str]:
    identities: set[str] = set()
    for action in (action_repository.ACTION_HIDDEN, "rejected"):
        try:
            identities.update(action_repository.load_action_identities(action, path=path))
        except Exception:
            continue
    return identities


def _result_number(result: dict[str, Any], key: str) -> float | None:
    value = result.get(key)
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _result_country_codes(result: dict[str, Any]) -> list[str]:
    return country_schema.normalize_country_filter_list(
        result.get("origin_country")
        or result.get("production_countries")
        or result.get("country_codes")
        or result.get("countries")
    )


def candidate_rejection_reason(
    result: dict[str, Any],
    bucket: CandidateFetchBucket,
    *,
    existing_index: dict[str, Any],
    accepted_identities: set[tuple[str, int]],
    hidden_or_rejected_identities: set[str],
    watched_signatures: set[str],
    dataset_title_keys: set[str],
    current_date: date | None = None,
) -> str | None:
    current_date = current_date or _current_date()
    tmdb_id = result.get("id")
    if tmdb_id in (None, ""):
        return "missing_id"
    try:
        normalized_tmdb_id = int(tmdb_id)
    except (TypeError, ValueError):
        return "bad_id"
    if result.get("poster_path") in (None, ""):
        return "missing_poster"
    release_date = _parse_iso_date(result.get(_date_field(bucket.media_type)))
    result_year = _result_year(result, bucket.media_type)
    if release_date is not None and release_date > current_date:
        return "future"
    if result_year is not None and result_year > current_date.year:
        return "future"
    vote_average = _result_number(result, "vote_average")
    vote_count = _result_number(result, "vote_count")
    if vote_average is None or vote_count is None:
        return "missing_votes"
    if vote_average < 5.8:
        return "low_score"
    if bucket.era == ERA_TOP_ALL_TIME and vote_count < _base_vote_count(bucket):
        return "low_votes"
    country_codes = _result_country_codes(result)
    if bucket.target_country and country_codes and bucket.target_country not in country_codes:
        return "wrong_country"
    if bucket.exclude_home_country and bucket.home_country in country_codes:
        return "home_country_excluded"
    if (bucket.media_type, normalized_tmdb_id) in accepted_identities:
        return "duplicate_batch"
    if discover_item_existing_reason(result, existing_index, media_type=bucket.media_type) is not None:
        return "existing"

    candidate_stub = _discover_candidate_stub(result, bucket.media_type)
    if is_watched_candidate(
        candidate_stub,
        watched_signatures=watched_signatures,
        dataset_title_keys=dataset_title_keys,
    ):
        return "watched"
    if title_identity_key(candidate_stub) in hidden_or_rejected_identities:
        return "hidden_or_rejected"
    return None


def accept_candidate(
    result: dict[str, Any],
    bucket: CandidateFetchBucket,
    *,
    existing_index: dict[str, Any],
    accepted_identities: set[tuple[str, int]],
    hidden_or_rejected_identities: set[str],
    watched_signatures: set[str],
    dataset_title_keys: set[str],
    current_date: date | None = None,
) -> bool:
    return candidate_rejection_reason(
        result,
        bucket,
        existing_index=existing_index,
        accepted_identities=accepted_identities,
        hidden_or_rejected_identities=hidden_or_rejected_identities,
        watched_signatures=watched_signatures,
        dataset_title_keys=dataset_title_keys,
        current_date=current_date,
    ) is None


def _genre_lookup_by_id(client: TmdbClientProtocol) -> dict[str, dict[int, str]]:
    return {
        MEDIA_MOVIE: {
            int(item["id"]): str(item["name"])
            for item in client.movie_genres(language="en")
            if item.get("id") not in (None, "") and item.get("name") not in (None, "")
        },
        MEDIA_TV: {
            int(item["id"]): str(item["name"])
            for item in client.tv_genres(language="en")
            if item.get("id") not in (None, "") and item.get("name") not in (None, "")
        },
    }


def _result_year(result: dict[str, Any], media_type: str) -> int | None:
    return tmdb_api.get_year(result.get(_date_field(media_type)))


def compute_candidate_score(
    result: dict[str, Any],
    bucket: CandidateFetchBucket,
    *,
    page: int,
    index_on_page: int,
) -> float:
    vote_average = float(result.get("vote_average") or 0)
    vote_count = float(result.get("vote_count") or 0)
    popularity = float(result.get("popularity") or 0)
    bucket_priority_score = int(bucket.quota_weight * 10_000)
    tmdb_quality_score = vote_average * 100 + min(math.log10(max(vote_count, 1)) * 100, 500) + min(popularity, 500)
    result_year = _result_year(result, bucket.media_type) or 0
    freshness_score = 0
    if bucket.era == ERA_NEW_SWEEP:
        freshness_score = max(0, result_year - 2021) * 20
    fetch_order_penalty = int(page) * 20 + int(index_on_page)
    return round(100000 + bucket_priority_score + tmdb_quality_score + freshness_score - fetch_order_penalty, 4)


def build_candidate_record_from_result(
    result: dict[str, Any],
    bucket: CandidateFetchBucket,
    *,
    genre_lookup: dict[str, dict[int, str]],
    profile_id: int,
    candidate_score: float,
    fetch_rank: int,
    fallback: str = FALLBACK_BASE,
) -> dict[str, Any]:
    title_key, original_title_key = _title_field(bucket.media_type)
    date_key = _date_field(bucket.media_type)
    genre_names = [
        genre_lookup.get(bucket.media_type, {}).get(int(genre_id))
        for genre_id in result.get("genre_ids") or []
        if str(genre_id).strip().lstrip("-").isdigit()
    ]
    genre_names = [name for name in genre_names if name]
    country_codes = _result_country_codes(result)
    if bucket.target_country and len(country_codes) == 0:
        country_codes.append(bucket.target_country)
    if bucket.origin == ORIGIN_DOMESTIC and bucket.home_country not in country_codes:
        country_codes.append(bucket.home_country)

    candidate = {
        "media_type": bucket.media_type,
        "source": "onboarding_autofill",
        "source_provider": "tmdb",
        "source_version": 3,
        "source_bucket_id": bucket.bucket_id,
        "origin_bucket": bucket.origin,
        "target_country": bucket.target_country,
        "target_country_weight": bucket.target_country_weight,
        "onboarding_profile_id": int(profile_id),
        "candidate_score": candidate_score,
        "fetch_rank": int(fetch_rank),
        "criteria_name": COMMON_POOL_CRITERIA_NAME,
        "tmdb_id": result.get("id"),
        "title": result.get(title_key) or result.get(original_title_key) or "",
        "original_title": result.get(original_title_key),
        "year": _result_year(result, bucket.media_type),
        date_key: result.get(date_key),
        "description": result.get("overview"),
        "overview": result.get("overview"),
        "genres": genre_names,
        "genre_keys": build_genre_keys({"genres": genre_names}),
        "countries": country_codes,
        "country_codes": country_codes,
        "original_language": result.get("original_language"),
        "tmdb_score": result.get("vote_average"),
        "tmdb_votes": result.get("vote_count"),
        "tmdb_popularity": result.get("popularity"),
        "poster_path": result.get("poster_path"),
        "poster_url": tmdb_api.image_link(result.get("poster_path")),
        "backdrop_path": result.get("backdrop_path"),
        "backdrop_url": tmdb_api.image_link(result.get("backdrop_path")),
        "source_query": {
            "onboarding_bucket": bucket.bucket_id,
            "media_type": bucket.media_type,
            "era": bucket.era,
            "vibe": bucket.vibe,
            "origin": bucket.origin,
            "target_country": bucket.target_country,
            "target_country_weight": bucket.target_country_weight,
            "original_language": bucket.original_language,
            "fallback": fallback,
        },
        "signals": ["onboarding_autofill"],
    }
    candidate["quality_score"] = round(
        float(result.get("vote_average") or 0) * 10
        + min(math.log10(max(float(result.get("vote_count") or 1), 1)) * 10, 50)
        + min(float(result.get("popularity") or 0), 500) / 10,
        4,
    )
    candidate["hidden_gem_score"] = 0.0
    candidate["final_score"] = round(candidate_score / 10_000, 4)
    completeness = compute_completeness(candidate)
    candidate["is_complete"] = completeness["is_complete"]
    candidate["missing_fields"] = completeness["missing_fields"]
    candidate["optional_missing_fields"] = completeness["optional_missing_fields"]
    return normalize_candidate_record(candidate)


def _emit(progress_callback: ProgressCallback | None, **payload: Any) -> None:
    if progress_callback is not None:
        progress_callback(payload)


def _pool_snapshot(path: str | Path | None = None) -> dict[str, dict[str, Any]]:
    data = load_candidate_pool_dict(path=path)
    return data if isinstance(data, dict) else {}


def planned_counts_for_profile(
    profile: OnboardingTasteProfile,
    *,
    target: int = STARTER_POOL_TARGET,
    genre_ids: dict[str, dict[str, tuple[int, ...]]] | None = None,
) -> dict[str, dict[str, int]]:
    buckets = build_fetch_buckets(profile.normalized(), genre_ids=genre_ids, target=target)

    def totals(field: str) -> dict[str, int]:
        counter: Counter[str] = Counter()
        for bucket in buckets:
            value = getattr(bucket, field)
            if value is not None:
                counter[str(value)] += int(bucket.quota)
        return dict(counter)

    return {
        "media_type": totals("media_type"),
        "release": totals("era"),
        "vibe": totals("vibe"),
        "country": totals("target_country"),
        "origin": totals("origin"),
        "original_language": totals("original_language"),
    }


def actual_counts_for_candidates(candidates: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    counters = {
        "media_type": Counter(),
        "release": Counter(),
        "vibe": Counter(),
        "country": Counter(),
        "origin": Counter(),
        "original_language": Counter(),
        "fallback": Counter(),
    }
    for candidate in candidates:
        source_query = candidate.get("source_query") if isinstance(candidate.get("source_query"), dict) else {}
        media_type = candidate.get("media_type") or source_query.get("media_type")
        if media_type:
            counters["media_type"][str(media_type)] += 1
        release = source_query.get("era")
        if release:
            counters["release"][str(release)] += 1
        vibe = source_query.get("vibe")
        if vibe:
            counters["vibe"][str(vibe)] += 1
        target_country = candidate.get("target_country") or source_query.get("target_country")
        if target_country:
            counters["country"][str(target_country)] += 1
        origin = candidate.get("origin_bucket") or source_query.get("origin")
        if origin:
            counters["origin"][str(origin)] += 1
        language = source_query.get("original_language") or candidate.get("original_language")
        if language:
            counters["original_language"][str(language)] += 1
        fallback = source_query.get("fallback")
        if fallback:
            counters["fallback"][str(fallback)] += 1
    return {name: dict(counter) for name, counter in counters.items()}


def should_start_onboarding_autofill(*, path: str | Path | None = None) -> bool:
    if has_completed_onboarding_profile(path=path):
        return False
    return len(_pool_snapshot(path=path)) == 0


def _build_warnings(
    *,
    profile: OnboardingTasteProfile,
    planned_counts: dict[str, dict[str, int]],
    actual_counts: dict[str, dict[str, int]],
    created_count: int,
    rejected_future_count: int,
) -> list[str]:
    warnings: list[str] = []
    if created_count < STARTER_POOL_TARGET:
        warnings.append(f"Starter pool underfilled: created {created_count} of {STARTER_POOL_TARGET}.")
    if created_count < STARTER_POOL_MIN_ACCEPTABLE:
        warnings.append(f"Only {created_count} candidates collected; the pool can be topped up later.")
    for media_type, planned in sorted(planned_counts.get("media_type", {}).items()):
        actual = int(actual_counts.get("media_type", {}).get(media_type, 0))
        if actual < int(planned):
            warnings.append(f"Media quota underfilled: {media_type} planned {planned}, actual {actual}.")
    for country, planned in sorted(planned_counts.get("country", {}).items()):
        actual = int(actual_counts.get("country", {}).get(country, 0))
        if actual < int(planned):
            warnings.append(f"Country quota underfilled: {country} planned {planned}, actual {actual}.")
    if str(profile.ui_language or "").strip().casefold() == "ru":
        for origin in (ORIGIN_DOMESTIC, ORIGIN_FOREIGN):
            planned = int(planned_counts.get("origin", {}).get(origin, 0))
            actual = int(actual_counts.get("origin", {}).get(origin, 0))
            if planned > 0 and actual < planned:
                warnings.append(f"Origin quota underfilled: {origin} planned {planned}, actual {actual}.")
    if rejected_future_count > 0:
        warnings.append(f"Rejected future/unreleased titles: {rejected_future_count}.")
    return warnings


def _save_pool_incremental(
    pool: dict[str, dict[str, Any]],
    candidates: list[dict[str, Any]],
    *,
    path: str | Path | None = None,
) -> None:
    for candidate in candidates:
        key = pool_entry_key(candidate)
        if key != "|":
            candidate["pool_entry_key"] = key
            pool[key] = candidate
    save_candidate_pool_dict(pool, path=path)


def run_onboarding_autofill(
    profile: OnboardingTasteProfile,
    *,
    client: TmdbClientProtocol | None = None,
    path: str | Path | None = None,
    progress_callback: ProgressCallback | None = None,
    cancel_checker: CancelChecker | None = None,
    current_year: int | None = None,
) -> AutofillResult:
    profile = profile.normalized()
    client = client or TmdbAutofillClient()
    current_year = current_year or _current_year()
    current_date = date(current_year, 12, 31) if current_year != _current_year() else _current_date()
    cancelled = False
    profile_id = create_onboarding_profile(profile.as_repository_dict(), path=path)
    pool = _pool_snapshot(path=path)
    created_candidates: list[dict[str, Any]] = []
    accepted_identities: set[tuple[str, int]] = set()
    existing_index = build_existing_candidate_index(pool)
    hidden_or_rejected = _load_hidden_or_rejected_identities(path=path)
    try:
        watched_signatures = build_watched_signatures()
        dataset_title_keys = build_dataset_title_keys()
    except Exception:
        watched_signatures = set()
        dataset_title_keys = set()

    _emit(progress_callback, stage=1, message="Настраиваем вкус", profile_id=profile_id)
    genre_ids = resolve_tmdb_genre_ids(client)
    genre_lookup = _genre_lookup_by_id(client)
    _emit(progress_callback, stage=2, message="Собираем жанровые направления", profile_id=profile_id)
    buckets = build_fetch_buckets(profile, genre_ids=genre_ids)
    planned_counts = planned_counts_for_profile(profile, genre_ids=genre_ids)
    states = [_BucketState(bucket=bucket) for bucket in sorted(buckets, key=lambda item: bucket_priority_key(item, profile))]
    api_requests = 0
    fetch_rank = 0
    rejected_future_count = 0
    duplicate_requests_skipped = 0
    executed_request_keys: set[str] = set()

    def is_cancelled() -> bool:
        return bool(cancel_checker is not None and cancel_checker())

    for fallback in FALLBACK_ORDER:
        for state in states:
            state.request_index = 0
            state.exhausted = False
        while len(created_candidates) < STARTER_POOL_TARGET and api_requests < MAX_TMDB_REQUESTS:
            progressed = False
            for state in states:
                if len(created_candidates) >= STARTER_POOL_TARGET or api_requests >= MAX_TMDB_REQUESTS:
                    break
                if state.filled >= state.bucket.quota or state.exhausted:
                    continue
                if fallback not in _fallback_order_for_bucket(profile, state.bucket):
                    continue
                if is_cancelled():
                    cancelled = True
                    break
                bucket = state.bucket
                endpoint, params = build_discover_request(
                    bucket,
                    profile=profile,
                    fallback=fallback,
                    request_index=state.request_index,
                    current_year=current_year,
                    current_date=current_date,
                )
                message = f"Собираем {'фильмы' if bucket.media_type == MEDIA_MOVIE else 'сериалы'} · {'лёгкий вайб' if bucket.vibe == VIBE_LIGHT else 'мрачный вайб'}"
                if bucket.era == ERA_NEW_SWEEP:
                    message += " · новинки"
                elif bucket.era == ERA_CLASSIC_SWEEP:
                    message += " · классика"
                _emit(
                    progress_callback,
                    stage=3,
                    message=message,
                    profile_id=profile_id,
                    pool_size=len(created_candidates),
                    api_requests=api_requests,
                    completed_buckets=sum(1 for item in states if item.filled >= item.bucket.quota),
                    total_buckets=len(states),
                    fallback=fallback,
                )
                page = int(params.get("page") or 1)
                request_key = canonical_discover_request_key(endpoint, params)
                if request_key in executed_request_keys:
                    duplicate_requests_skipped += 1
                    save_autofill_request_audit(
                        {
                            "onboarding_profile_id": profile_id,
                            "bucket_id": bucket.bucket_id,
                            "endpoint": endpoint,
                            "params": {**params, "_fallback": fallback},
                            "page": page,
                            "status": "skipped_duplicate",
                            "accepted_count": 0,
                            "rejected_count": 0,
                            "error_text": None,
                        },
                        path=path,
                    )
                    state.request_index += 1
                    progressed = True
                    continue
                executed_request_keys.add(request_key)
                accepted_batch: list[dict[str, Any]] = []
                rejected_count = 0
                status = "ok"
                error_text = None
                try:
                    payload = client.discover(endpoint, params)
                    api_requests += 1
                    results = payload.get("results") if isinstance(payload, dict) else []
                    results = results if isinstance(results, list) else []
                    if not results:
                        state.exhausted = True
                    for index_on_page, result in enumerate(results):
                        if len(created_candidates) + len(accepted_batch) >= STARTER_POOL_TARGET:
                            break
                        if state.filled + len(accepted_batch) >= state.bucket.quota:
                            break
                        rejection_reason = candidate_rejection_reason(
                            result,
                            bucket,
                            existing_index=existing_index,
                            accepted_identities=accepted_identities,
                            hidden_or_rejected_identities=hidden_or_rejected,
                            watched_signatures=watched_signatures,
                            dataset_title_keys=dataset_title_keys,
                            current_date=current_date,
                        )
                        if rejection_reason is not None:
                            if rejection_reason == "future":
                                rejected_future_count += 1
                            rejected_count += 1
                            continue
                        fetch_rank += 1
                        candidate_score = compute_candidate_score(
                            result,
                            bucket,
                            page=page,
                            index_on_page=index_on_page,
                        )
                        candidate = build_candidate_record_from_result(
                            result,
                            bucket,
                            genre_lookup=genre_lookup,
                            profile_id=profile_id,
                            candidate_score=candidate_score,
                            fetch_rank=fetch_rank,
                            fallback=fallback,
                        )
                        accepted_batch.append(candidate)
                        accepted_identities.add((bucket.media_type, int(result["id"])))
                        state.filled += 1
                    total_pages = int((payload or {}).get("total_pages") or page)
                    if page >= total_pages:
                        state.exhausted = True
                except Exception as error:
                    api_requests += 1
                    status = "error"
                    error_text = str(error)
                    state.exhausted = True
                finally:
                    save_autofill_request_audit(
                        {
                            "onboarding_profile_id": profile_id,
                            "bucket_id": bucket.bucket_id,
                            "endpoint": endpoint,
                            "params": {**params, "_fallback": fallback},
                            "page": page,
                            "status": status,
                            "accepted_count": len(accepted_batch),
                            "rejected_count": rejected_count,
                            "error_text": error_text,
                        },
                        path=path,
                    )
                state.request_index += 1
                progressed = True
                if accepted_batch:
                    _emit(progress_callback, stage=4, message="Убираем повторы", profile_id=profile_id)
                    created_candidates.extend(accepted_batch)
                    _emit(progress_callback, stage=5, message="Создаём первый пул", profile_id=profile_id)
                    _save_pool_incremental(pool, accepted_batch, path=path)
                    existing_index = build_existing_candidate_index(pool)
            if cancelled:
                break
            if progressed is False:
                break
        if cancelled or len(created_candidates) >= STARTER_POOL_TARGET or api_requests >= MAX_TMDB_REQUESTS:
            break

    complete_onboarding_profile(profile_id, path=path)
    actual_counts = actual_counts_for_candidates(created_candidates)
    warnings = _build_warnings(
        profile=profile,
        planned_counts=planned_counts,
        actual_counts=actual_counts,
        created_count=len(created_candidates),
        rejected_future_count=rejected_future_count,
    )
    warning = "\n".join(warnings) if warnings else None
    _emit(
        progress_callback,
        stage=6,
        message="Готово",
        profile_id=profile_id,
        pool_size=len(created_candidates),
        api_requests=api_requests,
        cancelled=cancelled,
        warning=warning,
    )
    return AutofillResult(
        ok=cancelled is False,
        profile_id=profile_id,
        created_count=len(created_candidates),
        pool_size=len(_pool_snapshot(path=path)),
        api_requests=api_requests,
        cancelled=cancelled,
        warning=warning,
        candidates=created_candidates,
        warnings=warnings,
        planned_counts=planned_counts,
        actual_counts=actual_counts,
        rejected_future_count=rejected_future_count,
        duplicate_requests_skipped=duplicate_requests_skipped,
    )

"""Deterministic TMDb onboarding autofill for the starter candidate pool."""

from __future__ import annotations

import copy
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
import json
import math
from pathlib import Path
from typing import Any, Callable, Protocol

from apis import tmdb_api
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
FALLBACK_RELAX_LANGUAGE = "relax_language"
FALLBACK_RELAX_VOTES_MID = "relax_votes_mid"
FALLBACK_RELAX_VOTES_LOW = "relax_votes_low"
FALLBACK_RELAX_VOTES_TINY = "relax_votes_tiny"
FALLBACK_RELAX_VOTES_ZERO = "relax_votes_zero"
FALLBACK_RELAX_ERA = "relax_era"
FALLBACK_POPULAR = "popular"

SEED_ORIGIN_TOP = "origin_top_seed"
SEED_QUALITY = "quality_seed"
SEED_ORDER = (SEED_ORIGIN_TOP, SEED_QUALITY)

SOURCE_STAGE_ORIGIN_TOP_SEED = "origin_top_seed"
SOURCE_STAGE_QUALITY_SEED = "quality_seed"
SOURCE_STAGE_FOCUSED = "focused"
SOURCE_STAGE_FALLBACK = "fallback"
QUALITY_SEED_MAX_SHARE = 0.20

STRATEGY_BASELINE_QUOTA_FIX = "baseline_quota_fix"
STRATEGY_BROAD_TOP_SEED = "broad_top_seed"
STRATEGY_FOCUSED_FIRST = "focused_first"
STRATEGY_HYBRID_QUALITY_FOCUSED = "hybrid_quality_focused"
STRATEGY_STRICT_UNDERFILL = "strict_underfill"
DEFAULT_AUTOFILL_STRATEGY = STRATEGY_BROAD_TOP_SEED
SUPPORTED_AUTOFILL_STRATEGIES = (
    STRATEGY_BASELINE_QUOTA_FIX,
    STRATEGY_BROAD_TOP_SEED,
    STRATEGY_FOCUSED_FIRST,
    STRATEGY_HYBRID_QUALITY_FOCUSED,
    STRATEGY_STRICT_UNDERFILL,
)

FALLBACK_ORDER = (
    FALLBACK_BASE,
    FALLBACK_RELAX_ORIGIN,
    FALLBACK_RELAX_ERA,
    FALLBACK_RELAX_VOTES_MID,
    FALLBACK_RELAX_VOTES_LOW,
    FALLBACK_RELAX_VOTES_TINY,
    FALLBACK_RELAX_VOTES_ZERO,
    FALLBACK_RELAX_GENRES,
    FALLBACK_RELAX_LANGUAGE,
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


@dataclass(frozen=True)
class OnboardingTasteProfile:
    media_preference: str
    release_preference: str
    vibe_preference: str
    origin_preference: str | None
    ui_language: str

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
        return OnboardingTasteProfile(
            media_preference=media_preference,
            release_preference=release_preference,
            vibe_preference=vibe_preference,
            origin_preference=origin_preference,
            ui_language=ui_language,
        )

    def as_repository_dict(self) -> dict[str, Any]:
        return asdict(self.normalized())


@dataclass(frozen=True)
class CandidateFetchBucket:
    media_type: str
    era: str
    vibe: str
    origin: str
    original_language: str | None
    quota: int
    quota_weight: float
    genre_ids: tuple[int, ...] = ()

    @property
    def bucket_id(self) -> str:
        language = self.original_language or "any"
        return f"{self.media_type}:{self.era}:{self.vibe}:{self.origin}:{language}"


@dataclass
class _BucketState:
    bucket: CandidateFetchBucket
    filled: int = 0
    request_index: int = 0
    exhausted: bool = False


@dataclass(frozen=True)
class AutofillResult:
    ok: bool
    strategy: str
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
    source_stats: dict[str, int]
    rejection_counts: dict[str, int]
    request_stats: dict[str, int]
    rejected_future_count: int = 0


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
    origin = origin_weights(profile.origin_preference, ui_language=profile.ui_language)
    genre_ids = genre_ids or {}

    raw_quotas: dict[tuple[str, str, str, str, str | None], float] = {}
    quota_weights: dict[tuple[str, str, str, str, str | None], float] = {}
    for media_type, media_weight in media.items():
        for era_name, era_weight in era.items():
            for vibe_name, vibe_weight in vibe.items():
                for origin_name, origin_weight in origin.items():
                    if origin_name == ORIGIN_FOREIGN:
                        for language, language_weight in FOREIGN_LANGUAGE_BUCKETS:
                            key = (media_type, era_name, vibe_name, origin_name, language)
                            quota_weight = media_weight * era_weight * vibe_weight * origin_weight * language_weight
                            quota_weights[key] = quota_weight
                            raw_quotas[key] = target * quota_weight
                    else:
                        key = (media_type, era_name, vibe_name, origin_name, None)
                        quota_weight = media_weight * era_weight * vibe_weight * origin_weight
                        quota_weights[key] = quota_weight
                        raw_quotas[key] = target * quota_weight

    quotas = _allocate_bucket_quotas(raw_quotas, profile=profile, target=target)
    buckets: list[CandidateFetchBucket] = []
    for key, quota in quotas.items():
        if quota <= 0:
            continue
        media_type, era_name, vibe_name, origin_name, language = key
        buckets.append(
            CandidateFetchBucket(
                media_type=media_type,
                era=era_name,
                vibe=vibe_name,
                origin=origin_name,
                original_language=language,
                quota=quota,
                quota_weight=quota_weights[key],
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


_VOLATILE_REQUEST_PARAM_TOKENS = ("token", "api_key", "authorization", "debug")


def _normalize_request_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _normalize_request_value(value[key]) for key in sorted(value)}
    if isinstance(value, (list, tuple, set)):
        return sorted(_normalize_request_value(item) for item in value)
    if isinstance(value, str):
        text = value.strip()
        if "|" in text or "," in text:
            parts = [part.strip() for part in text.replace(",", "|").split("|") if part.strip()]
            return "|".join(sorted(parts))
        return text
    return value


def canonical_discover_request_key(endpoint: str, params: dict[str, Any]) -> str:
    normalized_params = {
        str(key): _normalize_request_value(value)
        for key, value in params.items()
        if not str(key).startswith("_")
        and not any(token in str(key).casefold() for token in _VOLATILE_REQUEST_PARAM_TOKENS)
    }
    return json.dumps(
        {"endpoint": str(endpoint), "params": normalized_params},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _state_remaining(state: _BucketState) -> int:
    return max(0, int(state.bucket.quota) - int(state.filled))


def _state_deficit_priority_key(
    profile: OnboardingTasteProfile,
    state: _BucketState,
    states: list[_BucketState],
) -> tuple[Any, ...]:
    bucket = state.bucket
    remaining = _state_remaining(state)
    media_deficit = sum(_state_remaining(item) for item in states if item.bucket.media_type == bucket.media_type)
    origin_deficit = 0
    if _is_hard_origin_bucket(profile, bucket):
        origin_deficit = sum(_state_remaining(item) for item in states if item.bucket.origin == bucket.origin)
    combined_deficit = remaining + media_deficit + origin_deficit
    return (
        -combined_deficit,
        -origin_deficit,
        -media_deficit,
        -remaining,
        bucket_priority_key(bucket, profile),
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
    if fallback in {FALLBACK_BASE, FALLBACK_RELAX_ORIGIN, FALLBACK_RELAX_ERA}:
        return base
    if fallback == FALLBACK_RELAX_VOTES_MID:
        if bucket.media_type == MEDIA_MOVIE:
            return min(base, 300)
        return min(base, 100)
    if fallback == FALLBACK_RELAX_VOTES_LOW:
        return min(base, 100 if bucket.media_type == MEDIA_MOVIE else 50)
    if fallback == FALLBACK_RELAX_VOTES_TINY:
        return min(base, 50 if bucket.media_type == MEDIA_MOVIE else 20)
    return 0


def _is_hard_origin_bucket(profile: OnboardingTasteProfile, bucket: CandidateFetchBucket) -> bool:
    return (
        str(profile.ui_language or "").strip().casefold() == "ru"
        and bucket.origin in {ORIGIN_DOMESTIC, ORIGIN_FOREIGN}
    )


def _fallback_order_for_bucket(profile: OnboardingTasteProfile, bucket: CandidateFetchBucket) -> tuple[str, ...]:
    if _is_hard_origin_bucket(profile, bucket):
        return tuple(fallback for fallback in FALLBACK_ORDER if fallback != FALLBACK_RELAX_ORIGIN)
    return FALLBACK_ORDER


def _source_stage_for_query(query_stage: str) -> str:
    if query_stage == SEED_ORIGIN_TOP:
        return SOURCE_STAGE_ORIGIN_TOP_SEED
    if query_stage == SEED_QUALITY:
        return SOURCE_STAGE_QUALITY_SEED
    if query_stage == FALLBACK_BASE:
        return SOURCE_STAGE_FOCUSED
    return SOURCE_STAGE_FALLBACK


def _query_stage_allowed_for_bucket(
    profile: OnboardingTasteProfile,
    bucket: CandidateFetchBucket,
    query_stage: str,
) -> bool:
    if query_stage == SEED_ORIGIN_TOP:
        return _is_hard_origin_bucket(profile, bucket) and bucket.origin == ORIGIN_DOMESTIC
    if query_stage == SEED_QUALITY:
        return True
    return query_stage in _fallback_order_for_bucket(profile, bucket)


def normalize_autofill_strategy(strategy: str | None) -> str:
    text = str(strategy or DEFAULT_AUTOFILL_STRATEGY).strip().casefold()
    if text in SUPPORTED_AUTOFILL_STRATEGIES:
        return text
    return DEFAULT_AUTOFILL_STRATEGY


def _is_mixed_profile(profile: OnboardingTasteProfile) -> bool:
    normalized = profile.normalized()
    values = [
        normalized.media_preference,
        normalized.release_preference,
        normalized.vibe_preference,
        normalized.origin_preference if normalized.ui_language == "ru" else "mixed",
    ]
    return sum(value in {"both", "mixed", None} for value in values) >= 3


def query_stage_order_for_strategy(profile: OnboardingTasteProfile, strategy: str | None) -> tuple[str, ...]:
    normalized_strategy = normalize_autofill_strategy(strategy)
    if normalized_strategy == STRATEGY_BASELINE_QUOTA_FIX:
        return FALLBACK_ORDER
    if normalized_strategy == STRATEGY_FOCUSED_FIRST:
        return (FALLBACK_BASE, *SEED_ORDER, *FALLBACK_ORDER[1:])
    if normalized_strategy == STRATEGY_HYBRID_QUALITY_FOCUSED:
        if _is_mixed_profile(profile):
            return (SEED_ORIGIN_TOP, FALLBACK_BASE, SEED_QUALITY, *FALLBACK_ORDER[1:])
        return (FALLBACK_BASE, *SEED_ORDER, *FALLBACK_ORDER[1:])
    if normalized_strategy == STRATEGY_STRICT_UNDERFILL:
        return (FALLBACK_BASE,)
    return (SEED_ORIGIN_TOP, SEED_QUALITY, *FALLBACK_ORDER)


def _domestic_filter_for_fallback(fallback: str) -> dict[str, str]:
    if fallback in {FALLBACK_RELAX_LANGUAGE, FALLBACK_POPULAR}:
        return {"with_origin_country": "RU"}
    return dict(DOMESTIC_FILTER)


def _relaxation_stage_for_query(query_stage: str, bucket: CandidateFetchBucket) -> int:
    if query_stage == SEED_ORIGIN_TOP:
        return 5 if bucket.origin == ORIGIN_DOMESTIC else 0
    if query_stage == SEED_QUALITY:
        return 0
    stage_map = {
        FALLBACK_BASE: 0,
        FALLBACK_RELAX_ORIGIN: 0,
        FALLBACK_RELAX_ERA: 1,
        FALLBACK_RELAX_VOTES_MID: 2,
        FALLBACK_RELAX_VOTES_LOW: 2,
        FALLBACK_RELAX_VOTES_TINY: 2,
        FALLBACK_RELAX_VOTES_ZERO: 2,
        FALLBACK_RELAX_GENRES: 3,
        FALLBACK_RELAX_LANGUAGE: 4,
        FALLBACK_POPULAR: 5,
    }
    return stage_map.get(query_stage, 0)


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

    relaxation_stage = _relaxation_stage_for_query(fallback, bucket)
    effective_popular = fallback == FALLBACK_POPULAR
    effective_relax_era = relaxation_stage >= 1
    effective_no_genres = fallback in {
        FALLBACK_RELAX_GENRES,
        FALLBACK_RELAX_LANGUAGE,
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

    if effective_any_origin is False:
        if bucket.origin == ORIGIN_DOMESTIC:
            params.update(_domestic_filter_for_fallback(fallback))
        elif bucket.origin == ORIGIN_FOREIGN and bucket.original_language:
            params["with_original_language"] = bucket.original_language

    vote_count = _vote_count_for_fallback(bucket, fallback)
    if vote_count is not None:
        params["vote_count.gte"] = vote_count
    return _endpoint(bucket.media_type), params


def build_quality_seed_request(
    bucket: CandidateFetchBucket,
    *,
    profile: OnboardingTasteProfile,
    seed_stage: str,
    request_index: int,
    current_date: date | None = None,
) -> tuple[str, dict[str, Any]]:
    current_date = current_date or _current_date()
    params: dict[str, Any] = {
        "include_adult": False,
        "language": _ui_language_to_tmdb_locale(profile.ui_language),
        _date_lte_field(bucket.media_type): current_date.isoformat(),
        "page": request_index + 1,
        "sort_by": "vote_average.desc",
        "vote_count.gte": 300 if bucket.media_type == MEDIA_MOVIE else 100,
    }
    if seed_stage == SEED_ORIGIN_TOP:
        params["with_origin_country"] = "RU"
    return _endpoint(bucket.media_type), params


def _origin_countries(result: dict[str, Any]) -> set[str]:
    values = result.get("origin_country") or []
    if isinstance(values, str):
        values = [values]
    return {str(value).strip().upper() for value in values if str(value).strip()}


def _seed_candidate_matches_hard_bucket(
    result: dict[str, Any],
    bucket: CandidateFetchBucket,
    *,
    profile: OnboardingTasteProfile,
    seed_stage: str,
) -> bool:
    if seed_stage == SEED_ORIGIN_TOP:
        return _query_stage_allowed_for_bucket(profile, bucket, seed_stage)
    if seed_stage != SEED_QUALITY:
        return True
    if not _is_hard_origin_bucket(profile, bucket):
        return True
    if bucket.origin == ORIGIN_DOMESTIC:
        return "RU" in _origin_countries(result)
    if bucket.origin == ORIGIN_FOREIGN and bucket.original_language:
        return str(result.get("original_language") or "").strip().casefold() == bucket.original_language
    return True


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
    title_key, original_title_key = _title_field(bucket.media_type)
    if result.get(title_key) in (None, "") and result.get(original_title_key) in (None, ""):
        return "wrong_media"
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


def _result_genre_names(
    result: dict[str, Any],
    media_type: str,
    genre_lookup: dict[str, dict[int, str]],
) -> set[str]:
    names: set[str] = set()
    lookup = genre_lookup.get(media_type, {})
    for genre_id in result.get("genre_ids") or []:
        try:
            name = lookup.get(int(genre_id))
        except (TypeError, ValueError):
            name = None
        if name:
            names.add(str(name))
    return names


def quality_seed_profile_penalty(
    result: dict[str, Any],
    bucket: CandidateFetchBucket,
    *,
    profile: OnboardingTasteProfile,
    genre_lookup: dict[str, dict[int, str]],
) -> tuple[int, list[str]]:
    reasons: list[str] = []
    result_year = _result_year(result, bucket.media_type)
    if profile.release_preference == "new" and result_year is not None and result_year < NEW_START_YEAR:
        reasons.append("old_for_new_profile")

    genre_names = {name.casefold() for name in _result_genre_names(result, bucket.media_type, genre_lookup)}
    if bucket.media_type == MEDIA_MOVIE:
        light_names = {name.casefold() for name in MOVIE_LIGHT_GENRES}
        dark_names = {name.casefold() for name in MOVIE_DARK_GENRES}
    else:
        light_names = {name.casefold() for name in TV_LIGHT_GENRES}
        dark_names = {name.casefold() for name in TV_DARK_GENRES}
    if profile.vibe_preference == VIBE_LIGHT and genre_names & dark_names:
        reasons.append("heavy_genre_for_light_profile")
    if profile.vibe_preference == VIBE_DARK and genre_names & light_names and not genre_names & dark_names:
        reasons.append("light_genre_for_dark_profile")

    return 750 * len(reasons), reasons


def candidate_score_debug(
    result: dict[str, Any],
    bucket: CandidateFetchBucket,
    *,
    page: int,
    index_on_page: int,
    source_stage: str = SOURCE_STAGE_FOCUSED,
    quality_seed_penalty: int = 0,
) -> dict[str, Any]:
    vote_average = float(result.get("vote_average") or 0)
    vote_count = float(result.get("vote_count") or 0)
    popularity = float(result.get("popularity") or 0)
    base_score = 100000
    base_quality = vote_average * 100
    vote_bonus = min(math.log10(max(vote_count, 1)) * 100, 500)
    popularity_bonus = min(popularity, 500)
    bucket_priority_bonus = int(bucket.quota_weight * 10_000)
    result_year = _result_year(result, bucket.media_type) or 0
    release_bonus = 0
    if bucket.era == ERA_NEW_SWEEP:
        release_bonus = max(0, result_year - 2021) * 20
    source_bonus = 0
    if source_stage == SOURCE_STAGE_ORIGIN_TOP_SEED:
        source_bonus = 20
    fallback_penalty = 0
    if source_stage == SOURCE_STAGE_FALLBACK:
        fallback_penalty = 40
    diversity_penalty = int(page) * 20 + int(index_on_page)
    final_score = round(
        base_score
        + bucket_priority_bonus
        + base_quality
        + vote_bonus
        + popularity_bonus
        + release_bonus
        + source_bonus
        - fallback_penalty
        - diversity_penalty
        - int(quality_seed_penalty),
        4,
    )
    return {
        "base_quality": round(base_quality, 4),
        "vote_bonus": round(vote_bonus, 4),
        "popularity_bonus": round(popularity_bonus, 4),
        "media_bonus": bucket_priority_bonus,
        "origin_bonus": 0,
        "release_bonus": release_bonus,
        "vibe_bonus": 0,
        "source_bonus": source_bonus,
        "fallback_penalty": fallback_penalty,
        "diversity_penalty": diversity_penalty,
        "quality_seed_penalty": int(quality_seed_penalty),
        "final_score": final_score,
    }


def compute_candidate_score(
    result: dict[str, Any],
    bucket: CandidateFetchBucket,
    *,
    page: int,
    index_on_page: int,
    source_stage: str = SOURCE_STAGE_FOCUSED,
    quality_seed_penalty: int = 0,
) -> float:
    return float(
        candidate_score_debug(
            result,
            bucket,
            page=page,
            index_on_page=index_on_page,
            source_stage=source_stage,
            quality_seed_penalty=quality_seed_penalty,
        )["final_score"]
    )


def build_candidate_record_from_result(
    result: dict[str, Any],
    bucket: CandidateFetchBucket,
    *,
    genre_lookup: dict[str, dict[int, str]],
    profile_id: int,
    candidate_score: float,
    fetch_rank: int,
    fallback: str = FALLBACK_BASE,
    source_stage: str = SOURCE_STAGE_FOCUSED,
    score_debug: dict[str, Any] | None = None,
    quality_seed_penalty_reasons: list[str] | None = None,
) -> dict[str, Any]:
    title_key, original_title_key = _title_field(bucket.media_type)
    date_key = _date_field(bucket.media_type)
    genre_names = [
        genre_lookup.get(bucket.media_type, {}).get(int(genre_id))
        for genre_id in result.get("genre_ids") or []
        if str(genre_id).strip().lstrip("-").isdigit()
    ]
    genre_names = [name for name in genre_names if name]
    country_codes = list(result.get("origin_country") or [])
    if bucket.origin == ORIGIN_DOMESTIC and "RU" not in country_codes:
        country_codes.append("RU")

    candidate = {
        "media_type": bucket.media_type,
        "source": "onboarding_autofill",
        "source_provider": "tmdb",
        "source_version": 3,
        "source_bucket_id": bucket.bucket_id,
        "source_stage": source_stage,
        "origin_bucket": bucket.origin,
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
            "original_language": bucket.original_language,
            "fallback": fallback,
            "source_stage": source_stage,
            "relaxation_stage": _relaxation_stage_for_query(fallback, bucket),
        },
        "signals": ["onboarding_autofill"],
    }
    if score_debug is not None:
        candidate["score_debug"] = dict(score_debug)
    if quality_seed_penalty_reasons:
        candidate["quality_seed_penalty_reasons"] = list(quality_seed_penalty_reasons)
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
        "origin": totals("origin"),
        "original_language": totals("original_language"),
    }


def actual_counts_for_candidates(candidates: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    counters = {
        "media_type": Counter(),
        "release": Counter(),
        "vibe": Counter(),
        "origin": Counter(),
        "original_language": Counter(),
        "fallback": Counter(),
        "source_stage": Counter(),
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
        origin = candidate.get("origin_bucket") or source_query.get("origin")
        if origin:
            counters["origin"][str(origin)] += 1
        language = source_query.get("original_language") or candidate.get("original_language")
        if language:
            counters["original_language"][str(language)] += 1
        fallback = source_query.get("fallback")
        if fallback:
            counters["fallback"][str(fallback)] += 1
        source_stage = candidate.get("source_stage") or source_query.get("source_stage")
        if source_stage:
            counters["source_stage"][str(source_stage)] += 1
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
    strategy: str | None = None,
) -> AutofillResult:
    profile = profile.normalized()
    strategy = normalize_autofill_strategy(strategy)
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
    rejection_counts: Counter[str] = Counter()
    request_cache: dict[str, dict[str, Any]] = {}
    request_stats: Counter[str] = Counter()
    source_stage_counts: Counter[str] = Counter()
    quality_seed_limit = int(STARTER_POOL_TARGET * QUALITY_SEED_MAX_SHARE)

    def is_cancelled() -> bool:
        return bool(cancel_checker is not None and cancel_checker())

    def target_deficit(state: _BucketState) -> dict[str, int]:
        bucket = state.bucket
        origin_deficit = 0
        if _is_hard_origin_bucket(profile, bucket):
            origin_deficit = sum(_state_remaining(item) for item in states if item.bucket.origin == bucket.origin)
        return {
            "bucket": _state_remaining(state),
            "media": sum(_state_remaining(item) for item in states if item.bucket.media_type == bucket.media_type),
            "origin": origin_deficit,
        }

    for query_stage in query_stage_order_for_strategy(profile, strategy):
        for state in states:
            state.request_index = 0
            state.exhausted = False
        while len(created_candidates) < STARTER_POOL_TARGET and api_requests < MAX_TMDB_REQUESTS:
            progressed = False
            for state in sorted(states, key=lambda item: _state_deficit_priority_key(profile, item, states)):
                if len(created_candidates) >= STARTER_POOL_TARGET or api_requests >= MAX_TMDB_REQUESTS:
                    break
                if state.filled >= state.bucket.quota or state.exhausted:
                    continue
                if not _query_stage_allowed_for_bucket(profile, state.bucket, query_stage):
                    continue
                if is_cancelled():
                    cancelled = True
                    break
                bucket = state.bucket
                source_stage = _source_stage_for_query(query_stage)
                if source_stage == SOURCE_STAGE_QUALITY_SEED:
                    quality_seed_bucket_limit = max(0, int(bucket.quota) - 1)
                    if (
                        source_stage_counts[SOURCE_STAGE_QUALITY_SEED] >= quality_seed_limit
                        or state.filled >= quality_seed_bucket_limit
                    ):
                        rejection_counts["quality_seed_limit_applied"] += 1
                        request_stats["quality_seed_limit_applied"] = 1
                        state.exhausted = True
                        continue
                if query_stage in SEED_ORDER:
                    endpoint, params = build_quality_seed_request(
                        bucket,
                        profile=profile,
                        seed_stage=query_stage,
                        request_index=state.request_index,
                        current_date=current_date,
                    )
                else:
                    endpoint, params = build_discover_request(
                        bucket,
                        profile=profile,
                        fallback=query_stage,
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
                    fallback=query_stage,
                    source_stage=source_stage,
                    strategy=strategy,
                )
                accepted_batch: list[dict[str, Any]] = []
                rejected_count = 0
                status = "ok"
                error_text = None
                page = int(params.get("page") or 1)
                request_key = canonical_discover_request_key(endpoint, params)
                cache_hit = False
                quality_limit_reached = False
                try:
                    request_stats["requests_total"] += 1
                    if request_key in request_cache:
                        payload = copy.deepcopy(request_cache[request_key])
                        cache_hit = True
                        status = "cache_hit"
                        request_stats["cache_hits"] += 1
                        request_stats["requests_duplicate_skipped"] += 1
                    else:
                        request_stats["requests_unique"] += 1
                        api_requests += 1
                        payload = client.discover(endpoint, params)
                        request_cache[request_key] = copy.deepcopy(payload)
                    results = payload.get("results") if isinstance(payload, dict) else []
                    results = results if isinstance(results, list) else []
                    if not results:
                        request_stats["zero_result_requests"] += 1
                        state.exhausted = True
                    for index_on_page, result in enumerate(results):
                        if len(created_candidates) + len(accepted_batch) >= STARTER_POOL_TARGET:
                            break
                        if state.filled + len(accepted_batch) >= state.bucket.quota:
                            break
                        if source_stage == SOURCE_STAGE_QUALITY_SEED:
                            if source_stage_counts[SOURCE_STAGE_QUALITY_SEED] + len(accepted_batch) >= quality_seed_limit:
                                quality_limit_reached = True
                                request_stats["quality_seed_limit_applied"] = 1
                                break
                            if state.filled + len(accepted_batch) >= max(0, int(state.bucket.quota) - 1):
                                quality_limit_reached = True
                                request_stats["quality_seed_limit_applied"] = 1
                                break
                        if query_stage in SEED_ORDER and not _seed_candidate_matches_hard_bucket(
                            result,
                            bucket,
                            profile=profile,
                            seed_stage=query_stage,
                        ):
                            rejection_counts["quota_mismatch"] += 1
                            rejected_count += 1
                            continue
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
                            rejection_counts[rejection_reason] += 1
                            if rejection_reason == "future":
                                rejected_future_count += 1
                            rejected_count += 1
                            continue
                        fetch_rank += 1
                        quality_seed_penalty = 0
                        quality_seed_penalty_reasons: list[str] = []
                        if source_stage == SOURCE_STAGE_QUALITY_SEED:
                            quality_seed_penalty, quality_seed_penalty_reasons = quality_seed_profile_penalty(
                                result,
                                bucket,
                                profile=profile,
                                genre_lookup=genre_lookup,
                            )
                            if quality_seed_penalty_reasons:
                                rejection_counts["quality_seed_penalized"] += 1
                        score_debug = candidate_score_debug(
                            result,
                            bucket,
                            page=page,
                            index_on_page=index_on_page,
                            source_stage=source_stage,
                            quality_seed_penalty=quality_seed_penalty,
                        )
                        candidate_score = float(score_debug["final_score"])
                        candidate = build_candidate_record_from_result(
                            result,
                            bucket,
                            genre_lookup=genre_lookup,
                            profile_id=profile_id,
                            candidate_score=candidate_score,
                            fetch_rank=fetch_rank,
                            fallback=query_stage,
                            source_stage=source_stage,
                            score_debug=score_debug,
                            quality_seed_penalty_reasons=quality_seed_penalty_reasons,
                        )
                        accepted_batch.append(candidate)
                        accepted_identities.add((bucket.media_type, int(result["id"])))
                        state.filled += 1
                    total_pages = int((payload or {}).get("total_pages") or page)
                    if page >= total_pages:
                        state.exhausted = True
                    if quality_limit_reached:
                        state.exhausted = True
                except Exception as error:
                    status = "error"
                    error_text = str(error)
                    state.exhausted = True
                finally:
                    save_autofill_request_audit(
                        {
                            "onboarding_profile_id": profile_id,
                            "bucket_id": bucket.bucket_id,
                            "endpoint": endpoint,
                            "params": {
                                **params,
                                "_fallback": query_stage,
                                "_source_stage": source_stage,
                                "_cache_hit": cache_hit,
                                "_request_cache_key": request_key,
                                "_relaxation_stage": _relaxation_stage_for_query(query_stage, bucket),
                                "_target_deficit": target_deficit(state),
                            },
                            "page": page,
                            "status": status,
                            "accepted_count": len(accepted_batch),
                            "rejected_count": rejected_count,
                            "error_text": error_text,
                        },
                        path=path,
                    )
                state.request_index += 1
                if query_stage in SEED_ORDER and state.request_index >= 1:
                    state.exhausted = True
                progressed = True
                if accepted_batch:
                    _emit(progress_callback, stage=4, message="Убираем повторы", profile_id=profile_id)
                    created_candidates.extend(accepted_batch)
                    source_stage_counts[source_stage] += len(accepted_batch)
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
    source_stats = dict(actual_counts.get("source_stage", {}))
    request_stats_summary = {
        "requests_total": int(request_stats.get("requests_total", 0)),
        "requests_unique": int(request_stats.get("requests_unique", 0)),
        "requests_duplicate_skipped": int(request_stats.get("requests_duplicate_skipped", 0)),
        "zero_result_requests": int(request_stats.get("zero_result_requests", 0)),
        "cache_hits": int(request_stats.get("cache_hits", 0)),
        "quality_seed_limit_applied": int(request_stats.get("quality_seed_limit_applied", 0)),
    }
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
        strategy=strategy,
    )
    return AutofillResult(
        ok=cancelled is False,
        strategy=strategy,
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
        source_stats=source_stats,
        rejection_counts=dict(rejection_counts),
        request_stats=request_stats_summary,
        rejected_future_count=rejected_future_count,
    )

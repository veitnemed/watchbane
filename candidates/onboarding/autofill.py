"""Deterministic TMDb onboarding autofill for the starter candidate pool."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
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
MAX_TMDB_REQUESTS = 60
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
    profile_id: int
    created_count: int
    pool_size: int
    api_requests: int
    cancelled: bool
    warning: str | None
    candidates: list[dict[str, Any]]


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
) -> tuple[str, dict[str, Any]]:
    current_year = current_year or _current_year()
    params: dict[str, Any] = {
        "include_adult": False,
        "language": _ui_language_to_tmdb_locale(profile.ui_language),
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
    effective_any_origin = fallback != FALLBACK_BASE

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
            params.update(DOMESTIC_FILTER)
        elif bucket.origin == ORIGIN_FOREIGN and bucket.original_language:
            params["with_original_language"] = bucket.original_language

    vote_count = _vote_count_for_fallback(bucket, fallback)
    if vote_count is not None:
        params["vote_count.gte"] = vote_count
    return _endpoint(bucket.media_type), params


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


def accept_candidate(
    result: dict[str, Any],
    bucket: CandidateFetchBucket,
    *,
    existing_index: dict[str, Any],
    accepted_identities: set[tuple[str, int]],
    hidden_or_rejected_identities: set[str],
    watched_signatures: set[str],
    dataset_title_keys: set[str],
) -> bool:
    tmdb_id = result.get("id")
    if tmdb_id in (None, ""):
        return False
    try:
        normalized_tmdb_id = int(tmdb_id)
    except (TypeError, ValueError):
        return False
    if result.get("poster_path") in (None, ""):
        return False
    vote_average = _result_number(result, "vote_average")
    vote_count = _result_number(result, "vote_count")
    if vote_average is None or vote_count is None:
        return False
    if vote_average < 5.8:
        return False
    if bucket.era == ERA_TOP_ALL_TIME and vote_count < _base_vote_count(bucket):
        return False
    if (bucket.media_type, normalized_tmdb_id) in accepted_identities:
        return False
    if discover_item_existing_reason(result, existing_index, media_type=bucket.media_type) is not None:
        return False

    candidate_stub = _discover_candidate_stub(result, bucket.media_type)
    if is_watched_candidate(
        candidate_stub,
        watched_signatures=watched_signatures,
        dataset_title_keys=dataset_title_keys,
    ):
        return False
    if title_identity_key(candidate_stub) in hidden_or_rejected_identities:
        return False
    return True


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


def should_start_onboarding_autofill(*, path: str | Path | None = None) -> bool:
    if has_completed_onboarding_profile(path=path):
        return False
    return len(_pool_snapshot(path=path)) == 0


def _warning_for_count(created_count: int) -> str | None:
    if created_count >= STARTER_POOL_MIN_ACCEPTABLE:
        return None
    return f"Удалось собрать только {created_count} кандидатов. Можно пополнить пул позже."


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
    states = [_BucketState(bucket=bucket) for bucket in sorted(buckets, key=lambda item: bucket_priority_key(item, profile))]
    api_requests = 0
    fetch_rank = 0

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
                accepted_batch: list[dict[str, Any]] = []
                rejected_count = 0
                status = "ok"
                error_text = None
                page = int(params.get("page") or 1)
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
                        if accept_candidate(
                            result,
                            bucket,
                            existing_index=existing_index,
                            accepted_identities=accepted_identities,
                            hidden_or_rejected_identities=hidden_or_rejected,
                            watched_signatures=watched_signatures,
                            dataset_title_keys=dataset_title_keys,
                        ) is False:
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
                            "params": params,
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
    warning = _warning_for_count(len(created_candidates))
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
    )

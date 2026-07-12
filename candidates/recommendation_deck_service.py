"""Build stable local recommendation decks from the shared candidate pool."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from enum import IntEnum
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Callable, Literal
from uuid import uuid4

from candidates.search.filtering import candidate_matches
from candidates.models import genre_schema
from candidates.models.keys import (
    candidate_state_identity_key,
    candidate_state_identity_keys,
    title_identity_key,
)
from candidates.models.schema import coerce_candidate_number, normalize_candidate_record
from candidates.pool.storage import candidate_tmdb_identity
from candidates.preferences import (
    RecommendationVector,
    resolve_diversity_window,
    resolve_exploration_ratio,
    resolve_rarity_weights,
)
from candidates.repositories.pool_repository import load_candidate_pool
from candidates.scoring.rating_confidence import has_unknown_rating, is_viable_unrated_candidate
from candidates.sources.tmdb.scoring import compute_tmdb_quality_score
from candidates import title_state_service
from dataset.models.media_type import normalize_media_type
from dataset.models.user_rating import normalize_user_rating
from storage.sqlite import (
    action_repository,
    impression_repository,
    recommendation_deck_repository,
)
from storage.sqlite.connection import connect
from storage.sqlite.migrations import apply_migrations


PoolLoader = Callable[[], dict]
ACTIVE_DECK_SIZE = 25
DEFAULT_ACTIVE_LIMIT = ACTIVE_DECK_SIZE
DEFAULT_RESERVE_SIZE = 70
DEFAULT_RECENT_DAYS = 30
DEFAULT_REFILL_THRESHOLD = 20
DEFAULT_UNKNOWN_RATING_LIMIT = 6
EXPANDED_UNKNOWN_RATING_LIMIT = 12
DEFAULT_EXPLORATION_RATIO = 0.2
DECK_STATE_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class DeckReserveSnapshot:
    remaining: int
    fresh_eligible: int
    target: int
    ratio: float
    display_count: int
    percent: int
    band: Literal["ready", "low", "critical", "empty"]
    empty_reason: Literal["processed", "recent_fallback", "pool_empty", None]


def compute_deck_reserve_snapshot(deck: dict) -> DeckReserveSnapshot:
    """Compute reserve UI metrics from a materialized recommendation deck."""
    active = deck.get("active") or []
    reserve = deck.get("reserve") or []
    materialized = len(active) + len(reserve)
    catalog_eligible = max(0, int(deck.get("catalog_eligible_count") or materialized))
    fresh_eligible = max(
        0,
        int(deck.get("fresh_eligible_count") or 0),
        catalog_eligible - materialized,
    )
    remaining = materialized + fresh_eligible
    target = 45
    ratio = min(float(remaining) / float(target), 1.0)
    display_count = min(remaining, target)
    percent = int(round(ratio * 100))
    if remaining == 0:
        band: Literal["ready", "low", "critical", "empty"] = "empty"
        excluded = deck.get("excluded") if isinstance(deck.get("excluded"), dict) else {}
        if deck.get("last_action"):
            empty_reason: Literal["processed", "recent_fallback", "pool_empty", None] = "processed"
        elif int(excluded.get("recently_seen") or 0) > 0:
            empty_reason = "recent_fallback"
        else:
            empty_reason = "pool_empty"
    elif remaining >= 45:
        band = "ready"
        empty_reason = None
    elif remaining >= 25:
        band = "low"
        empty_reason = None
    else:
        band = "critical"
        empty_reason = None
    return DeckReserveSnapshot(
        remaining=remaining,
        fresh_eligible=fresh_eligible,
        target=target,
        ratio=ratio,
        display_count=display_count,
        percent=percent,
        band=band,
        empty_reason=empty_reason,
    )


class RelevanceTier(IntEnum):
    """Small internal ordering for explicit recommendation intent."""

    A = 0
    B = 1
    C = 2
    D = 3


_MOOD_RELEVANCE_PROFILES = {
    "dark": {
        "exact": frozenset({"crime", "mystery", "thriller"}),
        "adjacent": frozenset({"drama", "horror", "film_noir"}),
        "incompatible": frozenset({
            "comedy",
            "family",
            "reality",
            "romance",
            "talk_show",
            "news",
            "game_show",
        }),
    },
    "light": {
        "exact": frozenset({"comedy", "family", "animation"}),
        "adjacent": frozenset({"romance", "drama", "music", "musical"}),
        "incompatible": frozenset({"crime", "horror", "thriller", "war", "film_noir"}),
    },
    "dynamic": {
        "exact": frozenset({"action_adventure", "thriller"}),
        "adjacent": frozenset({"crime", "sci_fi_fantasy", "war", "western"}),
        "incompatible": frozenset({"reality", "talk_show", "news", "game_show"}),
    },
    "drama": {
        "exact": frozenset({"drama", "romance"}),
        "adjacent": frozenset({"crime", "mystery", "history", "biography"}),
        "incompatible": frozenset({"reality", "talk_show", "news", "game_show"}),
    },
}


def _as_utc(value: datetime | date) -> datetime:
    if isinstance(value, datetime):
        current = value
    elif isinstance(value, date):
        current = datetime.combine(value, time.min)
    else:
        raise TypeError("now must be a date or datetime")
    if current.tzinfo is None:
        return current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc)


def _identity(candidate: dict) -> tuple[str, str]:
    return title_identity_key(candidate), normalize_media_type(candidate.get("media_type"))


def _stable_identity(candidate: dict) -> tuple[str, str, str]:
    tmdb_identity = candidate_tmdb_identity(candidate)
    if tmdb_identity is not None:
        media_type, tmdb_id = tmdb_identity
        return "tmdb", media_type, str(tmdb_id)
    title_key, media_type = _identity(candidate)
    return "title", media_type, title_key


def _number(value) -> float | None:
    result = coerce_candidate_number(value)
    if result is None or isinstance(result, bool):
        return None
    return float(result)


def _score_percent(field_name: str, value: float) -> float:
    if field_name == "tmdb_score" and value <= 10.0:
        return value * 10.0
    if 0.0 <= value <= 1.0:
        return value * 100.0
    return value


def _base_score(candidate: dict) -> float:
    if has_unknown_rating(candidate):
        for field in ("final_score", "candidate_score", "quality_score"):
            score = _number(candidate.get(field))
            if score is not None:
                return _score_percent(field, score)
        return compute_tmdb_quality_score(candidate) * 100.0
    for field in ("final_score", "candidate_score", "quality_score", "tmdb_score"):
        score = _number(candidate.get(field))
        if score is not None:
            return _score_percent(field, score)
    return 0.0


def _personal_fit_score(candidate: dict) -> float:
    """Use only explicit per-candidate fit fields; watched alone is never positive."""
    for field_name in ("personal_fit_score", "preference_score", "affinity_score"):
        value = _number(candidate.get(field_name))
        if value is not None:
            return _score_percent(field_name, value)
    return 0.0


def _preference_values(preferences: dict, *field_names: str) -> list[str]:
    for field_name in field_names:
        if field_name not in preferences:
            continue
        values: Any = preferences.get(field_name)
        if values in (None, ""):
            continue
        if not isinstance(values, (list, tuple, set)):
            values = [values]
        return [str(value).strip() for value in values if str(value or "").strip()]
    return []


def _coerce_vector(
    vector: RecommendationVector | dict | None,
    legacy_preferences: dict | None = None,
) -> RecommendationVector:
    if isinstance(vector, RecommendationVector):
        return vector.normalized()
    if isinstance(vector, dict):
        if {"openness_level", "rarity_level", "diversity_level", "mood"} & set(vector):
            return RecommendationVector.from_dict(vector)
        legacy_preferences = vector
    legacy = dict(legacy_preferences or {})
    mood = str(
        legacy.get("_recommendation_mood")
        or legacy.get("mood")
        or legacy.get("vibe")
        or "any"
    ).strip().casefold()
    return RecommendationVector(mood="any" if mood == "mixed" else mood).normalized()


def _recommendation_profile(
    vector: RecommendationVector | dict | None,
) -> tuple[frozenset[str], frozenset[str], frozenset[str], bool]:
    mood = _coerce_vector(vector).mood
    if mood == "any":
        mood = ""
    mood_profile = _MOOD_RELEVANCE_PROFILES.get(mood, {})
    exact = set(mood_profile.get("exact") or ())
    adjacent = set(mood_profile.get("adjacent") or ()) - exact
    incompatible = set(mood_profile.get("incompatible") or ()) - exact
    explicit = bool(exact or mood_profile)
    return frozenset(exact), frozenset(adjacent), frozenset(incompatible), explicit


def _has_relevance_intent(vector: RecommendationVector | dict | None) -> bool:
    return _recommendation_profile(vector)[3]


def _relevance_tier(candidate: dict, vector: RecommendationVector | dict | None) -> RelevanceTier:
    exact, adjacent, incompatible, explicit = _recommendation_profile(vector)
    if explicit is False:
        return RelevanceTier.A
    normalized = normalize_candidate_record(candidate)
    genres = set(genre_schema.normalize_genre_filter_list(normalized.get("genre_keys") or []))
    if genres & exact:
        return RelevanceTier.A
    if genres & adjacent:
        return RelevanceTier.C if genres & incompatible else RelevanceTier.B
    if genres & incompatible:
        return RelevanceTier.D
    return RelevanceTier.C


def _exploration_allowance(ab_count: int, capacity: int, ratio: float = DEFAULT_EXPLORATION_RATIO) -> int:
    if ab_count <= 0 or capacity <= 0:
        return 0
    ratio = max(0.0, min(0.95, float(ratio)))
    if ratio <= 0:
        return 0
    capacity_limit = int(capacity * ratio)
    balance_limit = int(ab_count * ratio / (1.0 - ratio))
    return max(0, min(capacity_limit, balance_limit))


def _automatic_ranked_candidates(
    ranked: list[dict],
    vector: RecommendationVector | dict | None,
    *,
    capacity: int,
) -> list[dict]:
    current_vector = _coerce_vector(vector)
    if _has_relevance_intent(current_vector) is False:
        return list(ranked)
    close = [
        candidate
        for candidate in ranked
        if _relevance_tier(candidate, current_vector) <= RelevanceTier.B
    ]
    exploratory = [
        candidate
        for candidate in ranked
        if _relevance_tier(candidate, current_vector) == RelevanceTier.C
    ]
    ratio = resolve_exploration_ratio(current_vector.openness_level)
    return close + exploratory[: _exploration_allowance(len(close), capacity, ratio)]


def count_automatic_recommendation_candidates(
    candidates: list[dict],
    vector: RecommendationVector | dict | None,
    *,
    capacity: int = DEFAULT_ACTIVE_LIMIT + DEFAULT_RESERVE_SIZE,
) -> int:
    """Count the local A/B slice plus its bounded exploratory allowance."""
    current_vector = _coerce_vector(vector)
    if _has_relevance_intent(current_vector) is False:
        return len(candidates)
    close_count = sum(
        _relevance_tier(candidate, current_vector) <= RelevanceTier.B
        for candidate in candidates
    )
    exploratory_count = sum(
        _relevance_tier(candidate, current_vector) == RelevanceTier.C
        for candidate in candidates
    )
    ratio = resolve_exploration_ratio(current_vector.openness_level)
    return close_count + min(exploratory_count, _exploration_allowance(close_count, capacity, ratio))


def _stable_hash(day_seed: str, candidate: dict) -> str:
    identity_key, media_type = _identity(candidate)
    return hashlib.sha256(f"{day_seed}|{identity_key}|{media_type}".encode("utf-8")).hexdigest()


def _first_genre(candidate: dict) -> str:
    for field in ("genres_tmdb", "genres", "genre_names", "genre_ids"):
        values = candidate.get(field)
        if isinstance(values, (list, tuple)) and values:
            return str(values[0]).strip().casefold()
    return ""


def _country(candidate: dict) -> str:
    value = (
        candidate.get("country_codes")
        or candidate.get("countries")
        or candidate.get("country")
        or candidate.get("origin_country")
        or ""
    )
    if isinstance(value, (list, tuple)):
        value = value[0] if value else ""
    return str(value).strip().upper()


def _decade(candidate: dict) -> int | None:
    year = _number(candidate.get("year"))
    return None if year is None else int(year) // 10 * 10


def _diversify_quality_group(
    candidates: list[dict],
    day_seed: str,
    *,
    window_size: int = 12,
) -> list[dict]:
    remaining = sorted(candidates, key=lambda item: _stable_hash(day_seed, item))
    result: list[dict] = []
    media_counts: dict[str, int] = {}
    genre_counts: dict[str, int] = {}
    country_counts: dict[str, int] = {}
    decade_counts: dict[int | None, int] = {}
    while remaining:
        window = remaining[: min(max(1, int(window_size)), len(remaining))]

        def diversity_key(item: dict) -> tuple[int, str]:
            media_type = normalize_media_type(item.get("media_type"))
            genre = _first_genre(item)
            country = _country(item)
            decade = _decade(item)
            penalty = (
                media_counts.get(media_type, 0)
                + genre_counts.get(genre, 0)
                + country_counts.get(country, 0)
                + decade_counts.get(decade, 0)
            )
            return penalty, _stable_hash(day_seed, item)

        selected = min(window, key=diversity_key)
        remaining.remove(selected)
        result.append(selected)
        media_type = normalize_media_type(selected.get("media_type"))
        genre = _first_genre(selected)
        country = _country(selected)
        decade = _decade(selected)
        media_counts[media_type] = media_counts.get(media_type, 0) + 1
        genre_counts[genre] = genre_counts.get(genre, 0) + 1
        country_counts[country] = country_counts.get(country, 0) + 1
        decade_counts[decade] = decade_counts.get(decade, 0) + 1
    return result


def _popularity_score(candidate: dict) -> float:
    popularity = _number(candidate.get("tmdb_popularity"))
    if popularity is None or popularity <= 0:
        return 0.0
    return min(100.0, 100.0 * math.log1p(popularity) / math.log1p(500.0))


def _hidden_gem_score(candidate: dict) -> float:
    if has_unknown_rating(candidate):
        return 0.0
    value = _number(candidate.get("hidden_gem_score"))
    if value is None:
        return 0.0
    return _score_percent("hidden_gem_score", value)


def _vector_score(candidate: dict, vector: RecommendationVector | dict | None) -> float:
    base_weight, hidden_weight, popularity_weight = resolve_rarity_weights(
        _coerce_vector(vector).rarity_level
    )
    return (
        base_weight * _base_score(candidate)
        + hidden_weight * _hidden_gem_score(candidate)
        + popularity_weight * _popularity_score(candidate)
    )


def _rank_candidates(
    candidates: list[dict],
    day_seed: str,
    vector: RecommendationVector | dict | None = None,
) -> list[dict]:
    current_vector = _coerce_vector(vector)
    if current_vector.diversity_level != 2:
        ordered = sorted(
            candidates,
            key=lambda candidate: (
                int(_relevance_tier(candidate, current_vector)),
                -_personal_fit_score(candidate),
                -_vector_score(candidate, current_vector),
                _stable_hash(day_seed, candidate),
            ),
        )
        return _diversify_quality_group(
            ordered,
            day_seed,
            window_size=resolve_diversity_window(current_vector.diversity_level),
        )
    quality_groups: dict[tuple[int, float, float], list[dict]] = {}
    for candidate in candidates:
        group_key = (
            int(_relevance_tier(candidate, current_vector)),
            round(_personal_fit_score(candidate), 6),
            round(_vector_score(candidate, current_vector), 6),
        )
        quality_groups.setdefault(group_key, []).append(candidate)
    ranked: list[dict] = []
    for group_key in sorted(
        quality_groups,
        key=lambda value: (value[0], -value[1], -value[2]),
    ):
        ranked.extend(_diversify_quality_group(quality_groups[group_key], day_seed))
    return ranked


def _unknown_rating_limit(preferences: dict, active_limit: int) -> int:
    collection = str(
        preferences.get("_recommendation_collection")
        or preferences.get("release_preference")
        or ""
    ).strip().casefold()
    countries = preferences.get("country") or preferences.get("countries") or []
    if isinstance(countries, str):
        countries = [countries]
    has_explicit_market = any(str(value or "").strip() for value in countries)
    configured = (
        EXPANDED_UNKNOWN_RATING_LIMIT
        if collection == "new" and has_explicit_market
        else DEFAULT_UNKNOWN_RATING_LIMIT
    )
    return min(max(0, int(active_limit)), configured)


def _select_active_with_unknown_quota(
    ranked: list[dict],
    *,
    active_limit: int,
    unknown_limit: int,
    vector: RecommendationVector | dict | None = None,
    initial_active: list[dict] | None = None,
) -> tuple[list[dict], list[dict]]:
    active: list[dict] = list(initial_active or [])[:active_limit]
    remaining: list[dict] = []
    unknown_count = sum(has_unknown_rating(candidate) for candidate in active)
    exploratory_count = sum(
        _relevance_tier(candidate, vector) == RelevanceTier.C
        for candidate in active
    )
    explicit_relevance = _has_relevance_intent(vector)
    for candidate in ranked:
        unknown = has_unknown_rating(candidate)
        exploratory = (
            explicit_relevance
            and _relevance_tier(candidate, vector) == RelevanceTier.C
        )
        exploration_allowed = (
            not exploratory
            or (exploratory_count + 1) * 5 <= len(active) + 1
        )
        if (
            len(active) < active_limit
            and (not unknown or unknown_count < unknown_limit)
            and exploration_allowed
        ):
            active.append(candidate)
            unknown_count += int(unknown)
            exploratory_count += int(exploratory)
        else:
            remaining.append(candidate)
    return active, remaining


def _deck_refill_needed(
    active: list[dict],
    reserve: list[dict],
    *,
    active_limit: int,
    reserve_threshold: int,
) -> bool:
    return len(active) < active_limit or len(reserve) < reserve_threshold


class RecommendationDeckService:
    def __init__(
        self,
        *,
        pool_loader: PoolLoader = load_candidate_pool,
        db_path: str | Path | None = None,
        recent_days: int = DEFAULT_RECENT_DAYS,
        refill_threshold: int = DEFAULT_REFILL_THRESHOLD,
    ) -> None:
        self._pool_loader = pool_loader
        self._db_path = db_path
        self._recent_days = max(0, int(recent_days))
        self._refill_threshold = max(0, int(refill_threshold))
        self._decks: dict[str, dict] = {}
        self._latest_cache_key: str | None = None
        self._latest_deck_id: str | None = None

    @staticmethod
    def _material_signature(
        candidate_filters: dict,
        vector: RecommendationVector | dict | None,
        variation_seed: int,
    ) -> str:
        current_vector = _coerce_vector(vector, candidate_filters)
        return json.dumps(
            {
                "candidate_filters": dict(candidate_filters or {}),
                "recommendation_vector": current_vector.to_dict(),
                "variation_seed": max(0, int(variation_seed or 0)),
            },
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )

    def _remember_deck(self, deck: dict, *, reason: str) -> None:
        snapshot = deepcopy(deck)
        snapshot["state_schema_version"] = DECK_STATE_SCHEMA_VERSION
        snapshot["material_signature"] = self._material_signature(
            dict(snapshot.get("candidate_filters") or snapshot.get("preferences") or {}),
            snapshot.get("recommendation_vector"),
            int(snapshot.get("variation_seed") or 0),
        )
        snapshot["last_change_reason"] = reason
        snapshot["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        deck.clear()
        deck.update(snapshot)
        deck_id = str(deck["deck_id"])
        self._decks = {deck_id: deck}
        self._latest_cache_key = snapshot["material_signature"]
        self._latest_deck_id = deck_id
        recommendation_deck_repository.save_current_deck(snapshot, path=self._db_path)

    def _load_persisted_deck(self, material_signature: str) -> dict | None:
        snapshot = recommendation_deck_repository.load_current_deck(path=self._db_path)
        if not isinstance(snapshot, dict):
            return None
        if snapshot.get("state_schema_version") != DECK_STATE_SCHEMA_VERSION:
            return None
        if snapshot.get("material_signature") != material_signature:
            return None
        deck_id = str(snapshot.get("deck_id") or "").strip()
        if not deck_id or not isinstance(snapshot.get("active"), list) or not isinstance(
            snapshot.get("reserve"), list
        ):
            return None
        self._decks = {deck_id: snapshot}
        self._latest_cache_key = material_signature
        self._latest_deck_id = deck_id
        return snapshot

    def record_detail_reveal(
        self,
        deck_id: str,
        candidate: dict,
        *,
        shown_at: str | None = None,
    ) -> bool:
        """Record one actual detail reveal per candidate within a persisted deck."""
        deck = self._decks.get(str(deck_id))
        if deck is None:
            raise KeyError(f"Unknown recommendation deck: {deck_id}")
        identity = _stable_identity(candidate)
        if identity not in {
            _stable_identity(item) for item in (deck.get("active") or [])
        }:
            return False
        identity_token = "|".join(identity)
        revealed = {
            str(item) for item in (deck.get("revealed_identities") or []) if str(item)
        }
        if identity_token in revealed:
            return False

        snapshot = deepcopy(deck)
        revealed.add(identity_token)
        snapshot["revealed_identities"] = sorted(revealed)
        snapshot["last_selected_identity"] = identity_token
        snapshot["last_selected_pool_key"] = str(candidate.get("pool_entry_key") or "")
        snapshot["last_change_reason"] = "detail_reveal"
        snapshot["updated_at"] = str(
            shown_at or datetime.now(timezone.utc).isoformat(timespec="seconds")
        )
        conn = connect(self._db_path)
        try:
            apply_migrations(conn)
            with conn:
                recommendation_deck_repository.save_current_deck(snapshot, conn=conn)
                impression_repository.record_impressions(
                    [candidate],
                    deck_id=str(deck_id),
                    shown_at=shown_at,
                    conn=conn,
                )
        finally:
            conn.close()
        deck.clear()
        deck.update(snapshot)
        return True

    def _watched_identities(
        self,
    ) -> tuple[set[tuple[str, str]], set[tuple[str, int]]]:
        conn = connect(self._db_path)
        try:
            apply_migrations(conn)
            title_identities: set[tuple[str, str]] = set()
            tmdb_identities: set[tuple[str, int]] = set()
            for row in conn.execute(
                "SELECT title, year, media_type, tmdb_id FROM watched_records WHERE payload_json != '{}'"
            ):
                candidate = {
                    "title": row["title"],
                    "year": row["year"],
                    "media_type": row["media_type"],
                    "tmdb_id": row["tmdb_id"],
                }
                title_identities.add(_identity(candidate))
                tmdb_identity = candidate_tmdb_identity(candidate)
                if tmdb_identity is not None:
                    tmdb_identities.add(tmdb_identity)
            return title_identities, tmdb_identities
        finally:
            conn.close()

    def _excluded_action_identities(
        self,
    ) -> tuple[set[str], set[tuple[str, int]]]:
        identities: set[str] = set()
        tmdb_identities: set[tuple[str, int]] = set()
        for action in (action_repository.ACTION_WATCHLIST, action_repository.ACTION_HIDDEN):
            identities.update(action_repository.load_action_identities(action, path=self._db_path))
            for candidate in title_state_service.load_action_candidates(action, path=self._db_path):
                tmdb_identity = candidate_tmdb_identity(candidate)
                if tmdb_identity is not None:
                    tmdb_identities.add(tmdb_identity)
        return identities, tmdb_identities

    def _recent_identities(self, now: datetime) -> set[tuple[str, str]]:
        cutoff = (now - timedelta(days=self._recent_days)).isoformat(timespec="seconds")
        return {
            (str(row["identity_key"]), normalize_media_type(row["media_type"]))
            for row in impression_repository.get_recently_seen(cutoff, path=self._db_path)
        }

    def _eligible_candidates(
        self,
        preferences: dict,
        now: datetime,
    ) -> tuple[list[dict], list[dict], dict[str, int]]:
        pool = self._pool_loader()
        source = list(pool.values()) if isinstance(pool, dict) else list(pool or [])
        watched, watched_tmdb = self._watched_identities()
        excluded_actions, excluded_action_tmdb = self._excluded_action_identities()
        recently_seen = self._recent_identities(now)
        criteria = dict(preferences or {})
        criteria["only_unwatched"] = False
        criteria["hide_hidden"] = False
        seen: set[tuple[str, str, str]] = set()
        eligible: list[dict] = []
        recent_fallback: list[dict] = []
        counters = {
            "pool_total": len(source),
            "watched": 0,
            "actioned": 0,
            "recently_seen": 0,
            "future_release": 0,
            "duplicate": 0,
            "preferences": 0,
            "quality_gate": 0,
        }
        for raw_candidate in source:
            if not isinstance(raw_candidate, dict):
                continue
            candidate = normalize_candidate_record(raw_candidate)
            identity = _identity(candidate)
            stable_identity = _stable_identity(candidate)
            tmdb_identity = candidate_tmdb_identity(candidate)
            if identity in watched or tmdb_identity in watched_tmdb:
                counters["watched"] += 1
                continue
            if (
                any(key in excluded_actions for key in candidate_state_identity_keys(candidate))
                or tmdb_identity in excluded_action_tmdb
            ):
                counters["actioned"] += 1
                continue
            year = _number(candidate.get("year"))
            if year is not None and int(year) > now.year:
                counters["future_release"] += 1
                continue
            if not is_viable_unrated_candidate(candidate, current_year=now.year):
                counters["quality_gate"] += 1
                continue
            if candidate_matches(candidate, criteria) is False:
                counters["preferences"] += 1
                continue
            if stable_identity in seen:
                counters["duplicate"] += 1
                continue
            seen.add(stable_identity)
            if identity in recently_seen:
                counters["recently_seen"] += 1
                recent_fallback.append(candidate)
                continue
            eligible.append(candidate)
        return eligible, recent_fallback, counters

    def build_deck(
        self,
        candidate_filters: dict | None,
        now: datetime | date,
        *,
        vector: RecommendationVector | dict | None = None,
        variation_seed: int = 0,
        limit_active: int = DEFAULT_ACTIVE_LIMIT,
        reserve_size: int = DEFAULT_RESERVE_SIZE,
    ) -> dict:
        current = _as_utc(now)
        active_limit = max(0, int(limit_active))
        reserve_limit = max(0, int(reserve_size))
        current_filters = dict(candidate_filters or {})
        current_vector = _coerce_vector(vector, current_filters)
        variation = max(0, int(variation_seed or 0))
        rank_seed = f"{current.date().isoformat()}|{variation}"
        eligible, recent_fallback, excluded = self._eligible_candidates(
            current_filters,
            current,
        )
        selection_pool = eligible
        ranked = _automatic_ranked_candidates(
            _rank_candidates(
                selection_pool,
                rank_seed,
                current_vector,
            ),
            current_vector,
            capacity=active_limit + reserve_limit,
        )
        reused_recent = len(ranked) == 0 and len(recent_fallback) > 0
        if reused_recent:
            selection_pool = recent_fallback
            ranked = _automatic_ranked_candidates(
                _rank_candidates(
                    selection_pool,
                    rank_seed,
                    current_vector,
                ),
                current_vector,
                capacity=active_limit + reserve_limit,
            )
        relevance_counts = {
            tier.name: sum(
                _relevance_tier(candidate, current_vector) == tier
                for candidate in selection_pool
            )
            for tier in RelevanceTier
        }
        excluded["relevance_catalog"] = relevance_counts[RelevanceTier.D.name]
        excluded["exploration_capped"] = max(
            0,
            relevance_counts[RelevanceTier.C.name]
            - sum(
                _relevance_tier(candidate, current_vector) == RelevanceTier.C
                for candidate in ranked
            ),
        )
        unknown_limit = _unknown_rating_limit(current_filters, active_limit)
        active, remaining = _select_active_with_unknown_quota(
            ranked,
            active_limit=active_limit,
            unknown_limit=unknown_limit,
            vector=current_vector,
        )
        reserve = remaining[:reserve_limit]
        if not active:
            underfilled_reason = "no_eligible_candidates" if excluded["pool_total"] else "pool_empty"
        elif len(active) < active_limit:
            underfilled_reason = "active_underfilled"
        elif len(reserve) < reserve_limit:
            underfilled_reason = "reserve_underfilled"
        else:
            underfilled_reason = None
        deck_id = uuid4().hex
        deck = {
            "deck_id": deck_id,
            "generated_at": current.isoformat(timespec="seconds"),
            "candidate_filters": deepcopy(current_filters),
            "recommendation_vector": current_vector.to_dict(),
            "variation_seed": variation,
            "preferences": deepcopy(current_filters),
            "active": active,
            "reserve": reserve,
            "active_limit": active_limit,
            "reserve_size": reserve_limit,
            "unknown_rating_limit": unknown_limit,
            "refill_needed": _deck_refill_needed(
                active,
                reserve,
                active_limit=active_limit,
                reserve_threshold=self._refill_threshold,
            ),
            "underfilled_reason": underfilled_reason,
            "eligible_count": len(ranked),
            "catalog_eligible_count": len(selection_pool),
            "eligible_reserve_count": len(reserve),
            "relevance_counts": relevance_counts,
            "exploration_limit": int(
                active_limit * resolve_exploration_ratio(current_vector.openness_level)
            ),
            "recently_seen_reused": len(active) + len(reserve) if reused_recent else 0,
            "excluded": excluded,
        }
        self._remember_deck(deck, reason="new_deck")
        return deepcopy(deck)

    def refresh_deck(
        self,
        candidate_filters: dict | None,
        now: datetime | date,
        *,
        vector: RecommendationVector | dict | None = None,
        variation_seed: int = 0,
        force_new: bool = False,
    ) -> dict:
        current = _as_utc(now)
        current_filters = dict(candidate_filters or {})
        current_vector = _coerce_vector(vector, current_filters)
        cache_key = self._material_signature(
            current_filters,
            current_vector,
            variation_seed,
        )
        if (
            not force_new
            and cache_key == self._latest_cache_key
            and self._latest_deck_id in self._decks
        ):
            return deepcopy(self._decks[self._latest_deck_id])
        if not force_new:
            restored = self._load_persisted_deck(cache_key)
            if restored is not None:
                try:
                    return self.top_up_deck(str(restored["deck_id"]), current)
                except (KeyError, TypeError, ValueError):
                    recommendation_deck_repository.clear_current_deck(path=self._db_path)
        deck = self.build_deck(
            current_filters,
            current,
            vector=current_vector,
            variation_seed=variation_seed,
        )
        return deck

    def top_up_deck(self, deck_id: str, now: datetime | date) -> dict:
        """Merge newly eligible local candidates into an existing deck in place."""
        if deck_id not in self._decks:
            raise KeyError(f"Unknown recommendation deck: {deck_id}")
        current = _as_utc(now)
        deck = self._decks[deck_id]
        candidate_filters = dict(deck.get("candidate_filters") or deck.get("preferences") or {})
        vector = _coerce_vector(deck.get("recommendation_vector"), candidate_filters)
        variation_seed = max(0, int(deck.get("variation_seed") or 0))
        generated_at = str(deck.get("generated_at") or current.isoformat())
        rank_seed = f"{generated_at[:10]}|{variation_seed}"
        eligible, recent_fallback, excluded = self._eligible_candidates(candidate_filters, current)
        valid_candidates = list(eligible) + list(recent_fallback)
        valid_identities = {_stable_identity(candidate) for candidate in valid_candidates}

        active: list[dict] = []
        active_identities: set[tuple[str, str, str]] = set()
        for candidate in deck.get("active") or []:
            identity = _stable_identity(candidate)
            if identity not in valid_identities or identity in active_identities:
                continue
            active_identities.add(identity)
            active.append(candidate)

        existing_reserve: list[dict] = []
        available_identities: set[tuple[str, str, str]] = set()
        for candidate in list(deck.get("reserve") or []):
            identity = _stable_identity(candidate)
            if (
                identity in active_identities
                or identity in available_identities
                or identity not in valid_identities
            ):
                continue
            available_identities.add(identity)
            existing_reserve.append(candidate)

        new_candidates = [
            candidate
            for candidate in eligible
            if _stable_identity(candidate) not in active_identities
            and _stable_identity(candidate) not in available_identities
        ]
        ranked_new = _automatic_ranked_candidates(
            _rank_candidates(new_candidates, rank_seed, vector),
            vector,
            capacity=int(deck["active_limit"]) + int(deck["reserve_size"]),
        )

        policy_candidates = active + existing_reserve + ranked_new
        relevance_counts = {
            tier.name: sum(
                _relevance_tier(candidate, vector) == tier
                for candidate in policy_candidates
            )
            for tier in RelevanceTier
        }
        ranked_available = existing_reserve + ranked_new
        original_active_identities = set(active_identities)
        active, remaining = _select_active_with_unknown_quota(
            ranked_available,
            active_limit=int(deck["active_limit"]),
            unknown_limit=int(deck["unknown_rating_limit"]),
            vector=vector,
            initial_active=active,
        )
        reserve = remaining[: int(deck["reserve_size"])]
        if not active:
            underfilled_reason = "no_eligible_candidates" if excluded["pool_total"] else "pool_empty"
        elif len(active) < int(deck["active_limit"]):
            underfilled_reason = "active_underfilled"
        elif len(reserve) < int(deck["reserve_size"]):
            underfilled_reason = "reserve_underfilled"
        else:
            underfilled_reason = None

        excluded["relevance_catalog"] = relevance_counts[RelevanceTier.D.name]
        excluded["exploration_capped"] = max(
            0,
            relevance_counts[RelevanceTier.C.name]
            - sum(_relevance_tier(candidate, vector) == RelevanceTier.C for candidate in policy_candidates),
        )
        deck.update({
            "active": active,
            "reserve": reserve,
            "refill_needed": _deck_refill_needed(
                active,
                reserve,
                active_limit=int(deck["active_limit"]),
                reserve_threshold=self._refill_threshold,
            ),
            "underfilled_reason": underfilled_reason,
            "eligible_count": len(policy_candidates),
            "catalog_eligible_count": len(policy_candidates),
            "eligible_reserve_count": len(reserve),
            "relevance_counts": relevance_counts,
            "excluded": excluded,
            "last_top_up_at": current.isoformat(timespec="seconds"),
        })
        self._remember_deck(deck, reason="top_up")
        return deepcopy(deck)

    def apply_action_and_refill(
        self,
        deck_id: str,
        candidate: dict,
        action: str,
        *,
        user_score: int | None = None,
    ) -> dict:
        if deck_id not in self._decks:
            raise KeyError(f"Unknown recommendation deck: {deck_id}")
        normalized_action = str(action or "").strip().casefold()
        normalized_score = normalize_user_rating(user_score)
        if normalized_action == "watched":
            if normalized_score is None:
                raise ValueError("watched action requires user_score from 1 to 3")
        elif user_score is not None:
            raise ValueError("user_score is only supported for watched action")
        if normalized_action in {"watchlist", "deferred"}:
            transition = title_state_service.add_to_watchlist(candidate, path=self._db_path)
        elif normalized_action == "hidden":
            transition = title_state_service.hide_candidate(candidate, path=self._db_path)
        elif normalized_action == "watched":
            transition = title_state_service.mark_watched(
                candidate,
                normalized_score,
                path=self._db_path,
            )
        else:
            raise ValueError(f"Unsupported recommendation action: {action}")

        deck = self._decks[deck_id]
        target_identity = candidate_state_identity_key(candidate)
        removed_index = next(
            (
                index
                for index, item in enumerate(deck["active"])
                if candidate_state_identity_key(item) == target_identity
            ),
            len(deck["active"]),
        )
        deck["active"] = [
            item for item in deck["active"] if candidate_state_identity_key(item) != target_identity
        ]
        deck["reserve"] = [
            item for item in deck["reserve"] if candidate_state_identity_key(item) != target_identity
        ]
        promoted = None
        if len(deck["active"]) < deck["active_limit"] and deck["reserve"]:
            candidate_filters = dict(deck.get("candidate_filters") or deck.get("preferences") or {})
            vector = _coerce_vector(deck.get("recommendation_vector"), candidate_filters)
            explicit_relevance = _has_relevance_intent(vector)
            exploration_ratio = resolve_exploration_ratio(vector.openness_level)
            unknown_count = sum(has_unknown_rating(item) for item in deck["active"])
            exploratory_count = sum(
                _relevance_tier(item, vector) == RelevanceTier.C
                for item in deck["active"]
            )
            promotable_indexes = [
                index
                for index, item in enumerate(deck["reserve"])
                if not has_unknown_rating(item) or unknown_count < deck["unknown_rating_limit"]
                if (
                    not explicit_relevance
                    or _relevance_tier(item, vector) != RelevanceTier.C
                    or (
                        exploration_ratio > 0
                        and exploratory_count + 1
                        <= int((len(deck["active"]) + 1) * exploration_ratio)
                    )
                )
            ]
            if promotable_indexes:
                if explicit_relevance:
                    removed_tier = _relevance_tier(candidate, vector)
                    tier_order = [removed_tier]
                    tier_order.extend(
                        tier
                        for tier in RelevanceTier
                        if removed_tier < tier <= RelevanceTier.C
                    )
                    tier_order.extend(
                        tier
                        for tier in reversed(tuple(RelevanceTier))
                        if tier < removed_tier
                    )
                    promotion_index = None
                    for tier in tier_order:
                        comparable = [
                            index
                            for index in promotable_indexes
                            if _relevance_tier(deck["reserve"][index], vector) == tier
                        ]
                        if comparable:
                            promotion_index = min(
                                comparable,
                                key=lambda index: (
                                    -_personal_fit_score(deck["reserve"][index]),
                                    -_vector_score(deck["reserve"][index], vector),
                                    index,
                                ),
                            )
                            break
                else:
                    removed_score = _base_score(candidate)
                    promotion_index = min(
                        promotable_indexes,
                        key=lambda index: (
                            abs(_base_score(deck["reserve"][index]) - removed_score),
                            index,
                        ),
                    )
                if promotion_index is not None:
                    promoted = deck["reserve"].pop(promotion_index)
        if promoted is not None:
            deck["active"].insert(min(removed_index, len(deck["active"])), promoted)
        deck["refill_needed"] = _deck_refill_needed(
            deck["active"],
            deck["reserve"],
            active_limit=int(deck["active_limit"]),
            reserve_threshold=self._refill_threshold,
        )
        deck["eligible_count"] = max(
            len(deck["active"]) + len(deck["reserve"]),
            int(deck.get("eligible_count") or 0) - 1,
        )
        deck["catalog_eligible_count"] = max(
            len(deck["active"]) + len(deck["reserve"]),
            int(deck.get("catalog_eligible_count") or 0) - 1,
        )
        deck["eligible_reserve_count"] = len(deck["reserve"])
        relevance_counts = deck.get("relevance_counts")
        if isinstance(relevance_counts, dict):
            removed_tier_name = _relevance_tier(
                candidate,
                deck.get("recommendation_vector"),
            ).name
            relevance_counts[removed_tier_name] = max(
                0,
                int(relevance_counts.get(removed_tier_name) or 0) - 1,
            )
        if len(deck["active"]) < deck["active_limit"]:
            deck["underfilled_reason"] = (
                "reserve_exhausted" if not deck["reserve"] else "active_underfilled"
            )
        elif len(deck["reserve"]) < deck["reserve_size"]:
            deck["underfilled_reason"] = "reserve_underfilled"
        else:
            deck["underfilled_reason"] = None
        deck["last_action"] = {
            "action": normalized_action,
            "identity": target_identity,
            "transition": transition,
            "promoted_identity": candidate_state_identity_key(promoted) if promoted else None,
        }
        self._remember_deck(deck, reason=f"action:{normalized_action}")
        return deepcopy(deck)

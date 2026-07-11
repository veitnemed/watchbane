"""Build stable local recommendation decks from the shared candidate pool."""

from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, time, timedelta, timezone
from enum import IntEnum
import hashlib
import json
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from app.core.filters import candidate_matches
from candidates.models import genre_schema
from candidates.models.keys import (
    candidate_state_identity_key,
    candidate_state_identity_keys,
    title_identity_key,
)
from candidates.models.schema import coerce_candidate_number, normalize_candidate_record
from candidates.pool.storage import candidate_tmdb_identity
from candidates.repositories.pool_repository import load_candidate_pool
from candidates.scoring.rating_confidence import has_unknown_rating, is_viable_unrated_candidate
from candidates.sources.tmdb.scoring import compute_tmdb_quality_score
from candidates import title_state_service
from dataset.models.media_type import normalize_media_type
from storage.sqlite import action_repository, impression_repository
from storage.sqlite.connection import connect
from storage.sqlite.migrations import apply_migrations


PoolLoader = Callable[[], dict]
DEFAULT_ACTIVE_LIMIT = 30
DEFAULT_RESERVE_SIZE = 70
DEFAULT_RECENT_DAYS = 30
DEFAULT_REFILL_THRESHOLD = 20
DEFAULT_UNKNOWN_RATING_LIMIT = 6
EXPANDED_UNKNOWN_RATING_LIMIT = 12
DEFAULT_EXPLORATION_RATIO = 0.2


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


def _recommendation_profile(
    preferences: dict | None,
) -> tuple[frozenset[str], frozenset[str], frozenset[str], bool]:
    current = dict(preferences or {})
    mood = str(
        current.get("_recommendation_mood")
        or current.get("mood")
        or current.get("vibe")
        or ""
    ).strip().casefold()
    if mood in {"any", "mixed"}:
        mood = ""
    mood_profile = _MOOD_RELEVANCE_PROFILES.get(mood, {})
    configured = genre_schema.normalize_genre_filter_list(
        _preference_values(
            current,
            "_recommendation_genre_groups",
            "genre_groups",
            "include_genres",
            "genres",
        )
    )
    exact = set(mood_profile.get("exact") or ())
    exact.update(configured)
    include_genres = genre_schema.normalize_genre_filter_list(
        _preference_values(current, "include_genres", "genres")
    )
    exact.update(include_genres)
    adjacent = set(mood_profile.get("adjacent") or ()) - exact
    incompatible = set(mood_profile.get("incompatible") or ()) - exact
    explicit = bool(exact or mood_profile)
    return frozenset(exact), frozenset(adjacent), frozenset(incompatible), explicit


def _has_relevance_intent(preferences: dict | None) -> bool:
    return _recommendation_profile(preferences)[3]


def _relevance_tier(candidate: dict, preferences: dict | None) -> RelevanceTier:
    exact, adjacent, incompatible, explicit = _recommendation_profile(preferences)
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


def _exploration_allowance(ab_count: int, capacity: int) -> int:
    if ab_count <= 0 or capacity <= 0:
        return 0
    capacity_limit = int(capacity * DEFAULT_EXPLORATION_RATIO)
    balance_limit = int(ab_count * DEFAULT_EXPLORATION_RATIO / (1.0 - DEFAULT_EXPLORATION_RATIO))
    return max(0, min(capacity_limit, balance_limit))


def _automatic_ranked_candidates(
    ranked: list[dict],
    preferences: dict | None,
    *,
    capacity: int,
) -> list[dict]:
    if _has_relevance_intent(preferences) is False:
        return list(ranked)
    close = [
        candidate
        for candidate in ranked
        if _relevance_tier(candidate, preferences) <= RelevanceTier.B
    ]
    exploratory = [
        candidate
        for candidate in ranked
        if _relevance_tier(candidate, preferences) == RelevanceTier.C
    ]
    return close + exploratory[: _exploration_allowance(len(close), capacity)]


def count_automatic_recommendation_candidates(
    candidates: list[dict],
    preferences: dict | None,
    *,
    capacity: int = DEFAULT_ACTIVE_LIMIT + DEFAULT_RESERVE_SIZE,
) -> int:
    """Count the local A/B slice plus its bounded exploratory allowance."""
    if _has_relevance_intent(preferences) is False:
        return len(candidates)
    close_count = sum(
        _relevance_tier(candidate, preferences) <= RelevanceTier.B
        for candidate in candidates
    )
    exploratory_count = sum(
        _relevance_tier(candidate, preferences) == RelevanceTier.C
        for candidate in candidates
    )
    return close_count + min(exploratory_count, _exploration_allowance(close_count, capacity))


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


def _diversify_quality_group(candidates: list[dict], day_seed: str) -> list[dict]:
    remaining = sorted(candidates, key=lambda item: _stable_hash(day_seed, item))
    result: list[dict] = []
    media_counts: dict[str, int] = {}
    genre_counts: dict[str, int] = {}
    country_counts: dict[str, int] = {}
    decade_counts: dict[int | None, int] = {}
    while remaining:
        window = remaining[: min(12, len(remaining))]

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


def _rank_candidates(
    candidates: list[dict],
    day_seed: str,
    preferences: dict | None = None,
) -> list[dict]:
    quality_groups: dict[tuple[int, float, float], list[dict]] = {}
    for candidate in candidates:
        group_key = (
            int(_relevance_tier(candidate, preferences)),
            round(_personal_fit_score(candidate), 6),
            round(_base_score(candidate), 6),
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
    preferences: dict | None = None,
    initial_active: list[dict] | None = None,
) -> tuple[list[dict], list[dict]]:
    active: list[dict] = list(initial_active or [])[:active_limit]
    remaining: list[dict] = []
    unknown_count = sum(has_unknown_rating(candidate) for candidate in active)
    exploratory_count = sum(
        _relevance_tier(candidate, preferences) == RelevanceTier.C
        for candidate in active
    )
    explicit_relevance = _has_relevance_intent(preferences)
    for candidate in ranked:
        unknown = has_unknown_rating(candidate)
        exploratory = (
            explicit_relevance
            and _relevance_tier(candidate, preferences) == RelevanceTier.C
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
        preferences: dict | None,
        now: datetime | date,
        *,
        limit_active: int = DEFAULT_ACTIVE_LIMIT,
        reserve_size: int = DEFAULT_RESERVE_SIZE,
    ) -> dict:
        current = _as_utc(now)
        active_limit = max(0, int(limit_active))
        reserve_limit = max(0, int(reserve_size))
        current_preferences = dict(preferences or {})
        eligible, recent_fallback, excluded = self._eligible_candidates(
            current_preferences,
            current,
        )
        selection_pool = eligible
        ranked = _automatic_ranked_candidates(
            _rank_candidates(
                selection_pool,
                current.date().isoformat(),
                current_preferences,
            ),
            current_preferences,
            capacity=active_limit + reserve_limit,
        )
        reused_recent = len(ranked) == 0 and len(recent_fallback) > 0
        if reused_recent:
            selection_pool = recent_fallback
            ranked = _automatic_ranked_candidates(
                _rank_candidates(
                    selection_pool,
                    current.date().isoformat(),
                    current_preferences,
                ),
                current_preferences,
                capacity=active_limit + reserve_limit,
            )
        relevance_counts = {
            tier.name: sum(
                _relevance_tier(candidate, current_preferences) == tier
                for candidate in selection_pool
            )
            for tier in RelevanceTier
        }
        excluded["relevance_catalog"] = relevance_counts[RelevanceTier.D.name]
        excluded["exploration_capped"] = max(
            0,
            relevance_counts[RelevanceTier.C.name]
            - sum(
                _relevance_tier(candidate, current_preferences) == RelevanceTier.C
                for candidate in ranked
            ),
        )
        unknown_limit = _unknown_rating_limit(current_preferences, active_limit)
        active, remaining = _select_active_with_unknown_quota(
            ranked,
            active_limit=active_limit,
            unknown_limit=unknown_limit,
            preferences=current_preferences,
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
            "preferences": deepcopy(current_preferences),
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
            "exploration_limit": int(active_limit * DEFAULT_EXPLORATION_RATIO),
            "recently_seen_reused": len(active) + len(reserve) if reused_recent else 0,
            "excluded": excluded,
        }
        self._decks[deck_id] = deck
        impression_repository.record_impressions(
            active,
            deck_id=deck_id,
            shown_at=deck["generated_at"],
            path=self._db_path,
        )
        return deepcopy(deck)

    def refresh_deck(
        self,
        preferences: dict | None,
        now: datetime | date,
        *,
        force_new: bool = False,
    ) -> dict:
        current = _as_utc(now)
        cache_key = json.dumps(
            {"day": current.date().isoformat(), "preferences": preferences or {}},
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )
        if (
            not force_new
            and cache_key == self._latest_cache_key
            and self._latest_deck_id in self._decks
        ):
            return deepcopy(self._decks[self._latest_deck_id])
        deck = self.build_deck(preferences, current)
        self._latest_cache_key = cache_key
        self._latest_deck_id = deck["deck_id"]
        return deck

    def top_up_deck(self, deck_id: str, now: datetime | date) -> dict:
        """Merge newly eligible local candidates into an existing deck in place."""
        if deck_id not in self._decks:
            raise KeyError(f"Unknown recommendation deck: {deck_id}")
        current = _as_utc(now)
        deck = self._decks[deck_id]
        preferences = dict(deck.get("preferences") or {})
        eligible, recent_fallback, excluded = self._eligible_candidates(preferences, current)
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

        available_by_identity: dict[tuple[str, str, str], dict] = {}
        for candidate in list(deck.get("reserve") or []) + list(eligible):
            identity = _stable_identity(candidate)
            if identity in active_identities or identity not in valid_identities:
                continue
            available_by_identity.setdefault(identity, candidate)

        policy_candidates = active + list(available_by_identity.values())
        relevance_counts = {
            tier.name: sum(
                _relevance_tier(candidate, preferences) == tier
                for candidate in policy_candidates
            )
            for tier in RelevanceTier
        }
        ranked_policy = _rank_candidates(
            policy_candidates,
            current.date().isoformat(),
            preferences,
        )
        automatic_policy = _automatic_ranked_candidates(
            ranked_policy,
            preferences,
            capacity=int(deck["active_limit"]) + int(deck["reserve_size"]),
        )
        ranked_available = [
            candidate
            for candidate in automatic_policy
            if _stable_identity(candidate) not in active_identities
        ]
        original_active_identities = set(active_identities)
        active, remaining = _select_active_with_unknown_quota(
            ranked_available,
            active_limit=int(deck["active_limit"]),
            unknown_limit=int(deck["unknown_rating_limit"]),
            preferences=preferences,
            initial_active=active,
        )
        reserve = remaining[: int(deck["reserve_size"])]
        promoted = [
            candidate
            for candidate in active
            if _stable_identity(candidate) not in original_active_identities
        ]

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
            - sum(
                _relevance_tier(candidate, preferences) == RelevanceTier.C
                for candidate in automatic_policy
            ),
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
            "eligible_count": len(automatic_policy),
            "catalog_eligible_count": len(policy_candidates),
            "eligible_reserve_count": len(reserve),
            "relevance_counts": relevance_counts,
            "excluded": excluded,
            "last_top_up_at": current.isoformat(timespec="seconds"),
        })
        if promoted:
            impression_repository.record_impressions(
                promoted,
                deck_id=deck_id,
                shown_at=deck["last_top_up_at"],
                path=self._db_path,
            )
        return deepcopy(deck)

    def apply_action_and_refill(self, deck_id: str, candidate: dict, action: str) -> dict:
        if deck_id not in self._decks:
            raise KeyError(f"Unknown recommendation deck: {deck_id}")
        normalized_action = str(action or "").strip().casefold()
        if normalized_action in {"watchlist", "deferred"}:
            transition = title_state_service.add_to_watchlist(candidate, path=self._db_path)
        elif normalized_action == "hidden":
            transition = title_state_service.hide_candidate(candidate, path=self._db_path)
        elif normalized_action == "watched":
            transition = title_state_service.mark_watched(candidate, path=self._db_path)
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
            preferences = dict(deck.get("preferences") or {})
            explicit_relevance = _has_relevance_intent(preferences)
            unknown_count = sum(has_unknown_rating(item) for item in deck["active"])
            exploratory_count = sum(
                _relevance_tier(item, preferences) == RelevanceTier.C
                for item in deck["active"]
            )
            promotable_indexes = [
                index
                for index, item in enumerate(deck["reserve"])
                if not has_unknown_rating(item) or unknown_count < deck["unknown_rating_limit"]
                if (
                    not explicit_relevance
                    or _relevance_tier(item, preferences) != RelevanceTier.C
                    or (exploratory_count + 1) * 5 <= len(deck["active"]) + 1
                )
            ]
            if promotable_indexes:
                if explicit_relevance:
                    removed_tier = _relevance_tier(candidate, preferences)
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
                            if _relevance_tier(deck["reserve"][index], preferences) == tier
                        ]
                        if comparable:
                            promotion_index = min(
                                comparable,
                                key=lambda index: (
                                    -_personal_fit_score(deck["reserve"][index]),
                                    -_base_score(deck["reserve"][index]),
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
            impression_repository.record_impressions(
                [promoted],
                deck_id=deck_id,
                path=self._db_path,
            )
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
        deck["eligible_reserve_count"] = len(deck["reserve"])
        relevance_counts = deck.get("relevance_counts")
        if isinstance(relevance_counts, dict):
            removed_tier_name = _relevance_tier(
                candidate,
                dict(deck.get("preferences") or {}),
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
        return deepcopy(deck)

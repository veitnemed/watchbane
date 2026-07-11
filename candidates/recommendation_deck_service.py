"""Build stable local recommendation decks from the shared candidate pool."""

from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, time, timedelta, timezone
import hashlib
import json
from pathlib import Path
from typing import Callable
from uuid import uuid4

from app.core.filters import candidate_matches
from candidates.models.keys import (
    candidate_state_identity_key,
    candidate_state_identity_keys,
    title_identity_key,
)
from candidates.models.schema import coerce_candidate_number, normalize_candidate_record
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


def _number(value) -> float | None:
    result = coerce_candidate_number(value)
    if result is None or isinstance(result, bool):
        return None
    return float(result)


def _base_score(candidate: dict) -> float:
    if has_unknown_rating(candidate):
        for field in ("final_score", "candidate_score", "quality_score"):
            score = _number(candidate.get(field))
            if score is not None:
                return score
        return compute_tmdb_quality_score(candidate) * 100.0
    for field in ("final_score", "candidate_score", "quality_score", "tmdb_score"):
        score = _number(candidate.get(field))
        if score is not None:
            return score * 10.0 if field == "tmdb_score" and score <= 10.0 else score
    return 0.0


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
    value = candidate.get("country") or candidate.get("origin_country") or ""
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


def _rank_candidates(candidates: list[dict], day_seed: str) -> list[dict]:
    quality_groups: dict[int, list[dict]] = {}
    for candidate in candidates:
        bucket = int(_base_score(candidate) // 10)
        quality_groups.setdefault(bucket, []).append(candidate)
    ranked: list[dict] = []
    for bucket in sorted(quality_groups, reverse=True):
        ranked.extend(_diversify_quality_group(quality_groups[bucket], day_seed))
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
) -> tuple[list[dict], list[dict]]:
    active: list[dict] = []
    remaining: list[dict] = []
    unknown_count = 0
    for candidate in ranked:
        unknown = has_unknown_rating(candidate)
        if len(active) < active_limit and (not unknown or unknown_count < unknown_limit):
            active.append(candidate)
            unknown_count += int(unknown)
        else:
            remaining.append(candidate)
    return active, remaining


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

    def _watched_identities(self) -> set[tuple[str, str]]:
        conn = connect(self._db_path)
        try:
            apply_migrations(conn)
            return {
                (
                    title_identity_key({"title": row["title"], "year": row["year"]}),
                    normalize_media_type(row["media_type"]),
                )
                for row in conn.execute(
                    "SELECT title, year, media_type FROM watched_records WHERE payload_json != '{}'"
                )
            }
        finally:
            conn.close()

    def _excluded_action_identities(self) -> set[str]:
        result: set[str] = set()
        for action in (action_repository.ACTION_WATCHLIST, action_repository.ACTION_HIDDEN):
            result.update(action_repository.load_action_identities(action, path=self._db_path))
        return result

    def _recent_identities(self, now: datetime) -> set[tuple[str, str]]:
        cutoff = (now - timedelta(days=self._recent_days)).isoformat(timespec="seconds")
        return {
            (str(row["identity_key"]), normalize_media_type(row["media_type"]))
            for row in impression_repository.get_recently_seen(cutoff, path=self._db_path)
        }

    def _eligible_candidates(self, preferences: dict, now: datetime) -> tuple[list[dict], dict[str, int]]:
        pool = self._pool_loader()
        source = list(pool.values()) if isinstance(pool, dict) else list(pool or [])
        watched = self._watched_identities()
        excluded_actions = self._excluded_action_identities()
        recently_seen = self._recent_identities(now)
        criteria = dict(preferences or {})
        criteria["only_unwatched"] = False
        criteria["hide_hidden"] = False
        seen: set[tuple[str, str]] = set()
        eligible: list[dict] = []
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
            if identity in seen:
                counters["duplicate"] += 1
                continue
            seen.add(identity)
            if identity in watched:
                counters["watched"] += 1
                continue
            if any(key in excluded_actions for key in candidate_state_identity_keys(candidate)):
                counters["actioned"] += 1
                continue
            if identity in recently_seen:
                counters["recently_seen"] += 1
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
            eligible.append(candidate)
        return eligible, counters

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
        eligible, excluded = self._eligible_candidates(dict(preferences or {}), current)
        ranked = _rank_candidates(eligible, current.date().isoformat())
        unknown_limit = _unknown_rating_limit(dict(preferences or {}), active_limit)
        active, remaining = _select_active_with_unknown_quota(
            ranked,
            active_limit=active_limit,
            unknown_limit=unknown_limit,
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
            "preferences": deepcopy(dict(preferences or {})),
            "active": active,
            "reserve": reserve,
            "active_limit": active_limit,
            "reserve_size": reserve_limit,
            "unknown_rating_limit": unknown_limit,
            "refill_needed": len(reserve) < self._refill_threshold,
            "underfilled_reason": underfilled_reason,
            "eligible_count": len(eligible),
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
            unknown_count = sum(has_unknown_rating(item) for item in deck["active"])
            promotable_indexes = [
                index
                for index, item in enumerate(deck["reserve"])
                if not has_unknown_rating(item) or unknown_count < deck["unknown_rating_limit"]
            ]
            if promotable_indexes:
                removed_score = _base_score(candidate)
                promotion_index = min(
                    promotable_indexes,
                    key=lambda index: (
                        abs(_base_score(deck["reserve"][index]) - removed_score),
                        index,
                    ),
                )
                promoted = deck["reserve"].pop(promotion_index)
        if promoted is not None:
            deck["active"].insert(min(removed_index, len(deck["active"])), promoted)
            impression_repository.record_impressions(
                [promoted],
                deck_id=deck_id,
                path=self._db_path,
            )
        deck["refill_needed"] = len(deck["reserve"]) < self._refill_threshold
        if len(deck["active"]) < deck["active_limit"] and not deck["reserve"]:
            deck["underfilled_reason"] = "reserve_exhausted"
        deck["last_action"] = {
            "action": normalized_action,
            "identity": target_identity,
            "transition": transition,
            "promoted_identity": candidate_state_identity_key(promoted) if promoted else None,
        }
        return deepcopy(deck)

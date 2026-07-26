"""Read-only C3-13 audit for persisted candidate pools."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
import sqlite3
from typing import Any, Mapping

from candidates.models.keys import candidate_state_identity_keys, title_identity_key
from candidates.models.schema import normalize_candidate_record, resolve_canonical_year
from candidates.pool.storage import candidate_tmdb_identity, coerce_tmdb_id
from candidates.recommendation_deck_service import (
    ProductionEligibilityContext,
    evaluate_production_eligibility,
    _ALWAYS_IRRELEVANT_GENRES,
)
from candidates.models import genre_schema
from candidates.safety.explicit_content import is_blocked_explicit_sexual_content
from dataset.models.media_type import MOVIE_MEDIA_TYPE_ALIASES, TV_MEDIA_TYPE_ALIASES, normalize_media_type
from storage.sqlite.json_codec import loads_json
from tools.qa.output_defect_audit import audit_title


@dataclass(frozen=True)
class PoolAuditState:
    watched: set[tuple[str, str]]
    watched_tmdb: set[tuple[str, int]]
    saved: set[str]
    saved_tmdb: set[tuple[str, int]]
    hidden: set[str]
    hidden_tmdb: set[tuple[str, int]]
    recently_seen: set[tuple[str, str]]


def _valid_media_type(value: object) -> bool:
    return str(value or "").strip().casefold() in (MOVIE_MEDIA_TYPE_ALIASES | TV_MEDIA_TYPE_ALIASES)


def _title(candidate: Mapping[str, Any]) -> str:
    for field_name in ("title", "name", "localized_title", "original_title", "original_name"):
        value = str(candidate.get(field_name) or "").strip()
        if value:
            return value
    return ""


def _missing_fields(candidate: Mapping[str, Any]) -> list[str]:
    values = {
        "poster": any(candidate.get(name) not in (None, "") for name in ("poster_path", "poster_url", "poster")),
        "overview": bool(str(candidate.get("overview") or candidate.get("description") or "").strip()),
        "year": resolve_canonical_year(dict(candidate)) is not None,
        "genres": bool(candidate.get("genre_keys") or candidate.get("genres") or candidate.get("genre_ids")),
        "countries": bool(candidate.get("country_codes") or candidate.get("countries") or candidate.get("country")),
        "runtime": any(candidate.get(name) not in (None, "", []) for name in ("runtime", "runtime_minutes", "episode_run_time")),
        "content_rating": candidate.get("content_rating") not in (None, ""),
        "keywords": candidate.get("keywords") not in (None, "", []),
    }
    return [field_name for field_name, present in values.items() if not present]


def _hard_garbage_reasons(candidate: Mapping[str, Any], *, duplicate: bool) -> list[str]:
    reasons: list[str] = []
    tmdb_id = coerce_tmdb_id(candidate.get("tmdb_id"))
    if tmdb_id is None or tmdb_id <= 0:
        reasons.append("invalid_tmdb_id")
    if not _valid_media_type(candidate.get("media_type")):
        reasons.append("invalid_media_type")
    title = _title(candidate)
    if not title or "missing_or_placeholder_title" in audit_title(title):
        reasons.append("unusable_title")
    if duplicate:
        reasons.append("duplicate_identity")
    if is_blocked_explicit_sexual_content(dict(candidate)):
        reasons.append("explicit_content")
    genres = set(genre_schema.normalize_genre_filter_list(candidate.get("genre_keys") or []))
    if genres & _ALWAYS_IRRELEVANT_GENRES:
        reasons.append("hard_drop_genre")
    return reasons


def _state_flags(candidate: dict, state: PoolAuditState) -> list[str]:
    identity = (title_identity_key(candidate), normalize_media_type(candidate.get("media_type")))
    tmdb_identity = candidate_tmdb_identity(candidate)
    action_keys = set(candidate_state_identity_keys(candidate))
    flags: list[str] = []
    if identity in state.watched or tmdb_identity in state.watched_tmdb:
        flags.append("watched")
    if action_keys & state.saved or tmdb_identity in state.saved_tmdb:
        flags.append("saved")
    if action_keys & state.hidden or tmdb_identity in state.hidden_tmdb:
        flags.append("hidden")
    if identity in state.recently_seen:
        flags.append("recently_seen")
    return flags


def audit_candidate_pool(
    pool: Mapping[str, object],
    *,
    state: PoolAuditState,
    now: datetime,
    preferences: dict | None = None,
) -> dict[str, Any]:
    """Measure a pool with production eligibility, without mutating it or state."""
    seen: set[tuple[str, str, str]] = set()
    seen_aliases: set[tuple[str, str, str]] = set()
    duplicate_seen: set[tuple[str, int]] = set()
    reason_counts: Counter[str] = Counter()
    missing_counts: Counter[str] = Counter()
    state_counts: Counter[str] = Counter()
    findings: list[dict[str, Any]] = []
    hard_count = eligible_total = eligible_hard_leaks = duplicate_count = state_conflicts = 0

    for raw_candidate in pool.values():
        if not isinstance(raw_candidate, dict):
            continue
        candidate = normalize_candidate_record(raw_candidate)
        raw_tmdb_id = coerce_tmdb_id(raw_candidate.get("tmdb_id"))
        raw_identity = (
            (str(raw_candidate.get("media_type")).strip().casefold(), raw_tmdb_id)
            if raw_tmdb_id and raw_tmdb_id > 0 and _valid_media_type(raw_candidate.get("media_type"))
            else None
        )
        duplicate = raw_identity is not None and raw_identity in duplicate_seen
        if raw_identity is not None:
            duplicate_seen.add(raw_identity)
        hard_reasons = _hard_garbage_reasons(raw_candidate, duplicate=duplicate)
        missing_fields = _missing_fields(raw_candidate)
        flags = _state_flags(candidate, state)
        decision = evaluate_production_eligibility(
            candidate,
            ProductionEligibilityContext(
                preferences=dict(preferences or {}), now=now,
                watched=state.watched, watched_tmdb=state.watched_tmdb,
                excluded_actions=state.saved | state.hidden,
                excluded_action_tmdb=state.saved_tmdb | state.hidden_tmdb,
                recently_seen=state.recently_seen, seen=seen, seen_aliases=seen_aliases,
            ),
        )
        if decision.track_identity and decision.stable_identity is not None:
            seen.add(decision.stable_identity)
            seen_aliases.update(decision.aliases)
        if hard_reasons:
            hard_count += 1
            reason_counts.update(hard_reasons)
        if duplicate:
            duplicate_count += 1
        missing_counts.update(missing_fields)
        state_counts.update(flags)
        state_conflicts += int(len(flags) > 1)
        if decision.eligible:
            eligible_total += 1
            eligible_hard_leaks += int(bool(hard_reasons))
        if hard_reasons or missing_fields or flags:
            findings.append({
                "tmdb_id": raw_candidate.get("tmdb_id"), "media_type": raw_candidate.get("media_type"),
                "title": _title(raw_candidate), "hard_garbage_reasons": hard_reasons,
                "state_flags": flags, "missing_fields": missing_fields,
                "production_eligibility": decision.eligible,
                "production_reject_reason": decision.reason_code,
            })

    pool_total = len(pool)
    return {
        "summary": {
            "pool_total": pool_total, "pool_hard_garbage_count": hard_count,
            "pool_hard_garbage_rate": (hard_count / pool_total) if pool_total else 0.0,
            "eligible_total": eligible_total,
            "eligible_hard_garbage_leak_count": eligible_hard_leaks,
            "duplicate_identity_count": duplicate_count, "state_conflict_count": state_conflicts,
            "metadata_incomplete_count_by_field": dict(sorted(missing_counts.items())),
        },
        "reason_counts": dict(sorted(reason_counts.items())),
        "metadata_incomplete_counts": dict(sorted(missing_counts.items())),
        "state_counts": dict(sorted(state_counts.items())),
        "candidate_findings": findings,
        "production_context": {"uses_production_eligibility": True, "evaluated_at": now.isoformat()},
    }


def load_audit_state_read_only(db_path: Path, *, now: datetime) -> PoolAuditState:
    """Read state with SQLite ``mode=ro``; never migrates or writes the runtime."""
    if not db_path.is_file():
        return PoolAuditState(set(), set(), set(), set(), set(), set(), set())
    connection = sqlite3.connect(f"file:{db_path.resolve().as_posix()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        watched: set[tuple[str, str]] = set()
        watched_tmdb: set[tuple[str, int]] = set()
        for row in connection.execute("SELECT title, year, media_type, tmdb_id FROM watched_records"):
            candidate = dict(row)
            watched.add((title_identity_key(candidate), normalize_media_type(candidate.get("media_type"))))
            identity = candidate_tmdb_identity(candidate)
            if identity is not None:
                watched_tmdb.add(identity)
        saved: set[str] = set(); saved_tmdb: set[tuple[str, int]] = set()
        hidden: set[str] = set(); hidden_tmdb: set[tuple[str, int]] = set()
        for row in connection.execute("SELECT identity_key, action, candidate_json FROM candidate_actions"):
            entry = loads_json(row["candidate_json"], {})
            candidate = entry.get("candidate") if isinstance(entry, dict) else None
            target, target_tmdb = (saved, saved_tmdb) if row["action"] == "watchlist" else (hidden, hidden_tmdb)
            target.add(str(row["identity_key"]))
            if isinstance(candidate, dict):
                identity = candidate_tmdb_identity(candidate)
                if identity is not None:
                    target_tmdb.add(identity)
        cutoff = (now - timedelta(days=30)).isoformat(timespec="seconds")
        recently_seen = {
            (str(row["identity_key"]), normalize_media_type(row["media_type"]))
            for row in connection.execute(
                "SELECT identity_key, media_type FROM candidate_impressions WHERE julianday(last_shown_at) > julianday(?)",
                (cutoff,),
            )
        }
        return PoolAuditState(watched, watched_tmdb, saved, saved_tmdb, hidden, hidden_tmdb, recently_seen)
    finally:
        connection.close()


def load_pool_read_only(db_path: Path) -> dict[str, dict]:
    """Load candidate payloads through a read-only SQLite handle."""
    if not db_path.is_file():
        return {}
    connection = sqlite3.connect(f"file:{db_path.resolve().as_posix()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        return {
            str(row["pool_key"]): payload
            for row in connection.execute("SELECT pool_key, payload_json FROM candidate_records ORDER BY rowid")
            if isinstance((payload := loads_json(row["payload_json"], {})), dict)
        }
    finally:
        connection.close()

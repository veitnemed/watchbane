"""Deterministic, isolated synthetic taste-profile evaluation helpers.

This module is QA-only.  It seeds an isolated SQLite database through the
existing storage APIs, then calls the production RecommendationDeckService.
It must only be imported after WATCHBANE_DATA_DIR has been established.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from candidates.preferences import RecommendationVector
from candidates.recommendation_deck_service import RecommendationDeckService
from candidates.safety.explicit_content import evaluate_explicit_sexual_content
from candidates.title_state_service import add_to_watchlist, hide_candidate, mark_watched
from desktop.candidates.session import DEFAULT_BROWSE_FILTERS
from storage.sqlite.candidate_pool_repository import (
    load_candidate_pool_dict,
    save_candidate_pool_dict,
)


PROFILE_REQUIRED_FIELDS = frozenset(
    {
        "profile_id",
        "description",
        "media_types",
        "include",
        "exclude",
        "hard_exclusions",
        "preferences",
        "history",
        "vibe_alignment",
    }
)
PROFILE_ALLOWED_FIELDS = PROFILE_REQUIRED_FIELDS
INCLUDE_ALLOWED_FIELDS = frozenset(
    {
        "genres",
        "countries",
        "year_from",
        "year_to",
        "keywords",
        "min_tmdb_score",
        "min_tmdb_votes",
    }
)
EXCLUDE_ALLOWED_FIELDS = frozenset({"genres", "keywords"})
HARD_EXCLUSION_ALLOWED_FIELDS = frozenset(
    {
        "adult",
        "explicit_sexual_content",
        "watched",
        "hidden",
        "franchise_duplicates",
    }
)
PREFERENCE_ALLOWED_FIELDS = frozenset({"popularity", "novelty", "diversity"})
HISTORY_ALLOWED_FIELDS = frozenset({"watched", "saved", "hidden"})
VIBE_ALIGNMENT_REQUIRED_FIELDS = frozenset(
    {
        "description",
        "required_any_genres",
        "required_all_genres",
        "required_any_countries",
        "forbidden_genres",
        "forbidden_keywords",
        "minimum_matching_cards",
        "minimum_distinct_countries",
        "minimum_distinct_genres",
    }
)
VIBE_ALIGNMENT_ALLOWED_FIELDS = VIBE_ALIGNMENT_REQUIRED_FIELDS
MEDIA_TYPES = frozenset({"movie", "tv"})


class TasteProfileError(ValueError):
    """Raised for a malformed or unsupported synthetic taste profile."""


@dataclass(frozen=True)
class TasteProfile:
    """Validated profile payload; IDs in history refer to synthetic TMDb IDs."""

    payload: dict[str, Any]

    @property
    def profile_id(self) -> str:
        return str(self.payload["profile_id"])


def _require_mapping(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TasteProfileError(f"{path} must be an object")
    return dict(value)


def _reject_unknown_fields(payload: dict[str, Any], allowed: frozenset[str], path: str) -> None:
    unknown = sorted(str(key) for key in payload if key not in allowed)
    if unknown:
        raise TasteProfileError(f"Unknown field(s) at {path}: {', '.join(unknown)}")


def _require_exact_fields(payload: dict[str, Any], required: frozenset[str], path: str) -> None:
    missing = sorted(required.difference(payload))
    if missing:
        raise TasteProfileError(f"Missing required field(s) at {path}: {', '.join(missing)}")


def _string_list(value: Any, path: str) -> list[str]:
    if not isinstance(value, list):
        raise TasteProfileError(f"{path} must be an array")
    result: list[str] = []
    for item in value:
        text = str(item or "").strip()
        if not text:
            raise TasteProfileError(f"{path} must not contain empty values")
        if text not in result:
            result.append(text)
    return result


def _tmdb_id_list(value: Any, path: str) -> list[int]:
    if not isinstance(value, list):
        raise TasteProfileError(f"{path} must be an array of TMDb IDs")
    result: list[int] = []
    for item in value:
        if isinstance(item, bool):
            raise TasteProfileError(f"{path} must contain positive integer TMDb IDs")
        try:
            tmdb_id = int(item)
        except (TypeError, ValueError) as error:
            raise TasteProfileError(f"{path} must contain positive integer TMDb IDs") from error
        if tmdb_id <= 0:
            raise TasteProfileError(f"{path} must contain positive integer TMDb IDs")
        if tmdb_id not in result:
            result.append(tmdb_id)
    return result


def _level(value: Any, path: str) -> int:
    if isinstance(value, bool):
        raise TasteProfileError(f"{path} must be an integer from 0 to 4")
    try:
        level = int(value)
    except (TypeError, ValueError) as error:
        raise TasteProfileError(f"{path} must be an integer from 0 to 4") from error
    if level < 0 or level > 4:
        raise TasteProfileError(f"{path} must be an integer from 0 to 4")
    return level


def _optional_year(value: Any, path: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise TasteProfileError(f"{path} must be an integer year or null")
    try:
        return int(value)
    except (TypeError, ValueError) as error:
        raise TasteProfileError(f"{path} must be an integer year or null") from error


def _optional_number(value: Any, path: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise TasteProfileError(f"{path} must be a number or null")
    try:
        return float(value)
    except (TypeError, ValueError) as error:
        raise TasteProfileError(f"{path} must be a number or null") from error


def _optional_int(value: Any, path: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise TasteProfileError(f"{path} must be an integer or null")
    try:
        return int(value)
    except (TypeError, ValueError) as error:
        raise TasteProfileError(f"{path} must be an integer or null") from error


def _non_negative_int(value: Any, path: str) -> int:
    if isinstance(value, bool):
        raise TasteProfileError(f"{path} must be a non-negative integer")
    try:
        number = int(value)
    except (TypeError, ValueError) as error:
        raise TasteProfileError(f"{path} must be a non-negative integer") from error
    if number < 0:
        raise TasteProfileError(f"{path} must be a non-negative integer")
    return number


def _boolean(value: Any, path: str) -> bool:
    if not isinstance(value, bool):
        raise TasteProfileError(f"{path} must be boolean")
    return value


def validate_profile(payload: Any) -> TasteProfile:
    """Validate a strict JSON profile and return a normalized immutable wrapper."""
    root = _require_mapping(payload, "profile")
    _reject_unknown_fields(root, PROFILE_ALLOWED_FIELDS, "profile")
    _require_exact_fields(root, PROFILE_REQUIRED_FIELDS, "profile")

    profile_id = str(root["profile_id"] or "").strip()
    if not profile_id:
        raise TasteProfileError("profile.profile_id must be a non-empty string")
    if not str(root["description"] or "").strip():
        raise TasteProfileError("profile.description must be a non-empty string")

    media_types = _string_list(root["media_types"], "profile.media_types")
    invalid_media = sorted(set(media_types).difference(MEDIA_TYPES))
    if not media_types or invalid_media:
        raise TasteProfileError("profile.media_types must contain only movie and/or tv")

    include = _require_mapping(root["include"], "profile.include")
    _reject_unknown_fields(include, INCLUDE_ALLOWED_FIELDS, "profile.include")
    _require_exact_fields(
        include,
        frozenset({"genres", "countries", "year_from", "year_to", "keywords"}),
        "profile.include",
    )
    include["genres"] = _string_list(include["genres"], "profile.include.genres")
    include["countries"] = _string_list(include["countries"], "profile.include.countries")
    include["keywords"] = _string_list(include["keywords"], "profile.include.keywords")
    include["year_from"] = _optional_year(include["year_from"], "profile.include.year_from")
    include["year_to"] = _optional_year(include["year_to"], "profile.include.year_to")
    include["min_tmdb_score"] = _optional_number(
        include.get("min_tmdb_score"), "profile.include.min_tmdb_score"
    )
    include["min_tmdb_votes"] = _optional_int(
        include.get("min_tmdb_votes"), "profile.include.min_tmdb_votes"
    )
    if (
        include["year_from"] is not None
        and include["year_to"] is not None
        and include["year_from"] > include["year_to"]
    ):
        raise TasteProfileError("profile.include.year_from must not exceed year_to")

    exclude = _require_mapping(root["exclude"], "profile.exclude")
    _reject_unknown_fields(exclude, EXCLUDE_ALLOWED_FIELDS, "profile.exclude")
    _require_exact_fields(exclude, EXCLUDE_ALLOWED_FIELDS, "profile.exclude")
    exclude["genres"] = _string_list(exclude["genres"], "profile.exclude.genres")
    exclude["keywords"] = _string_list(exclude["keywords"], "profile.exclude.keywords")

    hard = _require_mapping(root["hard_exclusions"], "profile.hard_exclusions")
    _reject_unknown_fields(hard, HARD_EXCLUSION_ALLOWED_FIELDS, "profile.hard_exclusions")
    _require_exact_fields(
        hard,
        frozenset({"adult", "explicit_sexual_content", "watched", "hidden"}),
        "profile.hard_exclusions",
    )
    for key in HARD_EXCLUSION_ALLOWED_FIELDS:
        if key in hard:
            hard[key] = _boolean(hard[key], f"profile.hard_exclusions.{key}")
    hard.setdefault("franchise_duplicates", False)

    preferences = _require_mapping(root["preferences"], "profile.preferences")
    _reject_unknown_fields(preferences, PREFERENCE_ALLOWED_FIELDS, "profile.preferences")
    _require_exact_fields(preferences, PREFERENCE_ALLOWED_FIELDS, "profile.preferences")
    for key in PREFERENCE_ALLOWED_FIELDS:
        preferences[key] = _level(preferences[key], f"profile.preferences.{key}")

    history = _require_mapping(root["history"], "profile.history")
    _reject_unknown_fields(history, HISTORY_ALLOWED_FIELDS, "profile.history")
    _require_exact_fields(history, HISTORY_ALLOWED_FIELDS, "profile.history")
    for key in HISTORY_ALLOWED_FIELDS:
        history[key] = _tmdb_id_list(history[key], f"profile.history.{key}")
    overlap = set(history["watched"]).intersection(history["saved"], history["hidden"])
    if overlap:
        raise TasteProfileError("profile.history entries must not appear in more than one state")
    if set(history["saved"]).intersection(history["hidden"]):
        raise TasteProfileError("profile.history entries must not appear in more than one state")

    vibe = _require_mapping(root["vibe_alignment"], "profile.vibe_alignment")
    _reject_unknown_fields(vibe, VIBE_ALIGNMENT_ALLOWED_FIELDS, "profile.vibe_alignment")
    _require_exact_fields(vibe, VIBE_ALIGNMENT_REQUIRED_FIELDS, "profile.vibe_alignment")
    if not str(vibe["description"] or "").strip():
        raise TasteProfileError("profile.vibe_alignment.description must be a non-empty string")
    for key in (
        "required_any_genres",
        "required_all_genres",
        "required_any_countries",
        "forbidden_genres",
        "forbidden_keywords",
    ):
        vibe[key] = _string_list(vibe[key], f"profile.vibe_alignment.{key}")
    for key in (
        "minimum_matching_cards",
        "minimum_distinct_countries",
        "minimum_distinct_genres",
    ):
        vibe[key] = _non_negative_int(vibe[key], f"profile.vibe_alignment.{key}")
    vibe["description"] = str(vibe["description"]).strip()

    return TasteProfile(
        {
            "profile_id": profile_id,
            "description": str(root["description"]).strip(),
            "media_types": media_types,
            "include": include,
            "exclude": exclude,
            "hard_exclusions": hard,
            "preferences": preferences,
            "history": history,
            "vibe_alignment": vibe,
        }
    )


def load_profile(path: Path | str) -> TasteProfile:
    """Load and validate one UTF-8 JSON taste profile."""
    source = Path(path)
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise TasteProfileError(f"Invalid JSON profile {source}: {error.msg}") from error
    except OSError as error:
        raise TasteProfileError(f"Unable to read profile {source}: {error}") from error
    return validate_profile(payload)


def resolve_profile(profile: TasteProfile) -> dict[str, Any]:
    """Map compatible values to existing filters/vector; retain unmapped audit context."""
    source = profile.payload
    include = dict(source["include"])
    preferences = dict(source["preferences"])
    media_types = set(source["media_types"])
    filters = {
        **dict(DEFAULT_BROWSE_FILTERS),
        "country": list(include["countries"]),
        "media_type": next(iter(media_types)) if len(media_types) == 1 else None,
        "year_min": include["year_from"],
        "year_max": include["year_to"],
        "include_genres": list(include["genres"]),
        "exclude_genres": list(source["exclude"]["genres"]),
        "min_tmdb_score": include["min_tmdb_score"],
        "min_tmdb_votes": include["min_tmdb_votes"],
        "only_complete": True,
        "only_unwatched": bool(source["hard_exclusions"]["watched"]),
        "hide_hidden": bool(source["hard_exclusions"]["hidden"]),
    }
    vector = RecommendationVector(
        openness_level=preferences["novelty"],
        rarity_level=4 - preferences["popularity"],
        diversity_level=preferences["diversity"],
    ).to_dict()
    return {
        "candidate_filters": filters,
        "recommendation_vector": vector,
        "audit_only_constraints": {
            "include_keywords": list(include["keywords"]),
            "exclude_keywords": list(source["exclude"]["keywords"]),
            "adult": bool(source["hard_exclusions"]["adult"]),
            "explicit_sexual_content": bool(
                source["hard_exclusions"]["explicit_sexual_content"]
            ),
            "franchise_duplicates": bool(
                source["hard_exclusions"].get("franchise_duplicates", False)
            ),
            "note": (
                "Keyword and franchise constraints are audit-only because the current "
                "recommendation filter contract has no equivalent fields; they never "
                "alter candidate eligibility or ranking."
            ),
        },
    }


def _candidate(
    tmdb_id: int,
    title: str,
    *,
    media_type: str,
    year: int,
    genres: list[str],
    countries: list[str],
    score: float = 7.8,
    votes: int = 400,
    popularity: float = 70.0,
    adult: bool = False,
    content_rating: str = "TV-14",
    keywords: list[str] | None = None,
    franchise_id: str | None = None,
) -> dict[str, Any]:
    return {
        "pool_entry_key": f"synthetic-{tmdb_id}|{year}|{media_type}",
        "tmdb_id": tmdb_id,
        "title": title,
        "original_title": title,
        "media_type": media_type,
        "year": year,
        "genres": list(genres),
        "genre_keys": list(genres),
        "countries": list(countries),
        "country_codes": list(countries),
        "overview": f"Synthetic fixture overview for {title}.",
        "adult": adult,
        "content_rating": content_rating,
        "keywords": list(keywords or []),
        "franchise_id": franchise_id,
        "tmdb_score": score,
        "tmdb_votes": votes,
        "tmdb_popularity": popularity,
        "quality_score": score / 10,
        "hidden_gem_score": 0.35,
        "final_score": score / 10,
        "is_complete": True,
    }


def build_fixed_synthetic_pool() -> dict[str, dict[str, Any]]:
    """Return an offline, deterministic fixture pool sufficient for all profiles."""
    candidates: list[dict[str, Any]] = []
    p1_genres = (["drama"], ["crime", "drama"], ["sci_fi_fantasy", "drama"])
    for offset in range(15):
        tmdb_id = 1001 + offset
        candidates.append(
            _candidate(
                tmdb_id,
                f"Mainstream Fixture {offset + 1}",
                media_type="movie" if offset % 2 == 0 else "tv",
                year=2010 + offset,
                genres=list(p1_genres[offset % len(p1_genres)]),
                countries=["US" if offset % 2 == 0 else "GB"],
                score=7.2 + (offset % 5) * 0.2,
                votes=500 + offset * 70,
                popularity=120 + offset * 11,
            )
        )

    for offset in range(16):
        tmdb_id = 2001 + offset
        explicit = offset == 15
        candidates.append(
            _candidate(
                tmdb_id,
                f"Dark Anime Fixture {offset + 1}",
                media_type="tv",
                year=2005 + offset,
                genres=["animation", "mystery", "thriller"],
                countries=["JP"],
                score=7.4 + (offset % 4) * 0.2,
                votes=250 + offset * 30,
                popularity=35 + offset * 4,
                adult=explicit,
                content_rating="R18+" if explicit else "TV-14",
                keywords=["hentai", "ecchi"] if explicit else ["psychological"],
            )
        )

    p3_countries = ("KR", "FR", "BR", "IN", "SE", "MX", "DE", "AR", "NG", "ES", "TR", "AU")
    p3_genres = (
        "mystery",
        "drama",
        "crime",
        "sci_fi_fantasy",
        "comedy",
        "history",
        "horror",
        "action_adventure",
        "romance",
        "documentary",
        "music",
        "thriller",
    )
    for offset, (country, genre) in enumerate(zip(p3_countries, p3_genres), start=1):
        tmdb_id = 3000 + offset
        candidates.append(
            _candidate(
                tmdb_id,
                f"Explorer Fixture {offset}",
                media_type="movie" if offset % 2 else "tv",
                year=2004 + offset,
                genres=[genre],
                countries=[country],
                score=7.0 + (offset % 5) * 0.25,
                votes=130 + offset * 35,
                popularity=18 + offset * 3,
                franchise_id=f"explorer-{offset}",
            )
        )
    return {str(candidate["pool_entry_key"]): candidate for candidate in candidates}


def _history_candidates(profile: TasteProfile, pool: dict[str, dict[str, Any]]) -> dict[str, list[dict]]:
    by_tmdb_id = {int(candidate["tmdb_id"]): candidate for candidate in pool.values()}
    resolved: dict[str, list[dict]] = {}
    for state, ids in profile.payload["history"].items():
        missing = [tmdb_id for tmdb_id in ids if tmdb_id not in by_tmdb_id]
        if missing:
            raise TasteProfileError(
                f"profile.history.{state} references missing synthetic TMDb IDs: {missing}"
            )
        resolved[state] = [deepcopy(by_tmdb_id[tmdb_id]) for tmdb_id in ids]
    return resolved


def seed_synthetic_history(
    profile: TasteProfile,
    pool: dict[str, dict[str, Any]],
    *,
    db_path: Path,
) -> dict[str, list[int]]:
    """Seed pool + watched/saved/hidden through the production write APIs."""
    save_candidate_pool_dict(pool, path=db_path, purge_watched=False)
    history = _history_candidates(profile, pool)
    for candidate in history["watched"]:
        mark_watched(candidate, optional_user_score=3, path=db_path)
    for candidate in history["saved"]:
        add_to_watchlist(candidate, path=db_path)
    for candidate in history["hidden"]:
        hide_candidate(candidate, path=db_path)
    return {
        state: [int(candidate["tmdb_id"]) for candidate in candidates]
        for state, candidates in history.items()
    }


def _title(candidate: dict[str, Any]) -> str:
    return str(candidate.get("title") or candidate.get("original_title") or "").strip()


def _candidate_report(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "tmdb_id": candidate.get("tmdb_id"),
        "title": _title(candidate),
        "original_title": str(candidate.get("original_title") or "").strip(),
        "media_type": candidate.get("media_type"),
        "genres": list(candidate.get("genre_keys") or candidate.get("genres") or []),
        "countries": list(candidate.get("country_codes") or candidate.get("countries") or []),
        "year": candidate.get("year"),
        "adult": bool(candidate.get("adult")),
        "content_rating": candidate.get("content_rating"),
        "vote_average": candidate.get("tmdb_score"),
        "vote_count": candidate.get("tmdb_votes"),
        "recommendation_score": candidate.get("final_score") or candidate.get("quality_score"),
        "overview": str(candidate.get("overview") or "").strip(),
        "keywords": list(candidate.get("keywords") or []),
        "explicit_content_decision": evaluate_explicit_sexual_content(candidate).to_dict(),
        "franchise_id": candidate.get("franchise_id"),
    }


def evaluate_vibe_alignment(
    profile: TasteProfile,
    recommendations: list[dict[str, Any]],
) -> dict[str, Any]:
    """Audit fixed vibe expectations against returned metadata; never change ranking."""
    rubric = profile.payload["vibe_alignment"]
    required_any_genres = set(rubric["required_any_genres"])
    required_all_genres = set(rubric["required_all_genres"])
    required_countries = set(rubric["required_any_countries"])
    forbidden_genres = set(rubric["forbidden_genres"])
    forbidden_keywords = {value.casefold() for value in rubric["forbidden_keywords"]}
    cards: list[dict[str, Any]] = []
    for candidate in recommendations:
        genres = set(candidate.get("genre_keys") or candidate.get("genres") or [])
        countries = set(candidate.get("country_codes") or candidate.get("countries") or [])
        keywords = {str(value).casefold() for value in (candidate.get("keywords") or [])}
        reasons: list[str] = []
        if required_any_genres and not genres.intersection(required_any_genres):
            reasons.append("missing_required_any_genre")
        if required_all_genres and not required_all_genres.issubset(genres):
            reasons.append("missing_required_all_genres")
        if required_countries and not countries.intersection(required_countries):
            reasons.append("wrong_country")
        if genres.intersection(forbidden_genres):
            reasons.append("forbidden_genre")
        if keywords.intersection(forbidden_keywords):
            reasons.append("forbidden_keyword")
        cards.append(
            {
                "tmdb_id": candidate.get("tmdb_id"),
                "title": _title(candidate),
                "genres": sorted(genres),
                "countries": sorted(countries),
                "aligned": not reasons,
                "reasons": reasons,
            }
        )
    aligned_cards = sum(1 for card in cards if card["aligned"])
    distinct_countries = sorted(
        {country for card in cards for country in card["countries"]}
    )
    distinct_genres = sorted({genre for card in cards for genre in card["genres"]})
    criteria = {
        "minimum_matching_cards": {
            "expected": rubric["minimum_matching_cards"],
            "actual": aligned_cards,
            "passed": aligned_cards >= rubric["minimum_matching_cards"],
        },
        "minimum_distinct_countries": {
            "expected": rubric["minimum_distinct_countries"],
            "actual": len(distinct_countries),
            "passed": len(distinct_countries) >= rubric["minimum_distinct_countries"],
        },
        "minimum_distinct_genres": {
            "expected": rubric["minimum_distinct_genres"],
            "actual": len(distinct_genres),
            "passed": len(distinct_genres) >= rubric["minimum_distinct_genres"],
        },
    }
    return {
        "description": rubric["description"],
        "audit_only": True,
        "note": "This rubric evaluates returned metadata only; it never changes product filtering or ranking.",
        "criteria": criteria,
        "distinct_countries": distinct_countries,
        "distinct_genres": distinct_genres,
        "cards": cards,
        "passed": all(criterion["passed"] for criterion in criteria.values()),
    }


def _hard_checks(
    profile: TasteProfile,
    resolved: dict[str, Any],
    deck: dict[str, Any],
    recommendations: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    history = profile.payload["history"]
    selected_ids = [int(item["tmdb_id"]) for item in recommendations if item.get("tmdb_id") is not None]
    selected_genres = [set(item.get("genres") or []) for item in recommendations]
    allowed_media = set(profile.payload["media_types"])
    excluded_genres = set(resolved["candidate_filters"]["exclude_genres"])
    audit = resolved["audit_only_constraints"]
    excluded_keywords = {value.casefold() for value in audit["exclude_keywords"]}
    keyword_hits = [
        item["tmdb_id"]
        for item in recommendations
        if excluded_keywords.intersection(
            str(keyword).casefold()
            for keyword in (item.get("keywords") or [])
        )
    ]
    franchise_ids = [str(item.get("franchise_id") or "") for item in recommendations]
    duplicate_franchises = sorted(
        value for value in set(franchise_ids) if value and franchise_ids.count(value) > 1
    )
    checks = {
        "adult_violation": [item["tmdb_id"] for item in recommendations if item.get("adult")],
        "explicit_content_violation": [
            item["tmdb_id"]
            for item in recommendations
            if evaluate_explicit_sexual_content(item).blocked
        ],
        "watched_leak": sorted(set(selected_ids).intersection(history["watched"])),
        "saved_leak": sorted(set(selected_ids).intersection(history["saved"])),
        "hidden_leak": sorted(set(selected_ids).intersection(history["hidden"])),
        "duplicate_tmdb_id": sorted(
            value for value in set(selected_ids) if selected_ids.count(value) > 1
        ),
        "wrong_media_type": [
            item["tmdb_id"] for item in recommendations if item.get("media_type") not in allowed_media
        ],
        "excluded_genre": [
            recommendations[index]["tmdb_id"]
            for index, genres in enumerate(selected_genres)
            if genres.intersection(excluded_genres)
        ],
        "excluded_keyword_audit_only": keyword_hits,
        "missing_readable_title": [
            item["tmdb_id"] for item in recommendations if not _title(item)
        ],
        "duplicate_franchise_audit_only": duplicate_franchises,
        "underfilled_despite_eligible": (
            len(recommendations) < 10 and int(deck.get("catalog_eligible_count") or 0) >= 10
        ),
    }
    return {
        name: {"passed": not bool(value), "violations": value}
        for name, value in checks.items()
    }


def evaluate_profile(
    profile: TasteProfile,
    *,
    runtime_root: Path,
    app_data_dir: Path,
    commit: str,
    app_version: str,
) -> dict[str, Any]:
    """Run one profile through the production deck service in its own SQLite DB."""
    resolved = resolve_profile(profile)
    profile_root = runtime_root / profile.profile_id
    db_path = profile_root / "watchbane.sqlite3"
    pool = build_fixed_synthetic_pool()
    history = seed_synthetic_history(profile, pool, db_path=db_path)
    service = RecommendationDeckService(
        pool_loader=lambda: load_candidate_pool_dict(path=db_path),
        db_path=db_path,
        recent_days=0,
    )
    deck = service.build_deck(
        resolved["candidate_filters"],
        datetime(2026, 7, 19, tzinfo=timezone.utc),
        vector=resolved["recommendation_vector"],
        variation_seed=0,
        limit_active=10,
        reserve_size=0,
    )
    active = [dict(candidate) for candidate in deck.get("active") or []]
    checks = _hard_checks(profile, resolved, deck, active)
    vibe_alignment = evaluate_vibe_alignment(profile, active)
    return {
        "commit": commit,
        "app_version": app_version,
        "profile_id": profile.profile_id,
        "description": profile.payload["description"],
        "resolved_runtime_path": str(profile_root.resolve()),
        "isolation_proof": {
            "runtime_root": str(runtime_root.resolve()),
            "app_data_dir": str(app_data_dir.resolve()),
            "app_data_dir_inside_runtime": app_data_dir.resolve().is_relative_to(runtime_root.resolve()),
        },
        "applied_filters": resolved["candidate_filters"],
        "recommendation_vector": resolved["recommendation_vector"],
        "audit_only_constraints": resolved["audit_only_constraints"],
        "synthetic_history": history,
        "deck_summary": {
            "eligible_count": deck.get("eligible_count"),
            "catalog_eligible_count": deck.get("catalog_eligible_count"),
            "underfilled_reason": deck.get("underfilled_reason"),
            "excluded": deck.get("excluded"),
        },
        "top_10": [_candidate_report(candidate) for candidate in active],
        "hard_checks": checks,
        "all_hard_checks_passed": all(check["passed"] for check in checks.values()),
        "vibe_alignment": vibe_alignment,
        "determinism": {
            "now": "2026-07-19T00:00:00+00:00",
            "variation_seed": 0,
            "pool": "build_fixed_synthetic_pool v1",
            "note": "Deck ID and storage timestamps are intentionally omitted from comparison; top_10 is deterministic for this fixture/date/seed.",
        },
    }

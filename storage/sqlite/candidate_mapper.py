"""Candidate-record mapping from compatibility payloads to SQLite rows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from candidates.models.keys import normalize_key_part, pool_entry_key
from candidates.models.schema import coerce_candidate_number
from dataset.models.media_type import normalize_media_type
from storage.sqlite.json_codec import dumps_json


def _as_dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if text != "" else None


def _number(value: Any) -> int | float | None:
    return coerce_candidate_number(value)


def _int_or_none(value: Any) -> int | None:
    number = _number(value)
    if isinstance(number, bool) or number is None:
        return None
    return int(number)


def _float_or_none(value: Any) -> float | None:
    number = _number(value)
    if isinstance(number, bool) or number is None:
        return None
    return float(number)


def _first_value(*values: Any) -> Any:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and value.strip() == "":
            continue
        return value
    return None


def _year_from(value: Any) -> int | None:
    year = _int_or_none(value)
    if year is not None:
        return year
    text = _clean_text(value)
    if text is not None and len(text) >= 4 and text[:4].isdigit():
        return int(text[:4])
    return None


def _tmdb_id_from(*sections: dict) -> int | None:
    for section in sections:
        value = _first_value(
            section.get("tmdb_id"),
            section.get("tmdbId"),
            section.get("id") if section.get("source") == "tmdb" else None,
        )
        result = _int_or_none(value)
        if result is not None:
            return result
    return None


@dataclass(frozen=True)
class CandidateRecordRow:
    pool_key: str
    title: str
    title_normalized: str
    media_type: str
    year: int | None
    tmdb_id: int | None
    criteria_name: str | None
    tmdb_score: float | None
    tmdb_votes: int | None
    tmdb_popularity: float | None
    quality_score: float | None
    hidden_gem_score: float | None
    final_score: float | None
    source: str | None
    source_bucket_id: str | None
    onboarding_profile_id: int | None
    candidate_score: float | None
    fetch_rank: int | None
    payload_json: str


def extract_candidate_record(pool_key: str | None, record: dict) -> CandidateRecordRow:
    """Extract indexed candidate columns while preserving original payload."""
    candidate = _as_dict(record)
    title = _clean_text(
        _first_value(
            candidate.get("title"),
            candidate.get("alternative_title"),
            candidate.get("name"),
            candidate.get("alternativeName"),
            candidate.get("enName"),
        )
    ) or ""
    year = _year_from(_first_value(candidate.get("year"), candidate.get("first_air_date"), candidate.get("release_date")))
    payload_for_key = dict(candidate)
    if year is not None:
        payload_for_key["year"] = year
    resolved_pool_key = str(pool_key or "").strip() or pool_entry_key(payload_for_key)

    return CandidateRecordRow(
        pool_key=resolved_pool_key,
        title=title,
        title_normalized=normalize_key_part(title),
        media_type=normalize_media_type(candidate.get("media_type")),
        year=year,
        tmdb_id=_tmdb_id_from(candidate),
        criteria_name=_clean_text(candidate.get("criteria_name")),
        tmdb_score=_float_or_none(candidate.get("tmdb_score")),
        tmdb_votes=_int_or_none(candidate.get("tmdb_votes")),
        tmdb_popularity=_float_or_none(candidate.get("tmdb_popularity")),
        quality_score=_float_or_none(candidate.get("quality_score")),
        hidden_gem_score=_float_or_none(candidate.get("hidden_gem_score")),
        final_score=_float_or_none(candidate.get("final_score")),
        source=_clean_text(candidate.get("source")),
        source_bucket_id=_clean_text(candidate.get("source_bucket_id")),
        onboarding_profile_id=_int_or_none(candidate.get("onboarding_profile_id")),
        candidate_score=_float_or_none(candidate.get("candidate_score")),
        fetch_rank=_int_or_none(candidate.get("fetch_rank")),
        payload_json=dumps_json(candidate),
    )

"""Pure JSON-to-SQLite row extraction helpers."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any

from candidates.models.keys import normalize_key_part, pool_entry_key
from candidates.models.schema import coerce_candidate_number
from dataset.models.identity import normalize_title_key
from dataset.models.media_type import normalize_media_type


def dumps_json(value: Any) -> str:
    """Serialize canonical JSON for SQLite payload columns."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def loads_json(value: str | None, default: Any = None) -> Any:
    if value in (None, ""):
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


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
class WatchedRecordRow:
    dataset_key: str
    title: str
    title_normalized: str
    media_type: str
    year: int | None
    user_score: float | None
    country: str | None
    tmdb_id: int | None
    imdb_id: str | None
    payload_json: str
    meta_json: str | None


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
    payload_json: str


def extract_watched_record(
    dataset_key: str,
    record: dict,
    *,
    meta: dict | None = None,
) -> WatchedRecordRow:
    """Extract indexed watched columns while preserving original payloads."""
    movie = _as_dict(record)
    meta_obj = _as_dict(meta)
    main_info = _as_dict(movie.get("main_info"))
    raw_scores = _as_dict(movie.get("raw_scores"))
    meta_main_info = _as_dict(meta_obj.get("main_info"))
    meta_raw_scores = _as_dict(meta_obj.get("raw_scores"))

    title = _clean_text(
        _first_value(main_info.get("title"), meta_main_info.get("title"), movie.get("title"))
    ) or str(dataset_key).strip()
    media_type = normalize_media_type(
        _first_value(main_info.get("media_type"), meta_main_info.get("media_type"), movie.get("media_type"))
    )
    year = _year_from(_first_value(main_info.get("year"), meta_main_info.get("year"), movie.get("year")))
    tmdb_id = _tmdb_id_from(raw_scores, meta_raw_scores, movie, meta_obj)
    imdb_id = _clean_text(
        _first_value(
            raw_scores.get("imdb_id"),
            meta_raw_scores.get("imdb_id"),
            movie.get("imdb_id"),
            meta_obj.get("imdb_id"),
        )
    )

    return WatchedRecordRow(
        dataset_key=str(dataset_key),
        title=title,
        title_normalized=normalize_title_key(title),
        media_type=media_type,
        year=year,
        user_score=_float_or_none(_first_value(main_info.get("user_score"), movie.get("user_score"))),
        country=_clean_text(_first_value(main_info.get("country"), movie.get("country"))),
        tmdb_id=tmdb_id,
        imdb_id=imdb_id,
        payload_json=dumps_json(movie),
        meta_json=dumps_json(meta_obj) if isinstance(meta, dict) else None,
    )


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
    year = _year_from(_first_value(candidate.get("year"), candidate.get("first_air_date")))
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
        payload_json=dumps_json(candidate),
    )

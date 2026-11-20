"""Watched-record mapping from compatibility payloads to SQLite rows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from candidates.models.schema import coerce_candidate_number
from dataset.models.identity import normalize_title_key
from dataset.models.media_type import MOVIE_MEDIA_TYPE_ALIASES, TV_MEDIA_TYPE_ALIASES, normalize_media_type
from dataset.models.user_rating import normalize_user_rating
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
class WatchedRecordRow:
    dataset_key: str
    title: str
    title_normalized: str
    media_type: str
    year: int | None
    user_score: int | None
    country: str | None
    tmdb_id: int | None
    imdb_id: str | None
    payload_json: str
    meta_json: str | None


def metadata_watched_projection(meta: Any) -> dict | None:
    """Honor nested legacy and flat Story metadata without changing raw JSON."""
    if not isinstance(meta, dict):
        return None
    main_info = dict(_as_dict(meta.get("main_info")))
    if _clean_text(main_info.get("media_type")) is None and "media_type" in meta:
        main_info["media_type"] = meta["media_type"]
    return {**meta, "main_info": main_info}


def metadata_watched_identity(meta: Any) -> tuple[str, int] | None:
    """Recognize an explicit retained identity; never infer the default type."""
    projected = metadata_watched_projection(meta)
    if projected is None:
        return None
    raw_type = _clean_text(projected["main_info"].get("media_type"))
    types = MOVIE_MEDIA_TYPE_ALIASES | TV_MEDIA_TYPE_ALIASES
    if raw_type is None or raw_type.casefold() not in types:
        return None
    media = normalize_media_type(raw_type)
    flat_type = _clean_text(projected.get("media_type"))
    if flat_type and (flat_type.casefold() not in types or normalize_media_type(flat_type) != media):
        return None
    ids: set[int] = set()
    for section in (_as_dict(projected.get("raw_scores")), projected):
        values = [section.get("tmdb_id"), section.get("tmdbId")]
        if section.get("source") == "tmdb":
            values.append(section.get("id"))
        for value in values:
            if value is None or value == "":
                continue
            if type(value) is int:
                identifier = value
            elif isinstance(value, str) and (digits := value.strip()).isascii() and digits.isdecimal() and len(digits) <= 19:
                identifier = int(digits)
            else:
                return None
            if not 0 < identifier < 2**63:
                return None
            ids.add(identifier)
    return (media, next(iter(ids))) if len(ids) == 1 else None


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
        user_score=normalize_user_rating(_first_value(main_info.get("user_score"), movie.get("user_score"))),
        country=_clean_text(_first_value(main_info.get("country"), movie.get("country"))),
        tmdb_id=tmdb_id,
        imdb_id=imdb_id,
        payload_json=dumps_json(movie),
        meta_json=dumps_json(meta_obj) if isinstance(meta, dict) else None,
    )

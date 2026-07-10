"""TMDb-only defaults builder kept for compatibility with old imports."""

from __future__ import annotations

from config import scheme
from dataset.resolve.countries import extract_country_value
from dataset.resolve.defaults import build_tmdb_add_defaults, extract_tmdb_description
from dataset.resolve.genres import extract_tmdb_genres


def _source_if(value, source: str = "tmdb_api") -> str | None:
    return source if value not in (None, "", []) else None


def first_value(*items):
    """Return first non-empty value and its source."""
    for value, source in items:
        if value not in (None, "", []):
            return value, source
    return None, None


def extract_tmdb_title(series: dict | None) -> str:
    """Return title from a normalized TMDb object."""
    if not isinstance(series, dict):
        return ""
    for key in ("title", "name", "original_title", "original_name"):
        value = str(series.get(key) or "").strip()
        if value:
            return value
    return ""


def build_add_defaults_from_tmdb(input_title: str, tmdb_data: dict | None) -> dict:
    """Build add-title defaults using only TMDb data plus input fallback."""
    tmdb_data = tmdb_data if isinstance(tmdb_data, dict) else {}
    defaults = build_tmdb_add_defaults(tmdb_data)
    if defaults[scheme.MAIN_INFO].get("title") in (None, ""):
        defaults[scheme.MAIN_INFO]["title"] = input_title

    description = extract_tmdb_description(tmdb_data)
    genres = extract_tmdb_genres(tmdb_data)
    sources = {
        "title": "tmdb_api" if extract_tmdb_title(tmdb_data) else "input",
        "year": _source_if(defaults[scheme.MAIN_INFO].get("year")),
        "country": _source_if(extract_country_value(tmdb_data)),
        "tmdb_score": _source_if(defaults[scheme.RAW_SCORES].get("tmdb_score")),
        "tmdb_votes": _source_if(defaults[scheme.RAW_SCORES].get("tmdb_votes")),
        "tmdb_popularity": _source_if(defaults[scheme.RAW_SCORES].get("tmdb_popularity")),
        "genres": _source_if(genres),
        "description": _source_if(description),
    }
    return {
        "defaults": defaults,
        "sources": sources,
        "source_values": {
            "genres": genres,
            "description": description,
        },
    }


def build_add_defaults_by_priority(
    input_title: str,
    tmdb_data: dict | None,
) -> dict:
    """Compatibility wrapper: builds add-title defaults from TMDb data only."""
    return build_add_defaults_from_tmdb(input_title, tmdb_data)

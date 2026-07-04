"""Compact read-only card dicts built from dataset records."""

from __future__ import annotations

from pathlib import Path

from candidates.models import country_schema
from candidates.models.keys import title_identity_key
from config import constant
from posters.cache import lookup_poster_cache_entry


def _as_dict(value) -> dict:
    return value if isinstance(value, dict) else {}


def _as_list(value) -> list:
    if isinstance(value, list):
        return list(value)
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, set):
        return list(value)
    return []


def _clean_text(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if text != "" else None


def _to_float(value) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _list_text_values(value) -> list[str]:
    items = _as_list(value)
    if len(items) == 0 and isinstance(value, str):
        items = [part.strip() for part in value.split(",")]

    result = []
    for item in items:
        if isinstance(item, dict):
            text = _clean_text(item.get("name") or item.get("label") or item.get("title"))
        else:
            text = _clean_text(item)
        if text is not None and text not in result:
            result.append(text)
    return result


def _first_text(movie: dict, *field_names: str) -> str | None:
    sections = [
        movie,
        _as_dict(movie.get("main_info")),
        _as_dict(movie.get("raw_scores")),
        _as_dict(movie.get("source_values")),
        _as_dict(movie.get("meta")),
        _as_dict(movie.get("tmdb_data")),
    ]

    for section in sections:
        for field_name in field_names:
            text = _clean_text(section.get(field_name))
            if text is not None:
                return text
    return None


def _poster_url(movie: dict) -> str | None:
    poster = _as_dict(movie.get("poster"))
    return _first_text(movie, "poster_url", "posterUrl", "preview_url", "previewUrl") or _clean_text(
        poster.get("url") or poster.get("previewUrl")
    )


def _poster_path(movie: dict) -> str | None:
    poster = _as_dict(movie.get("poster"))
    return _first_text(movie, "poster_path", "posterPath") or _clean_text(
        poster.get("path") or poster.get("poster_path")
    )


def _local_poster_path(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if text == "" or text.startswith(("http://", "https://")):
        return None
    path = Path(text)
    return str(path) if path.is_file() else None


def _resolve_poster_fields(movie: dict, poster_cache: dict | None = None) -> dict:
    poster_url = _poster_url(movie)
    poster_path = _poster_path(movie)
    poster_source = "existing_field" if poster_url or poster_path else None

    main_info = _as_dict(movie.get("main_info"))
    title = _clean_text(main_info.get("title")) or _clean_text(movie.get("title")) or ""
    year = _to_int(main_info.get("year", movie.get("year")))
    cache_entry = lookup_poster_cache_entry(title, year, cache=poster_cache)

    if cache_entry and cache_entry.get("status") == "found":
        if poster_url is None:
            poster_url = _clean_text(cache_entry.get("poster_url"))
        if poster_path is None:
            poster_path = _clean_text(cache_entry.get("poster_path"))
        if poster_source is None:
            poster_source = _clean_text(cache_entry.get("source")) or "poster_cache"

    local_path = _local_poster_path(poster_path)
    if local_path is None and cache_entry:
        local_path = _local_poster_path(cache_entry.get("local_path"))
    if local_path is None and title:
        from posters.cache import default_local_poster_path

        local_path = default_local_poster_path(title, year)

    poster_src = local_path or poster_url or poster_path
    return {
        "poster_url": poster_url,
        "poster_path": poster_path,
        "poster_src": poster_src,
        "poster_source": poster_source,
    }


def _country(movie: dict) -> str | None:
    display = _first_text(movie, "country_display")
    if display is not None:
        codes = country_schema.normalize_country_filter_list(display)
        return country_schema.build_country_display(codes) or display

    for field_name in (
        "country_codes",
        "origin_country",
        "tmdb_country_codes",
        "tmdb_origin_countries",
    ):
        codes = country_schema.normalize_country_filter_list(movie.get(field_name))
        display = country_schema.build_country_display(codes)
        if display is not None:
            return display

    for field_name in ("countries", "production_countries", "tmdb_production_countries"):
        values = _list_text_values(movie.get(field_name))
        if len(values) > 0:
            display = country_schema.build_country_display(
                country_schema.normalize_country_filter_list(values)
            )
            return display or ", ".join(values)

    country = _first_text(movie, "country")
    if country is None:
        return None
    display = country_schema.build_country_display(
        country_schema.normalize_country_filter_list(country)
    )
    return display or country


def _object_type(movie: dict, default: str = "unknown") -> str:
    text = _first_text(movie, "object_type", "media_type", "title_type")
    if text is not None:
        return text
    return default


def _pool_candidate_for_title(title: str, year, lookup_cache: dict | None) -> dict | None:
    if lookup_cache is None:
        return None
    pool_by_identity = lookup_cache.get("pool_by_identity") or {}
    candidate = pool_by_identity.get(title_identity_key({"title": title, "year": year}))
    return candidate if isinstance(candidate, dict) else None


def _first_number(field_name: str, sections: list[dict], converter):
    for section in sections:
        value = converter(section.get(field_name))
        if value is not None:
            return value
    return None


def _first_existing(field_name: str, sections: list[dict]):
    for section in sections:
        value = section.get(field_name)
        if value not in (None, "", []):
            return value
    return None


def _tmdb_score_sections(movie: dict, raw_scores: dict, meta_obj: dict | None, pool_candidate: dict | None) -> list[dict]:
    sections = [raw_scores, movie]
    if isinstance(meta_obj, dict):
        sections.extend([_as_dict(meta_obj.get("raw_scores")), meta_obj])
    if isinstance(pool_candidate, dict):
        sections.append(pool_candidate)
    return sections


def _compute_watched_tmdb_scores(movie: dict, sections: list[dict], country: str | None) -> dict:
    if _first_number("tmdb_score", sections, _to_float) is None:
        return {}

    candidate_like = {
        "title": _first_existing("title", sections),
        "year": _first_number("year", sections, _to_int),
        "tmdb_score": _first_number("tmdb_score", sections, _to_float),
        "tmdb_votes": _first_number("tmdb_votes", sections, _to_int),
        "tmdb_popularity": _first_number("tmdb_popularity", sections, _to_float),
        "country": country,
        "countries": _first_existing("countries", sections),
        "country_codes": _first_existing("country_codes", sections),
        "origin_country": _first_existing("origin_country", sections),
        "original_language": _first_existing("original_language", sections),
        "genres": _genres(movie) or _first_existing("genres", sections),
        "genre_keys": _first_existing("genre_keys", sections),
        "genres_tmdb": _first_existing("genres_tmdb", sections),
        "description": _first_existing("description", sections),
        "overview": _first_existing("overview", sections),
        "poster_path": _first_existing("poster_path", sections),
        "poster_url": _first_existing("poster_url", sections),
        "content_rating": _first_existing("content_rating", sections),
        "actors_top": _first_existing("actors_top", sections),
        "crew_top": _first_existing("crew_top", sections),
        "keywords": _first_existing("keywords", sections),
        "networks": _first_existing("networks", sections),
        "production_companies": _first_existing("production_companies", sections),
        "first_air_date": _first_existing("first_air_date", sections),
        "imdb_id": _first_existing("imdb_id", sections),
    }

    from candidates.sources.tmdb.scoring import (
        compute_metadata_completeness_score,
        compute_tmdb_final_score,
        compute_tmdb_hidden_gem_score,
        compute_tmdb_quality_score,
    )

    metadata_score = compute_metadata_completeness_score(candidate_like)
    quality_score = compute_tmdb_quality_score(candidate_like)
    hidden_gem_score = compute_tmdb_hidden_gem_score(candidate_like)
    final_score = compute_tmdb_final_score(
        {
            **candidate_like,
            "metadata_completeness_score": metadata_score,
            "quality_score": quality_score,
            "hidden_gem_score": hidden_gem_score,
        }
    )
    return {
        "metadata_completeness_score": metadata_score,
        "quality_score": quality_score,
        "hidden_gem_score": hidden_gem_score,
        "final_score": final_score,
    }


def _resolve_country(movie: dict, title: str, year, lookup_cache: dict | None = None, meta_obj=None) -> str | None:
    country = _country(movie)
    if country is not None:
        return country

    resolved_meta = _meta_obj_for_title(title, lookup_cache, meta_obj=meta_obj)
    if isinstance(resolved_meta, dict):
        country = _country(resolved_meta)
        if country is not None:
            return country

    pool_candidate = _pool_candidate_for_title(title, year, lookup_cache)
    if isinstance(pool_candidate, dict):
        country = _country(pool_candidate)
        if country is not None:
            return country

    return None


def _genres_from_flags(movie: dict) -> list[str]:
    genre_section = _as_dict(movie.get(constant.GENRE_SECTION))
    result = []

    for feature in constant.GENRE:
        if genre_section.get(feature) != 1:
            continue
        label = _clean_text(constant.FIELD_LABELS.get(feature))
        if label is None:
            label = feature.removeprefix("has_").replace("_", " ").title()
        if label not in result:
            result.append(label)

    return result


def _genres(movie: dict) -> list[str]:
    for field_name in ("genres_display", "genre_display"):
        values = _list_text_values(movie.get(field_name))
        if len(values) > 0:
            return values

    for field_name in ("genres", "imdb_genres", "genres_tmdb", "tmdb_genres"):
        values = _list_text_values(movie.get(field_name))
        if len(values) > 0:
            return values

    return _genres_from_flags(movie)


def _meta_obj_for_title(title: str, lookup_cache: dict | None, meta_obj=None) -> dict | None:
    if isinstance(meta_obj, dict):
        return meta_obj
    if lookup_cache is None:
        return None
    return lookup_cache["meta_by_title"].get(title.strip().casefold())


def resolve_watched_description(title: str, year, meta_obj: dict | None, pool_by_identity: dict) -> str:
    """Resolve watched-title description from meta and candidate pool."""
    if isinstance(meta_obj, dict):
        meta_text = _clean_text(meta_obj.get("description"))
        if meta_text is not None:
            return meta_text

    pool_candidate = pool_by_identity.get(title_identity_key({"title": title, "year": year}))
    if isinstance(pool_candidate, dict):
        from candidates.views.formatters import format_candidate_description

        pool_text = format_candidate_description(pool_candidate)
        if pool_text and pool_text != "нет данных":
            return pool_text

    return ""


def _resolve_overview(
    movie: dict,
    title: str,
    year,
    lookup_cache: dict | None = None,
    meta_obj=None,
) -> str | None:
    direct = _first_text(
        movie,
        "overview",
        "description",
        "short_description",
        "shortDescription",
        "plot",
    )
    if direct is not None:
        return direct

    resolved_meta = _meta_obj_for_title(title, lookup_cache, meta_obj=meta_obj)
    pool_by_identity = lookup_cache["pool_by_identity"] if lookup_cache else {}
    resolved_text = resolve_watched_description(title, year, resolved_meta, pool_by_identity)
    return resolved_text or None


def build_watched_movie_card(
    movie,
    poster_cache=None,
    lookup_cache=None,
    meta_obj=None,
) -> dict:
    """Build one compact read-only card from a dataset record."""
    movie = _as_dict(movie)
    main_info = _as_dict(movie.get("main_info"))
    raw_scores = _as_dict(movie.get("raw_scores"))
    title = _clean_text(main_info.get("title")) or _clean_text(movie.get("title")) or ""
    year = _to_int(main_info.get("year", movie.get("year")))
    poster_fields = _resolve_poster_fields(movie, poster_cache=poster_cache)
    resolved_meta = _meta_obj_for_title(title, lookup_cache, meta_obj=meta_obj)
    pool_candidate = _pool_candidate_for_title(title, year, lookup_cache)
    tmdb_sections = _tmdb_score_sections(movie, raw_scores, resolved_meta, pool_candidate)
    country = _resolve_country(movie, title, year, lookup_cache=lookup_cache, meta_obj=resolved_meta)
    computed_tmdb_scores = _compute_watched_tmdb_scores(movie, tmdb_sections, country)
    quality_score = _first_number("quality_score", tmdb_sections, _to_float)
    final_score = _first_number("final_score", tmdb_sections, _to_float)

    return {
        "title": title,
        "year": year,
        "user_score": _to_float(main_info.get("user_score", movie.get("user_score"))),
        "tmdb_score": _first_number("tmdb_score", tmdb_sections, _to_float),
        "tmdb_votes": _first_number("tmdb_votes", tmdb_sections, _to_int),
        "tmdb_popularity": _first_number("tmdb_popularity", tmdb_sections, _to_float),
        "quality_score": quality_score if quality_score is not None else computed_tmdb_scores.get("quality_score"),
        "final_score": final_score if final_score is not None else computed_tmdb_scores.get("final_score"),
        "genres": _genres(movie),
        "country": country,
        "object_type": _object_type(movie, default="series"),
        "overview": _resolve_overview(movie, title, year, lookup_cache=lookup_cache, meta_obj=meta_obj),
        "poster_url": poster_fields["poster_url"],
        "poster_path": poster_fields["poster_path"],
        "poster_src": poster_fields["poster_src"],
        "poster_source": poster_fields["poster_source"],
        "runtime_status": "watched",
    }

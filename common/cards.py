"""Compact read-only card dicts built from dataset records."""

from __future__ import annotations

from pathlib import Path

from candidates.models import genre_schema
from candidates.models import country_schema
from candidates.models.keys import title_identity_key
from config import constant
from dataset.language import (
    choose_display_overview,
    choose_display_title,
    choose_genre_labels,
    normalize_data_language,
)
from dataset.models.media_type import normalize_media_type
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


def _localized_poster_value(movie: dict, data_language: str, *field_names: str) -> str | None:
    localized = _as_dict(movie.get("localized"))
    block = _as_dict(localized.get(normalize_data_language(data_language)))
    for field_name in field_names:
        text = _clean_text(block.get(field_name))
        if text is not None:
            return text
    return None


def _poster_url(movie: dict, data_language: str = "ru") -> str | None:
    localized = _localized_poster_value(
        movie,
        data_language,
        "poster_url",
        "posterUrl",
        "preview_url",
        "previewUrl",
    )
    if localized is not None:
        return localized
    poster = _as_dict(movie.get("poster"))
    return _first_text(movie, "poster_url", "posterUrl", "preview_url", "previewUrl") or _clean_text(
        poster.get("url") or poster.get("previewUrl")
    )


def _poster_path(movie: dict, data_language: str = "ru") -> str | None:
    localized = _localized_poster_value(movie, data_language, "poster_path", "posterPath")
    if localized is not None:
        return localized
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


def _resolve_poster_fields(
    movie: dict,
    poster_cache: dict | None = None,
    data_language: str = "ru",
) -> dict:
    poster_url = _poster_url(movie, data_language=data_language)
    poster_path = _poster_path(movie, data_language=data_language)
    poster_source = "existing_field" if poster_url or poster_path else None

    main_info = _as_dict(movie.get("main_info"))
    title = _clean_text(main_info.get("title")) or _clean_text(movie.get("title")) or ""
    year = _to_int(main_info.get("year", movie.get("year")))
    cache_entry = lookup_poster_cache_entry(title, year, cache=poster_cache)
    cache_poster_url = _clean_text(cache_entry.get("poster_url")) if cache_entry else None

    if cache_entry and cache_entry.get("status") == "found":
        if poster_url is None:
            poster_url = _clean_text(cache_entry.get("poster_url"))
        if poster_path is None:
            poster_path = _clean_text(cache_entry.get("poster_path"))
        if poster_source is None:
            poster_source = _clean_text(cache_entry.get("source")) or "poster_cache"

    local_path = _local_poster_path(poster_path)
    cache_matches_requested_url = poster_url is None or cache_poster_url in (None, poster_url)
    if local_path is None and cache_entry and cache_matches_requested_url:
        local_path = _local_poster_path(cache_entry.get("local_path"))
    if local_path is None and title and cache_matches_requested_url:
        from posters.cache import default_local_poster_path

        local_path = default_local_poster_path(title, year)

    poster_src = local_path or poster_url or poster_path
    return {
        "poster_url": poster_url,
        "poster_path": poster_path,
        "poster_src": poster_src,
        "poster_source": poster_source,
    }


def _country(movie: dict, data_language: str = "ru") -> str | None:
    language = normalize_data_language(data_language)
    display = _first_text(movie, "country_display")
    if display is not None:
        codes = country_schema.normalize_country_filter_list(display)
        return country_schema.build_country_display(codes, language=language) or display

    for field_name in (
        "country_codes",
        "origin_country",
        "tmdb_country_codes",
        "tmdb_origin_countries",
    ):
        codes = country_schema.normalize_country_filter_list(movie.get(field_name))
        display = country_schema.build_country_display(codes, language=language)
        if display is not None:
            return display

    for field_name in ("countries", "production_countries", "tmdb_production_countries"):
        values = _list_text_values(movie.get(field_name))
        if len(values) > 0:
            display = country_schema.build_country_display(
                country_schema.normalize_country_filter_list(values),
                language=language,
            )
            return display or ", ".join(values)

    country = _first_text(movie, "country")
    if country is None:
        return None
    display = country_schema.build_country_display(
        country_schema.normalize_country_filter_list(country),
        language=language,
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


def _localized_title_only(record: dict | None, data_language: str) -> str | None:
    source = _as_dict(record)
    language = normalize_data_language(data_language)
    localized = _as_dict(source.get("localized"))
    language_block = _as_dict(localized.get(language))
    title = _clean_text(language_block.get("title"))
    if title is not None:
        return title
    if language == "en":
        return _first_text(
            source,
            "title_en",
            "name_en",
            "enName",
            "alternative_title",
            "alternativeName",
        )
    return _first_text(source, "main_info.title", "title", "name")


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


def _compute_watched_tmdb_scores(
    movie: dict,
    sections: list[dict],
    country: str | None,
    data_language: str,
) -> dict:
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
        "genres": _genres(movie, data_language=data_language) or _first_existing("genres", sections),
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


def _resolve_country(
    movie: dict,
    title: str,
    year,
    lookup_cache: dict | None = None,
    meta_obj=None,
    data_language: str = "ru",
) -> str | None:
    country = _country(movie, data_language=data_language)
    if country is not None:
        return country

    resolved_meta = _meta_obj_for_title(title, lookup_cache, meta_obj=meta_obj)
    if isinstance(resolved_meta, dict):
        country = _country(resolved_meta, data_language=data_language)
        if country is not None:
            return country

    pool_candidate = _pool_candidate_for_title(title, year, lookup_cache)
    if isinstance(pool_candidate, dict):
        country = _country(pool_candidate, data_language=data_language)
        if country is not None:
            return country

    return None


def _genres_from_flags(movie: dict, data_language: str) -> list[str]:
    genre_section = _as_dict(movie.get(constant.GENRE_SECTION))
    genre_keys = []

    for feature in constant.GENRE:
        if genre_section.get(feature) != 1:
            continue
        genre_keys.append(feature)

    if len(genre_keys) > 0:
        return choose_genre_labels(genre_keys, data_language)
    return []


def _genres(movie: dict, data_language: str = "ru") -> list[str]:
    genre_keys = _as_list(movie.get("genre_keys"))
    if len(genre_keys) > 0:
        return choose_genre_labels(genre_keys, data_language)

    for field_name in ("genres_display", "genre_display"):
        values = _list_text_values(movie.get(field_name))
        if len(values) > 0:
            if normalize_data_language(data_language) == "en":
                keys = genre_schema.normalize_genre_filter_list(values)
                localized = choose_genre_labels(keys, data_language)
                if len(localized) > 0:
                    return localized
            return genre_schema.normalize_genre_display_labels(values)

    for field_name in ("genres", "imdb_genres", "genres_tmdb", "tmdb_genres"):
        values = _list_text_values(movie.get(field_name))
        if len(values) > 0:
            keys = genre_schema.normalize_genre_filter_list(values)
            if len(keys) > 0:
                return choose_genre_labels(keys, data_language)
            return genre_schema.normalize_genre_display_labels(values)

    return _genres_from_flags(movie, data_language)


def _resolve_genres(
    movie: dict,
    resolved_meta: dict | None,
    pool_candidate: dict | None,
    data_language: str,
) -> list[str]:
    for source in (movie, resolved_meta, pool_candidate):
        if isinstance(source, dict) is False:
            continue
        genres = _genres(source, data_language=data_language)
        if len(genres) > 0:
            return genres
    return []


def _meta_obj_for_title(title: str, lookup_cache: dict | None, meta_obj=None) -> dict | None:
    if isinstance(meta_obj, dict):
        return meta_obj
    if lookup_cache is None:
        return None
    return lookup_cache["meta_by_title"].get(title.strip().casefold())


def resolve_watched_description(
    title: str,
    year,
    meta_obj: dict | None,
    pool_by_identity: dict,
    *,
    data_language: str = "ru",
) -> str:
    """Resolve watched-title description from meta and candidate pool."""
    if isinstance(meta_obj, dict):
        meta_text = choose_display_overview(meta_obj, data_language) or _clean_text(meta_obj.get("description"))
        if meta_text is not None:
            return meta_text

    pool_candidate = pool_by_identity.get(title_identity_key({"title": title, "year": year}))
    if isinstance(pool_candidate, dict):
        from candidates.views.formatters import format_candidate_description

        pool_text = format_candidate_description(pool_candidate, data_language=data_language)
        if pool_text and pool_text != "нет данных":
            return pool_text

    return ""


def _resolve_overview(
    movie: dict,
    title: str,
    year,
    lookup_cache: dict | None = None,
    meta_obj=None,
    data_language: str = "ru",
) -> str | None:
    direct = choose_display_overview(movie, data_language)
    if direct is not None:
        return direct

    resolved_meta = _meta_obj_for_title(title, lookup_cache, meta_obj=meta_obj)
    pool_by_identity = lookup_cache["pool_by_identity"] if lookup_cache else {}
    resolved_text = resolve_watched_description(
        title,
        year,
        resolved_meta,
        pool_by_identity,
        data_language=data_language,
    )
    return resolved_text or None


def build_watched_movie_card(
    movie,
    poster_cache=None,
    lookup_cache=None,
    meta_obj=None,
    data_language: str = "ru",
) -> dict:
    """Build one compact read-only card from a dataset record."""
    language = normalize_data_language(data_language)
    movie = _as_dict(movie)
    main_info = _as_dict(movie.get("main_info"))
    raw_scores = _as_dict(movie.get("raw_scores"))
    legacy_title = _clean_text(main_info.get("title")) or _clean_text(movie.get("title")) or ""
    year = _to_int(main_info.get("year", movie.get("year")))
    poster_fields = _resolve_poster_fields(movie, poster_cache=poster_cache, data_language=language)
    resolved_meta = _meta_obj_for_title(legacy_title, lookup_cache, meta_obj=meta_obj)
    pool_candidate = _pool_candidate_for_title(legacy_title, year, lookup_cache)
    title = (
        _localized_title_only(movie, language)
        or _localized_title_only(resolved_meta, language)
        or _localized_title_only(pool_candidate, language)
        or choose_display_title(movie, language)
        or choose_display_title(resolved_meta, language)
        or choose_display_title(pool_candidate, language)
        or legacy_title
    )
    tmdb_sections = _tmdb_score_sections(movie, raw_scores, resolved_meta, pool_candidate)
    country = _resolve_country(
        movie,
        legacy_title,
        year,
        lookup_cache=lookup_cache,
        meta_obj=resolved_meta,
        data_language=language,
    )
    computed_tmdb_scores = _compute_watched_tmdb_scores(movie, tmdb_sections, country, language)
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
        "genres": _resolve_genres(movie, resolved_meta, pool_candidate, language),
        "country": country,
        "media_type": normalize_media_type(main_info.get("media_type") or movie.get("media_type")),
        "object_type": _object_type(movie, default="series"),
        "overview": _resolve_overview(
            movie,
            legacy_title,
            year,
            lookup_cache=lookup_cache,
            meta_obj=resolved_meta,
            data_language=language,
        ),
        "poster_url": poster_fields["poster_url"],
        "poster_path": poster_fields["poster_path"],
        "poster_src": poster_fields["poster_src"],
        "poster_source": poster_fields["poster_source"],
        "number_of_seasons": _first_number("number_of_seasons", tmdb_sections, _to_int),
        "number_of_episodes": _first_number("number_of_episodes", tmdb_sections, _to_int),
        "episode_run_time": _first_existing("episode_run_time", tmdb_sections),
        "first_air_date": _first_existing("first_air_date", tmdb_sections),
        "last_air_date": _first_existing("last_air_date", tmdb_sections),
        "last_episode_to_air": _first_existing("last_episode_to_air", tmdb_sections),
        "watch_providers": _first_existing("watch_providers", tmdb_sections)
        or _first_existing("watch_providers_ru", tmdb_sections),
        "status": _first_existing("status", tmdb_sections),
        "in_production": _first_existing("in_production", tmdb_sections),
        "runtime_status": "watched",
    }

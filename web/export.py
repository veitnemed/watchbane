"""Read-only web exports built from already loaded project data."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from config import constant
from model import model
from posters.cache import lookup_poster_cache_entry


DEFAULT_WATCHED_MOVIES_JSON = Path("web") / "data" / "watched_movies.json"


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
        return display

    for field_name in ("countries", "production_countries", "tmdb_production_countries"):
        values = _list_text_values(movie.get(field_name))
        if len(values) > 0:
            return ", ".join(values)

    return _first_text(movie, "country")


def _genres_from_flags(movie: dict) -> list[str]:
    genre_section = _as_dict(movie.get(constant.GENRE_SECTION))
    labels = constant.FIELD_LABELS
    result = []

    for feature in constant.GENRE:
        if genre_section.get(feature) != 1:
            continue
        label = _clean_text(labels.get(feature))
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


def build_export_lookup_cache(meta=None, pool_by_identity=None) -> dict:
    """Builds one lookup map for meta and candidate pool descriptions."""
    if meta is None:
        from storage.data import load_meta

        meta = load_meta()

    meta_by_title = {}
    for meta_title, meta_obj in meta.items():
        if isinstance(meta_obj, dict):
            meta_by_title[meta_title.strip().casefold()] = meta_obj

    if pool_by_identity is None:
        pool_by_identity = {}
        try:
            from candidates import candidate_pool
            from candidates import keys as candidate_keys

            for candidate in candidate_pool.load_candidate_pool().values():
                if isinstance(candidate, dict) is False:
                    continue
                identity = candidate_keys.title_identity_key(candidate)
                pool_by_identity.setdefault(identity, candidate)
        except Exception:
            pass

    return {
        "meta_by_title": meta_by_title,
        "pool_by_identity": pool_by_identity,
    }


def _meta_obj_for_title(title: str, lookup_cache: dict | None, meta_obj=None) -> dict | None:
    if isinstance(meta_obj, dict):
        return meta_obj
    if lookup_cache is None:
        return None
    return lookup_cache["meta_by_title"].get(title.strip().casefold())


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
    if isinstance(resolved_meta, dict):
        meta_text = _clean_text(resolved_meta.get("description"))
        if meta_text is not None:
            return meta_text

    from model.train_report import resolve_movie_description

    pool_by_identity = lookup_cache["pool_by_identity"] if lookup_cache else {}
    resolved_text = resolve_movie_description(title, year, resolved_meta, pool_by_identity)
    if resolved_text == "нет описания":
        return None
    return resolved_text


def build_watched_movie_card(
    movie,
    poster_cache=None,
    lookup_cache=None,
    meta_obj=None,
) -> dict:
    """Builds one compact read-only card from a dataset record."""
    movie = _as_dict(movie)
    main_info = _as_dict(movie.get("main_info"))
    raw_scores = _as_dict(movie.get("raw_scores"))
    title = _clean_text(main_info.get("title")) or _clean_text(movie.get("title")) or ""
    year = _to_int(main_info.get("year", movie.get("year")))
    poster_fields = _resolve_poster_fields(movie, poster_cache=poster_cache)

    return {
        "title": title,
        "year": year,
        "user_score": _to_float(main_info.get("user_score", movie.get("user_score"))),
        "kp_score": _to_float(raw_scores.get("kp_score", movie.get("kp_score"))),
        "imdb_score": _to_float(raw_scores.get("imdb_score", movie.get("imdb_score"))),
        "kp_votes": _to_int(raw_scores.get("kp_votes", movie.get("kp_votes"))),
        "imdb_votes": _to_int(raw_scores.get("imdb_votes", movie.get("imdb_votes"))),
        "genres": _genres(movie),
        "country": _country(movie),
        "overview": _resolve_overview(movie, title, year, lookup_cache=lookup_cache, meta_obj=meta_obj),
        "poster_url": poster_fields["poster_url"],
        "poster_path": poster_fields["poster_path"],
        "poster_src": poster_fields["poster_src"],
        "poster_source": poster_fields["poster_source"],
        "runtime_status": "watched",
    }


def export_watched_movies_json(data, path=None) -> Path:
    """Exports watched dataset records to a JSON payload for a future JS GUI."""
    output_path = DEFAULT_WATCHED_MOVIES_JSON if path is None else Path(path)
    poster_cache = None
    try:
        from posters.cache import load_poster_cache

        poster_cache = load_poster_cache()
    except Exception:
        poster_cache = {}
    lookup_cache = build_export_lookup_cache()
    items = [
        build_watched_movie_card(
            movie_obj,
            poster_cache=poster_cache,
            lookup_cache=lookup_cache,
        )
        for movie_obj in model.iter_movies(data)
    ]
    payload = {
        "report_type": "watched_movies",
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "count": len(items),
        "items": items,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
    return output_path

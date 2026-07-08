"""Read-only poster cache helpers for watched titles."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from candidates.models.keys import title_identity_key
from config import constant
from storage.data import get_meta_obj

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_POSTER_CACHE_DIR = Path(constant.CACHE_DIR) / "posters"
DEFAULT_POSTER_CACHE_JSON = DEFAULT_POSTER_CACHE_DIR / "posters.json"
DEFAULT_POSTER_IMAGES_DIR = DEFAULT_POSTER_CACHE_DIR / "images"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p"

POSTER_URL_FIELDS = (
    "poster_url",
    "posterUrl",
    "preview_url",
    "previewUrl",
    "tmdb_poster_url",
    "kp_poster_url",
    "cover_url",
    "image_url",
)
POSTER_PATH_FIELDS = (
    "poster_path",
    "posterPath",
    "tmdb_poster_path",
)
POSTER_NESTED_URL_FIELDS = ("url", "previewUrl", "preview_url")
POSTER_NESTED_PATH_FIELDS = ("path", "poster_path", "posterPath")
SEARCH_SECTIONS = (
    None,
    "main_info",
    "raw_scores",
    "computed_scores",
    "source_values",
    "meta",
    "tmdb_data",
    "api",
    "kp",
    "metadata",
    "poster",
)


def poster_identity_key(title: str, year: Any) -> str:
    """Build stable cache key from title and year."""
    return title_identity_key({"title": title, "year": year})


def load_poster_cache(path: str | Path | None = None) -> dict:
    """Load poster cache JSON or return empty dict when file is missing."""
    cache_path = DEFAULT_POSTER_CACHE_JSON if path is None else Path(path)
    if cache_path.is_file() is False:
        return {}

    try:
        with open(cache_path, "r", encoding="utf-8-sig") as file:
            payload = json.load(file)
    except (OSError, json.JSONDecodeError):
        return {}

    return payload if isinstance(payload, dict) else {}


def save_poster_cache(cache: dict, path: str | Path | None = None) -> Path:
    """Save poster cache JSON in UTF-8."""
    cache_path = DEFAULT_POSTER_CACHE_JSON if path is None else Path(path)
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    with open(cache_path, "w", encoding="utf-8") as file:
        json.dump(cache, file, ensure_ascii=False, indent=2)

    return cache_path


def build_tmdb_poster_url(poster_path: str | None, size: str = "w342") -> str | None:
    """Build TMDb image URL from poster_path without network calls."""
    if poster_path is None:
        return None

    text = str(poster_path).strip()
    if text == "":
        return None
    if text.startswith(("http://", "https://")):
        return text
    if text.startswith("/") is False:
        text = f"/{text}"
    return f"{TMDB_IMAGE_BASE}/{size}{text}"


def _as_dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if text != "" else None


def _section(movie: dict, section_name: str | None) -> dict:
    if section_name is None:
        return _as_dict(movie)
    return _as_dict(movie.get(section_name))


def _first_in_section(section: dict, field_names: tuple[str, ...]) -> tuple[str | None, str | None]:
    for field_name in field_names:
        text = _clean_text(section.get(field_name))
        if text is not None:
            return text, field_name
    return None, None


def _normalize_data_language(value: Any) -> str:
    text = str(value or "").strip().casefold()
    return text if text in {"ru", "en"} else "ru"


def _localized_poster_info(movie: dict, data_language: str | None) -> dict | None:
    if data_language in (None, ""):
        return None
    localized = _as_dict(movie.get("localized"))
    section = _as_dict(localized.get(_normalize_data_language(data_language)))
    if len(section) == 0:
        return None

    poster_url, url_field = _first_in_section(section, POSTER_URL_FIELDS)
    if poster_url is not None:
        poster_path, _path_field = _first_in_section(section, POSTER_PATH_FIELDS)
        return {
            "poster_path": poster_path,
            "poster_url": poster_url,
            "source": f"localized.{_normalize_data_language(data_language)}.{url_field}",
            "status": "found",
        }

    poster_path, path_field = _first_in_section(section, POSTER_PATH_FIELDS)
    if poster_path is not None:
        return {
            "poster_path": poster_path,
            "poster_url": build_tmdb_poster_url(poster_path),
            "source": f"localized.{_normalize_data_language(data_language)}.{path_field}",
            "status": "found",
        }
    return None


def _poster_search_context(movie: dict, meta_obj: dict | None = None) -> dict:
    """Build read-only search context from movie and optional meta."""
    context = dict(movie)
    if isinstance(meta_obj, dict) is False:
        return context

    if "meta" not in context:
        context["meta"] = meta_obj
    for key in ("tmdb_data", "api", "kp", "metadata", "poster"):
        if key in meta_obj and key not in context:
            context[key] = meta_obj[key]
    return context


def extract_existing_poster_info(movie: dict, *, data_language: str | None = None) -> dict:
    """Extract poster metadata already present in one movie/meta context."""
    search_movie = _as_dict(movie)
    localized_poster = _localized_poster_info(search_movie, data_language)
    if localized_poster is not None:
        return localized_poster

    for section_name in SEARCH_SECTIONS:
        section = _section(search_movie, section_name)
        if len(section) == 0:
            continue
        localized_section_poster = _localized_poster_info(section, data_language)
        if localized_section_poster is not None:
            return localized_section_poster

        poster_url, url_field = _first_in_section(section, POSTER_URL_FIELDS)
        if poster_url is not None:
            source = f"{section_name}.{url_field}" if section_name else url_field
            return {
                "poster_path": None,
                "poster_url": poster_url,
                "source": source,
                "status": "found",
            }

        poster_path, path_field = _first_in_section(section, POSTER_PATH_FIELDS)
        if poster_path is not None:
            source = f"{section_name}.{path_field}" if section_name else path_field
            return {
                "poster_path": poster_path,
                "poster_url": build_tmdb_poster_url(poster_path),
                "source": source,
                "status": "found",
            }

        nested_poster = _as_dict(section.get("poster"))
        if len(nested_poster) == 0:
            continue

        nested_url, nested_url_field = _first_in_section(nested_poster, POSTER_NESTED_URL_FIELDS)
        if nested_url is not None:
            prefix = section_name or "root"
            return {
                "poster_path": None,
                "poster_url": nested_url,
                "source": f"{prefix}.poster.{nested_url_field}",
                "status": "found",
            }

        nested_path, nested_path_field = _first_in_section(nested_poster, POSTER_NESTED_PATH_FIELDS)
        if nested_path is not None:
            prefix = section_name or "root"
            return {
                "poster_path": nested_path,
                "poster_url": build_tmdb_poster_url(nested_path),
                "source": f"{prefix}.poster.{nested_path_field}",
                "status": "found",
            }

        cover = _clean_text(section.get("cover"))
        if cover is not None and cover.startswith(("http://", "https://")):
            prefix = section_name or "root"
            return {
                "poster_path": None,
                "poster_url": cover,
                "source": f"{prefix}.cover",
                "status": "found",
            }

        image = _clean_text(section.get("image"))
        if image is not None and image.startswith(("http://", "https://")):
            prefix = section_name or "root"
            return {
                "poster_path": None,
                "poster_url": image,
                "source": f"{prefix}.image",
                "status": "found",
            }

    return {
        "poster_path": None,
        "poster_url": None,
        "source": None,
        "status": "missing",
    }


def _movie_title_year(dataset_key: str, movie: dict) -> tuple[str, Any]:
    main_info = _as_dict(movie.get("main_info"))
    title = _clean_text(main_info.get("title")) or _clean_text(movie.get("title")) or dataset_key
    year = main_info.get("year", movie.get("year"))
    return title, year


def _iter_dataset_items(data) -> list[tuple[str, dict]]:
    if isinstance(data, dict):
        return list(data.items())
    return [(str(index), movie) for index, movie in enumerate(data or [])]


def default_local_poster_path(title: str, year: Any) -> str | None:
    """Return watched poster image path when the default cache file already exists."""
    from posters.download_images import poster_image_path_for_identity

    path = poster_image_path_for_identity(poster_identity_key(title, year))
    return str(path) if path.is_file() else None


def build_poster_cache_from_existing_data(data) -> dict:
    """Build poster cache entries from existing dataset records without API calls."""
    cache: dict[str, dict] = {}
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    for dataset_key, movie in _iter_dataset_items(data):
        movie_dict = _as_dict(movie)
        original = deepcopy(movie_dict)
        title, year = _movie_title_year(dataset_key, movie_dict)
        meta_obj = get_meta_obj(title)
        search_context = _poster_search_context(movie_dict, meta_obj)
        poster_info = extract_existing_poster_info(search_context)

        if movie_dict != original:
            raise RuntimeError("poster cache builder mutated source movie")

        identity = poster_identity_key(title, year)
        local_path = default_local_poster_path(title, year)
        status = poster_info.get("status")
        if local_path is not None and status != "found":
            status = "found"

        cache[identity] = {
            "title": title,
            "year": year,
            "source": poster_info.get("source"),
            "poster_path": poster_info.get("poster_path"),
            "poster_url": poster_info.get("poster_url"),
            "local_path": local_path,
            "status": status,
            "updated_at": now,
        }

    return cache


def rehydrate_poster_cache_from_dataset(*, persist: bool = True) -> dict:
    """Rebuild poster-cache JSON from dataset/meta and existing local image files."""
    from storage.data import load_dataset

    cache = build_poster_cache_from_existing_data(load_dataset())
    linked = sum(1 for entry in cache.values() if entry.get("local_path"))
    if persist:
        save_poster_cache(cache)
    return {
        "entries": len(cache),
        "linked": linked,
        "missing": len(cache) - linked,
    }


def lookup_poster_cache_entry(title: str, year: Any, cache: dict | None = None) -> dict | None:
    """Return one cache entry by title/year identity."""
    poster_cache = load_poster_cache() if cache is None else cache
    entry = poster_cache.get(poster_identity_key(title, year))
    return entry if isinstance(entry, dict) else None


def _build_cache_entry(title: str, year: Any, poster_info: dict) -> dict:
    return {
        "title": title,
        "year": year,
        "source": poster_info.get("source"),
        "poster_path": poster_info.get("poster_path"),
        "poster_url": poster_info.get("poster_url"),
        "local_path": poster_info.get("local_path"),
        "status": poster_info.get("status", "missing"),
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def upsert_poster_cache_entry(
    title: str,
    year: Any,
    poster_info: dict,
    cache: dict | None = None,
    *,
    persist: bool = True,
) -> dict:
    """Insert or update one poster-cache entry."""
    if cache is None:
        poster_cache = load_poster_cache()
    else:
        poster_cache = cache

    identity = poster_identity_key(title, year)
    current = poster_cache.get(identity)
    current_url = _clean_text(current.get("poster_url")) if isinstance(current, dict) else None
    next_url = _clean_text(poster_info.get("poster_url"))
    if (
        isinstance(current, dict)
        and current.get("local_path")
        and (next_url is None or current_url == next_url)
    ):
        poster_info = dict(poster_info)
        poster_info["local_path"] = current.get("local_path")
    elif isinstance(current, dict) and current.get("local_path") and current_url != next_url:
        poster_info = dict(poster_info)
        poster_info["local_path"] = current.get("local_path")
    poster_cache[identity] = _build_cache_entry(title, year, poster_info)
    if persist:
        save_poster_cache(poster_cache)
    return poster_cache[identity]


def upsert_poster_cache_batch(cache: dict, *, persist: bool = True) -> Path | None:
    """Persist a poster-cache dict built in memory."""
    if persist is False:
        return None
    return save_poster_cache(cache)


def _merge_poster_info(*poster_infos: dict) -> dict:
    for poster_info in poster_infos:
        if isinstance(poster_info, dict) and poster_info.get("status") == "found":
            return poster_info
    for poster_info in poster_infos:
        if isinstance(poster_info, dict):
            return poster_info
    return {
        "poster_path": None,
        "poster_url": None,
        "source": None,
        "status": "missing",
    }


def sync_poster_cache_from_meta_and_sources(
    title: str,
    year: Any,
    meta_obj: dict | None = None,
    movie: dict | None = None,
    extra_sources: dict | None = None,
    cache: dict | None = None,
    *,
    persist: bool = True,
    data_language: str | None = None,
) -> dict:
    """Sync one watched poster-cache entry from movie/meta/extra sources."""
    search_context = _poster_search_context(_as_dict(movie), meta_obj)
    poster_infos = [extract_existing_poster_info(search_context, data_language=data_language)]
    if isinstance(extra_sources, dict):
        poster_infos.append(extract_existing_poster_info(extra_sources, data_language=data_language))
    poster_info = _merge_poster_info(*poster_infos)
    return upsert_poster_cache_entry(title, year, poster_info, cache=cache, persist=persist)

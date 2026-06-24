"""Read-only poster cache helpers for watched titles."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from candidates.keys import title_identity_key
from model import model
from storage.data import get_meta_obj

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_POSTER_CACHE_DIR = ROOT_DIR / "data" / "cache" / "posters"
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


def extract_existing_poster_info(movie: dict) -> dict:
    """Extract poster metadata already present in one movie/meta context."""
    search_movie = _as_dict(movie)

    for section_name in SEARCH_SECTIONS:
        section = _section(search_movie, section_name)
        if len(section) == 0:
            continue

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


def build_poster_cache_from_existing_data(data) -> dict:
    """Build poster cache entries from existing dataset records without API calls."""
    cache: dict[str, dict] = {}
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    if isinstance(data, dict):
        items = list(data.items())
    else:
        items = [(str(index), movie) for index, movie in enumerate(model.iter_movies(data))]

    for dataset_key, movie in items:
        movie_dict = _as_dict(movie)
        original = deepcopy(movie_dict)
        title, year = _movie_title_year(dataset_key, movie_dict)
        meta_obj = get_meta_obj(title)
        search_context = _poster_search_context(movie_dict, meta_obj)
        poster_info = extract_existing_poster_info(search_context)

        if movie_dict != original:
            raise RuntimeError("poster cache builder mutated source movie")

        cache[poster_identity_key(title, year)] = {
            "title": title,
            "year": year,
            "source": poster_info.get("source"),
            "poster_path": poster_info.get("poster_path"),
            "poster_url": poster_info.get("poster_url"),
            "local_path": None,
            "status": poster_info.get("status"),
            "updated_at": now,
        }

    return cache


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
    if isinstance(current, dict) and current.get("local_path"):
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
) -> dict:
    """Sync one watched poster-cache entry from movie/meta/extra sources."""
    search_context = _poster_search_context(_as_dict(movie), meta_obj)
    poster_infos = [extract_existing_poster_info(search_context)]
    if isinstance(extra_sources, dict):
        poster_infos.append(extract_existing_poster_info(extra_sources))
    poster_info = _merge_poster_info(*poster_infos)
    return upsert_poster_cache_entry(title, year, poster_info, cache=cache, persist=persist)

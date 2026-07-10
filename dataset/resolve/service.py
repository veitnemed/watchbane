"""TMDb-only add-flow resolve orchestration."""

from __future__ import annotations

from typing import Any

from apis import tmdb_api as api_tmdb
from config import scheme
from dataset.language import build_localized_block_from_legacy, normalize_data_language, tmdb_locale_for_data_language
from dataset.models.media_type import normalize_media_type
from dataset.resolve.countries import extract_country_value
from dataset.resolve.defaults import build_empty_add_defaults
from dataset.resolve.genres import extract_tmdb_genres
from dataset.resolve.sources import search_tmdb_defaults_data
from dataset.tmdb_localized import localized_blocks_from_tmdb_details

ADD_TITLE_RESOLVE_PROGRESS_TOTAL = 4

_EXTERNAL_RATING_FIELDS = {
    "kp_id",
    "kp_score",
    "kp_votes",
    "kp_rating",
    "kp_status",
    "imdb_score",
    "imdb_rating",
    "imdb_votes",
    "imdb_title_type",
    "imdb_is_adult",
    "imdb_start_year",
    "imdb_end_year",
    "imdb_runtime_minutes",
    "imdb_genres",
}


def print_progress_step(source: str, status: str) -> None:
    """Compatibility no-op: callers should pass ``on_progress`` to receive progress."""
    del source, status


def _normalize_text(value) -> str:
    return str(value or "").strip()


def _report_add_progress(
    on_progress,
    step: int,
    source: str,
    status: str,
) -> None:
    message = f"{source}: {status}"
    if on_progress is not None:
        on_progress(step, ADD_TITLE_RESOLVE_PROGRESS_TOTAL, message)


def _tmdb_error(error: str, details: str) -> dict[str, Any]:
    return {"ok": False, "error": error, "details": details}


def _clean_tmdb_data(data: dict[str, Any]) -> dict[str, Any]:
    cleaned = {
        key: value
        for key, value in dict(data or {}).items()
        if key not in _EXTERNAL_RATING_FIELDS and value not in (None, "")
    }
    if "tmdb_score" not in cleaned and data.get("tmdb_rating") not in (None, ""):
        cleaned["tmdb_score"] = data.get("tmdb_rating")
    cleaned.pop("tmdb_rating", None)
    cleaned["source"] = "tmdb_api"
    cleaned["media_type"] = normalize_media_type(data.get("media_type"))
    return cleaned


def _build_tmdb_add_defaults(
    input_title: str,
    country: str,
    tmdb_data: dict[str, Any],
    *,
    data_language: str = "ru",
) -> dict:
    media_type = normalize_media_type(tmdb_data.get("media_type"))
    defaults = build_empty_add_defaults(input_title, media_type=media_type)
    genres = extract_tmdb_genres(tmdb_data)
    defaults[scheme.MAIN_INFO]["title"] = tmdb_data.get("title") or input_title
    defaults[scheme.MAIN_INFO]["year"] = tmdb_data.get("year")
    defaults[scheme.MAIN_INFO]["country"] = extract_country_value(tmdb_data) or country
    defaults[scheme.MAIN_INFO]["media_type"] = media_type
    defaults[scheme.RAW_SCORES] = {
        key: tmdb_data.get(key)
        for key in ("tmdb_score", "tmdb_votes", "tmdb_popularity")
        if tmdb_data.get(key) not in (None, "")
    }
    if genres:
        defaults["genres_tmdb"] = list(genres)
    localized_source = dict(tmdb_data or {})
    tmdb_localized = localized_blocks_from_tmdb_details(
        tmdb_data,
        current_language=normalize_data_language(data_language),
    )
    if tmdb_localized:
        localized_source["localized"] = {
            **tmdb_localized,
            **dict(localized_source.get("localized") or {}),
        }
    localized_source["main_info"] = defaults[scheme.MAIN_INFO]
    localized = build_localized_block_from_legacy(
        localized_source,
        default_language=normalize_data_language(data_language),
    )
    selected_language = normalize_data_language(data_language)
    localized.setdefault(selected_language, {})
    selected_title = _normalize_text(tmdb_data.get("title"))
    selected_overview = _normalize_text(tmdb_data.get("overview") or tmdb_data.get("description"))
    if selected_title:
        localized[selected_language]["title"] = selected_title
    if selected_overview:
        localized[selected_language]["overview"] = selected_overview
    if localized:
        defaults["localized"] = localized
    return defaults


def _build_tmdb_sources(tmdb_data: dict[str, Any]) -> dict:
    return {
        "title": "tmdb_api" if tmdb_data.get("title") not in (None, "") else "input",
        "year": "tmdb_api" if tmdb_data.get("year") not in (None, "") else None,
        "country": "tmdb_api" if extract_country_value(tmdb_data) else "input",
        "tmdb_score": "tmdb_api" if tmdb_data.get("tmdb_score") not in (None, "") else None,
        "tmdb_votes": "tmdb_api" if tmdb_data.get("tmdb_votes") not in (None, "") else None,
        "tmdb_popularity": "tmdb_api" if tmdb_data.get("tmdb_popularity") not in (None, "") else None,
        "genres": "tmdb_api" if extract_tmdb_genres(tmdb_data) else None,
        "description": "tmdb_api" if tmdb_data.get("overview") not in (None, "") else None,
        "imdb_id": "tmdb_api" if tmdb_data.get("imdb_id") not in (None, "") else None,
        "media_type": "tmdb_api",
    }


def _build_tmdb_source_values(tmdb_data: dict[str, Any]) -> dict:
    return {
        "genres": extract_tmdb_genres(tmdb_data),
        "description": tmdb_data.get("overview"),
        "tmdb_score": tmdb_data.get("tmdb_score"),
        "tmdb_votes": tmdb_data.get("tmdb_votes"),
        "tmdb_popularity": tmdb_data.get("tmdb_popularity"),
        "imdb_id": tmdb_data.get("imdb_id"),
        "media_type": normalize_media_type(tmdb_data.get("media_type")),
    }


def search_tmdb_title_for_add(
    title: str,
    country: str = "",
    *,
    search_func=None,
    choose_func=None,
    details_func=None,
    normalizer=None,
    language: str | None = None,
    media_type: str = "tv",
) -> dict[str, Any]:
    """Search TMDb and return normalized add-flow data without KP/IMDb ratings."""
    result = search_tmdb_defaults_data(
        [{"title": title, "country": country}],
        search_func=search_func,
        choose_func=choose_func,
        details_func=details_func,
        normalizer=normalizer,
        language=language,
        media_type=media_type,
    )
    if result["data"] is not None:
        result["data"] = _clean_tmdb_data(result["data"])
    return result


def resolve_title_data_for_add(
    title: str,
    country: str = "Россия",
    *,
    on_progress=None,
    data_language: str = "ru",
    tmdb_language: str | None = None,
    tmdb_search_func=None,
    tmdb_choose_func=None,
    tmdb_details_func=None,
    tmdb_normalizer=None,
    media_type: str = "tv",
) -> dict:
    """Resolve add-title defaults through TMDb only."""
    title = _normalize_text(title)
    country = _normalize_text(country)
    normalized_media_type = normalize_media_type(media_type)
    normalized_data_language = normalize_data_language(data_language)
    resolved_tmdb_language = str(tmdb_language or "").strip() or tmdb_locale_for_data_language(normalized_data_language)

    _report_add_progress(on_progress, 1, "TMDb Search", "Поиск")
    tmdb_result = search_tmdb_title_for_add(
        title,
        country,
        search_func=tmdb_search_func,
        choose_func=tmdb_choose_func,
        details_func=tmdb_details_func,
        normalizer=tmdb_normalizer,
        language=resolved_tmdb_language,
        media_type=normalized_media_type,
    )
    tmdb_data = tmdb_result["data"]
    tmdb_error = tmdb_result["error"]
    tmdb_status = tmdb_result["status"]

    if tmdb_data is None:
        _report_add_progress(on_progress, 2, "TMDb Details", "Не требуется")
        _report_add_progress(on_progress, 3, "Подготовка defaults", "Ручной ввод")
        _report_add_progress(on_progress, 4, "Готово", tmdb_status)
        return {
            "title": title,
            "country": country,
            "tmdb_data": None,
            "tmdb_error": tmdb_error,
            "defaults": None,
            "sources": {},
            "source_values": {},
            "statuses": {"tmdb_api": tmdb_status},
            "data_language": normalized_data_language,
            "tmdb_language": resolved_tmdb_language,
            "media_type": normalized_media_type,
            "found": False,
        }

    _report_add_progress(on_progress, 2, "TMDb Details", "Успешно")
    _report_add_progress(on_progress, 3, "Подготовка defaults", "TMDb")
    defaults = _build_tmdb_add_defaults(
        title,
        country,
        tmdb_data,
        data_language=normalized_data_language,
    )
    sources = _build_tmdb_sources(tmdb_data)
    source_values = _build_tmdb_source_values(tmdb_data)
    _report_add_progress(on_progress, 4, "Готово", "найдено")

    return {
        "title": title,
        "country": country,
        "tmdb_data": tmdb_data,
        "tmdb_error": None,
        "defaults": defaults,
        "sources": sources,
        "source_values": source_values,
        "statuses": {"tmdb_api": tmdb_status},
        "data_language": normalized_data_language,
        "tmdb_language": resolved_tmdb_language,
        "media_type": normalized_media_type,
        "found": True,
    }


def resolve_title_data(title: str, country: str = "Россия") -> dict:
    """Compatibility name for add-flow resolve."""
    return resolve_title_data_for_add(title, country)
def resolve_title_data(title: str, country: str = "Россия", media_type: str = "tv") -> dict:
    """Compatibility name for add-flow resolve."""
    return resolve_title_data_for_add(title, country, media_type=media_type)

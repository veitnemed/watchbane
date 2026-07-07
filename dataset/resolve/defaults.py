"""TMDb-only default values for add-title flow."""

from config import constant
from config import scheme
from dataset.language import build_localized_block_from_legacy
from dataset.tmdb_localized import localized_blocks_from_tmdb_details
from dataset.resolve.countries import extract_country_value
from dataset.resolve.genres import build_genre_defaults, extract_tmdb_genres


def extract_tmdb_title(series: dict) -> str:
    """Return the best available title from a normalized TMDb object."""
    for key in ("title", "name", "original_title", "original_name"):
        value = series.get(key)
        if str(value or "").strip() != "":
            return str(value).strip()
    return ""


def extract_api_title(series: dict) -> str:
    """Compatibility alias for TMDb title extraction."""
    return extract_tmdb_title(series)


def extract_tmdb_raw_scores(series: dict) -> dict:
    """Return only TMDb score fields for watched raw_scores."""
    return {
        key: series.get(key)
        for key in ("tmdb_score", "tmdb_votes", "tmdb_popularity")
        if series.get(key) not in (None, "")
    }


def extract_api_raw_scores(series: dict) -> dict:
    """Compatibility alias for TMDb-only raw score extraction."""
    return extract_tmdb_raw_scores(series)


def extract_tmdb_description(series: dict) -> str:
    """Return the best available TMDb description text."""
    return str(series.get("description") or series.get("overview") or "").strip()


def extract_api_description(series: dict) -> str:
    """Compatibility alias for TMDb description extraction."""
    return extract_tmdb_description(series)


def build_empty_add_defaults(input_title: str) -> dict:
    """Build minimal defaults for manual add-title flow."""
    return {
        scheme.MAIN_INFO: {
            "title": input_title,
            "user_score": None,
            "year": None,
            "country": "",
        },
        scheme.RAW_SCORES: {},
        scheme.TAGS_VIBE: {feature: 0 for feature in constant.TAGS_VIBE},
        scheme.GENRE: {feature: 0 for feature in constant.GENRE},
    }


def merge_defaults(base: dict, extra: dict) -> dict:
    """Merge two defaults payloads with non-empty values from extra taking priority."""
    merged = {
        scheme.MAIN_INFO: {},
        scheme.RAW_SCORES: {},
        scheme.TAGS_VIBE: {},
        scheme.GENRE: {},
    }

    for section_name in merged.keys():
        base_section = base.get(section_name, {}) if isinstance(base, dict) else {}
        extra_section = extra.get(section_name, {}) if isinstance(extra, dict) else {}

        if section_name == scheme.GENRE:
            keys = set(base_section.keys()) | set(extra_section.keys())
            for key in keys:
                merged[section_name][key] = max(
                    int(base_section.get(key, 0) or 0),
                    int(extra_section.get(key, 0) or 0),
                )
            continue

        merged[section_name].update(base_section)
        for key, value in extra_section.items():
            if value is not None and value != "":
                merged[section_name][key] = value
            elif key not in merged[section_name]:
                merged[section_name][key] = value

    return merged


def build_tmdb_add_defaults(series: dict, genres: list | None = None, data_language: str = "ru") -> dict:
    """Build add-title defaults from a normalized TMDb object."""
    if genres is None:
        genres = extract_tmdb_genres(series)

    defaults = {
        scheme.MAIN_INFO: {
            "title": extract_tmdb_title(series),
            "user_score": None,
            "year": series.get("year"),
            "country": extract_country_value(series),
        },
        scheme.RAW_SCORES: extract_tmdb_raw_scores(series),
        scheme.TAGS_VIBE: {},
        scheme.GENRE: build_genre_defaults(genres),
    }
    localized_source = dict(series or {})
    tmdb_localized = localized_blocks_from_tmdb_details(series, current_language=data_language)
    if tmdb_localized:
        localized_source["localized"] = {
            **tmdb_localized,
            **dict(localized_source.get("localized") or {}),
        }
    localized_source["main_info"] = defaults[scheme.MAIN_INFO]
    localized = build_localized_block_from_legacy(localized_source, default_language=data_language)
    selected_language = str(data_language or "ru").strip().casefold()
    if selected_language not in {"ru", "en"}:
        selected_language = "ru"
    localized.setdefault(selected_language, {})
    selected_title = extract_tmdb_title(series)
    selected_overview = extract_tmdb_description(series)
    if selected_title:
        localized[selected_language]["title"] = selected_title
    if selected_overview:
        localized[selected_language]["overview"] = selected_overview
    if localized:
        defaults["localized"] = localized
    return defaults


build_api_defaults = build_tmdb_add_defaults

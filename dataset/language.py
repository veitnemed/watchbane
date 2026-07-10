"""Domain helpers for localized data display without machine translation."""

from __future__ import annotations

from collections.abc import Iterable
from copy import deepcopy
from typing import Any

SUPPORTED_DATA_LANGUAGES = ("ru", "en")
DATA_LANGUAGE_DEFAULT = "ru"
DATA_LANGUAGE_TMDB_LOCALES = {
    "ru": "ru-RU",
    "en": "en-US",
}
_ENGLISH_GENRE_LABELS_BY_KEY = {
    "drama": ("Drama",),
    "comedy": ("Comedy",),
    "crime": ("Crime",),
    "thriller": ("Thriller",),
    "horror": ("Horror",),
    "action_adventure": ("Action", "Adventure"),
    "sci_fi_fantasy": ("Sci-Fi", "Fantasy"),
    "mystery": ("Detective",),
    "detective": ("Detective",),
    "melodrama": ("Melodrama",),
    "romance": ("Romance",),
}
_LEGACY_DATASET_GENRE_KEY_ALIASES = {
    "has_action": "action_adventure",
    "has_fantasy": "sci_fi_fantasy",
    "has_detective": "mystery",
    "has_melodrama": "melodrama",
    "has_drama": "drama",
    "has_comedy": "comedy",
    "has_crime": "crime",
    "has_thriller": "thriller",
    "has_horror": "horror",
}


def _canonical_genre_key(raw_key: str) -> str:
    key = str(raw_key or "").strip()
    if key == "":
        return ""
    if key in _LEGACY_DATASET_GENRE_KEY_ALIASES:
        return _LEGACY_DATASET_GENRE_KEY_ALIASES[key]
    if key.startswith("has_"):
        return key.removeprefix("has_")
    return key


def normalize_data_language(value) -> str:
    """Return a supported data language code."""
    if isinstance(value, bool) or value in (None, ""):
        return DATA_LANGUAGE_DEFAULT
    text = str(value).strip().casefold()
    if text in SUPPORTED_DATA_LANGUAGES:
        return text
    return DATA_LANGUAGE_DEFAULT


def tmdb_locale_for_data_language(value) -> str:
    """Map supported data language to a TMDb locale."""
    return DATA_LANGUAGE_TMDB_LOCALES[normalize_data_language(value)]


def _as_dict(value) -> dict:
    return value if isinstance(value, dict) else {}


def _clean_text(value) -> str | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    return text if text else None


def _is_latinish_text(value: str | None) -> bool:
    text = _clean_text(value)
    if text is None:
        return False
    letters = [char for char in text if char.isalpha()]
    if not letters:
        return False
    latin_letters = [
        char for char in letters
        if ("a" <= char.casefold() <= "z")
    ]
    return len(latin_letters) / len(letters) >= 0.7


def _path_value(record: dict, selector: str | Iterable[str]):
    if isinstance(selector, str):
        parts = selector.split(".")
    else:
        parts = list(selector)

    current: Any = record
    for part in parts:
        if isinstance(current, dict) is False:
            return None
        current = current.get(part)
    return current


def _first_text(record: dict, selectors: Iterable[str | Iterable[str]]) -> str | None:
    for selector in selectors:
        text = _clean_text(_path_value(record, selector))
        if text is not None:
            return text
    return None


def _localized_text(record: dict, language: str, field: str) -> str | None:
    localized = _as_dict(record.get("localized"))
    language_block = _as_dict(localized.get(language))
    return _clean_text(language_block.get(field))


def localized_value(record: dict, field: str, language: str, fallbacks=()) -> str | None:
    """Return localized field value with selected-language -> ru -> legacy fallback."""
    source = _as_dict(record)
    normalized = normalize_data_language(language)

    selected = _localized_text(source, normalized, field)
    if selected is not None:
        return selected

    if normalized != "ru":
        ru_value = _localized_text(source, "ru", field)
        if ru_value is not None:
            return ru_value

    return _first_text(source, fallbacks)


def _translation_text(record: dict, language: str, *field_names: str) -> str | None:
    translations = _as_dict(record.get("translations"))
    candidate_blocks = [
        translations.get(language),
        translations.get(language.replace("-", "_")),
        translations.get(f"{language}-US"),
        translations.get(f"{language}_US"),
        translations.get(f"{language}-RU"),
        translations.get(f"{language}_RU"),
    ]
    for block in candidate_blocks:
        if isinstance(block, dict) is False:
            continue
        for field_name in field_names:
            text = _clean_text(block.get(field_name))
            if text is not None:
                return text

    raw_translations = record.get("translations")
    if isinstance(raw_translations, list):
        for item in raw_translations:
            if isinstance(item, dict) is False:
                continue
            item_language = _clean_text(
                item.get("iso_639_1")
                or item.get("language")
                or item.get("lang")
                or item.get("locale")
            )
            if item_language is None or item_language.split("-", 1)[0].casefold() != language:
                continue
            data = _as_dict(item.get("data")) or item
            for field_name in field_names:
                text = _clean_text(data.get(field_name))
                if text is not None:
                    return text
    return None


def _set_localized_if_missing(localized: dict, language: str, field: str, value: str | None) -> None:
    text = _clean_text(value)
    if text is None:
        return
    language_block = localized.setdefault(language, {})
    if _clean_text(language_block.get(field)) is None:
        language_block[field] = text


def build_localized_block_from_legacy(record: dict, default_language: str = "ru") -> dict:
    """Build/extend a localized block from existing fields only."""
    source = _as_dict(record)
    default = normalize_data_language(default_language)
    localized = deepcopy(_as_dict(source.get("localized")))

    _set_localized_if_missing(
        localized,
        default,
        "title",
        _first_text(source, ("main_info.title", "title", "name")),
    )
    _set_localized_if_missing(
        localized,
        default,
        "overview",
        _first_text(
            source,
            (
                "overview",
                "description",
                "tmdb_overview",
                "short_description",
                "shortDescription",
                "plot",
                "meta.description",
            ),
        ),
    )
    en_title = _first_text(
        source,
        (
            "enName",
            "alternative_title",
            "alternativeName",
            "title_en",
            "name_en",
        ),
    )
    if en_title is None:
        original_title = _first_text(source, ("original_title", "original_name"))
        en_title = original_title if _is_latinish_text(original_title) else None
    _set_localized_if_missing(localized, "en", "title", en_title)
    _set_localized_if_missing(
        localized,
        "en",
        "overview",
        _first_text(
            source,
            (
                "overview_en",
                "description_en",
                "tmdb_overview_en",
                "plot_en",
                "short_description_en",
                "shortDescription_en",
            ),
        )
        or _translation_text(source, "en", "overview", "description", "plot"),
    )

    return {
        language: block
        for language, block in localized.items()
        if isinstance(block, dict) and len(block) > 0
    }


def choose_display_title(record: dict, language: str) -> str | None:
    """Choose a display title for data language, falling back to legacy title."""
    source = _as_dict(record)
    normalized = normalize_data_language(language)

    if normalized == "en":
        en_value = _localized_text(source, "en", "title") or _first_text(
            source,
            (
                "enName",
                "alternative_title",
                "alternativeName",
                "title_en",
                "name_en",
            ),
        )
        if en_value is None:
            original_title = _first_text(source, ("original_title", "original_name"))
            en_value = original_title if _is_latinish_text(original_title) else None
        if en_value is not None:
            return en_value

    return localized_value(
        source,
        "title",
        normalized,
        ("main_info.title", "title", "name", "original_title", "original_name"),
    )


def choose_display_overview(record: dict, language: str) -> str | None:
    """Choose overview/description text for data language with safe fallback."""
    source = _as_dict(record)
    normalized = normalize_data_language(language)

    if normalized == "en":
        en_value = _localized_text(source, "en", "overview") or _first_text(
            source,
            (
                "overview_en",
                "description_en",
                "tmdb_overview_en",
                "plot_en",
                "short_description_en",
                "shortDescription_en",
            ),
        )
        en_value = en_value or _translation_text(source, "en", "overview", "description", "plot")
        if en_value is not None:
            return en_value

    return localized_value(
        source,
        "overview",
        normalized,
        (
            "overview",
            "description",
            "tmdb_overview",
            "short_description",
            "shortDescription",
            "plot",
            "meta.description",
        ),
    )


def choose_genre_labels(genre_keys, language: str) -> list[str]:
    """Map genre keys to labels for data language using candidate genre schema."""
    from candidates.models import genre_schema

    normalized = normalize_data_language(language)
    if isinstance(genre_keys, str):
        keys = [genre_keys]
    elif isinstance(genre_keys, (list, tuple, set)):
        keys = list(genre_keys)
    else:
        keys = []

    labels: list[str] = []
    seen: set[str] = set()

    for raw_key in keys:
        key = str(raw_key or "").strip()
        if key == "":
            continue
        canonical_key = _canonical_genre_key(key)
        if canonical_key == "":
            continue
        if normalized == "en" and canonical_key in _ENGLISH_GENRE_LABELS_BY_KEY:
            for text in _ENGLISH_GENRE_LABELS_BY_KEY[canonical_key]:
                label = _clean_text(text)
                if label is not None and label not in seen:
                    seen.add(label)
                    labels.append(label)
            continue

        display_labels = genre_schema.build_genres_display([canonical_key])
        if normalized == "en" and len(display_labels) == 0:
            display_labels = [canonical_key.replace("_", " ").title()]
        for display_label in display_labels:
            label = _clean_text(display_label)
            if label is not None and label not in seen:
                seen.add(label)
                labels.append(label)

    return labels

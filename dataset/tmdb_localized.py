"""TMDb localized read helpers for titles, overviews and poster hints."""

from __future__ import annotations

from typing import Any

from apis import tmdb_api
from dataset.language import SUPPORTED_DATA_LANGUAGES, normalize_data_language, tmdb_locale_for_data_language


def _clean_text(value: Any) -> str | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    return text if text else None


def _translation_items(details: dict[str, Any]) -> list[dict[str, Any]]:
    translations = details.get("translations") if isinstance(details, dict) else {}
    items = translations.get("translations") if isinstance(translations, dict) else translations
    return [item for item in items or [] if isinstance(item, dict)]


def translation_data_for_language(details: dict[str, Any], language: str) -> dict[str, Any]:
    """Return the best TMDb translation data block for a supported data language."""
    normalized = normalize_data_language(language)
    locale = tmdb_locale_for_data_language(normalized)
    expected_language, _, expected_country = locale.partition("-")
    fallback_data: dict[str, Any] = {}

    for translation in _translation_items(details):
        if str(translation.get("iso_639_1") or "").casefold() != expected_language.casefold():
            continue
        data = translation.get("data")
        if isinstance(data, dict) is False:
            continue
        if str(translation.get("iso_3166_1") or "").upper() == expected_country.upper():
            return data
        if not fallback_data:
            fallback_data = data
    return fallback_data


def _poster_items(details: dict[str, Any]) -> list[dict[str, Any]]:
    images = details.get("images") if isinstance(details, dict) else {}
    posters = images.get("posters") if isinstance(images, dict) else []
    return [
        item
        for item in posters or []
        if isinstance(item, dict) and _clean_text(item.get("file_path")) is not None
    ]


def _best_poster_path_for_language(details: dict[str, Any], language: str) -> str | None:
    normalized = normalize_data_language(language)
    candidates = [
        item
        for item in _poster_items(details)
        if str(item.get("iso_639_1") or "").casefold() == normalized
    ]
    if not candidates:
        return None

    def rank(item: dict[str, Any]) -> tuple[float, int]:
        return (
            float(item.get("vote_average") or 0),
            int(item.get("vote_count") or 0),
        )

    return _clean_text(max(candidates, key=rank).get("file_path"))


def localized_block_from_tmdb_details(
    details: dict[str, Any],
    language: str,
    *,
    current_language: str | None = None,
) -> dict[str, str]:
    """Extract localized display fields from one TMDb Details response."""
    normalized = normalize_data_language(language)
    current = normalize_data_language(current_language) if current_language is not None else None
    translation_data = translation_data_for_language(details, normalized)

    title = _clean_text(translation_data.get("name") or translation_data.get("title"))
    overview = _clean_text(translation_data.get("overview"))
    poster_path = _best_poster_path_for_language(details, normalized)

    if current == normalized:
        title = title or _clean_text(details.get("name") or details.get("title"))
        overview = overview or _clean_text(details.get("overview"))
        poster_path = poster_path or _clean_text(details.get("poster_path"))

    block: dict[str, str] = {}
    if title is not None:
        block["title"] = title
    if overview is not None:
        block["overview"] = overview
    if poster_path is not None:
        block["poster_path"] = poster_path
        poster_url = tmdb_api.image_link(poster_path)
        if poster_url is not None:
            block["poster_url"] = poster_url
    return block


def localized_blocks_from_tmdb_details(
    details: dict[str, Any],
    *,
    current_language: str | None = None,
) -> dict[str, dict[str, str]]:
    """Extract all supported localized blocks available in a TMDb Details response."""
    blocks: dict[str, dict[str, str]] = {}
    for language in SUPPORTED_DATA_LANGUAGES:
        block = localized_block_from_tmdb_details(
            details,
            language,
            current_language=current_language,
        )
        if block:
            blocks[language] = block
    return blocks

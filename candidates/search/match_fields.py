"""Detect which search-document fields matched a user query."""

from __future__ import annotations

import re

from candidates.search.document import (
    _iter_cast_parts,
    _iter_country_parts,
    _iter_genre_parts,
    _iter_title_parts,
    _strip_html,
    _truncate_overview,
)
from candidates.search.query_expand import expand_query_tokens
from dataset.language import choose_display_overview, normalize_data_language

_FIELD_LABELS = {
    "title_ru": "название",
    "title_en": "title",
    "original_title": "оригинальное название",
    "genre": "жанр",
    "country": "страна",
    "overview": "описание",
    "cast": "актёры",
}

_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _contains_token(haystack: str, token: str) -> bool:
    return token in str(haystack or "").casefold()


def _match_any_token(values: list[str], tokens: list[str]) -> bool:
    joined = " ".join(str(value).casefold() for value in values if str(value or "").strip())
    return any(_contains_token(joined, token) for token in tokens)


def find_matched_fields(candidate: dict, query: str, *, data_language: str = "ru") -> list[str]:
    """Return compact field ids explaining why a candidate matched the query."""
    tokens = expand_query_tokens(query)
    if not tokens:
        return []

    language = normalize_data_language(data_language)
    matched: list[str] = []

    title_values = [str(value).casefold() for value in _iter_title_parts(candidate)]
    if any(token in " ".join(title_values) for token in tokens):
        if language == "ru":
            matched.append("title_ru")
        else:
            matched.append("title_en")
        original = str(candidate.get("original_title") or candidate.get("original_name") or "").casefold()
        if original and any(token in original for token in tokens):
            matched.append("original_title")

    if _match_any_token(_iter_genre_parts(candidate), tokens):
        genre_keys = candidate.get("genre_keys") or []
        genre_field = "genre"
        if isinstance(genre_keys, list):
            for genre_key in genre_keys:
                if any(token in str(genre_key).casefold() for token in tokens):
                    genre_field = f"genre:{genre_key}"
                    break
        matched.append(genre_field)

    if _match_any_token(_iter_country_parts(candidate), tokens):
        matched.append("country")

    overview_parts = []
    overview = choose_display_overview(candidate, language)
    if overview:
        overview_parts.append(_truncate_overview(overview))
    for alt_language in ("ru", "en"):
        alt_overview = choose_display_overview(candidate, alt_language)
        if alt_overview:
            overview_parts.append(_truncate_overview(alt_overview))
    if _match_any_token(overview_parts, tokens):
        matched.append("overview")

    if _match_any_token(_iter_cast_parts(candidate), tokens):
        matched.append("cast")

    deduped: list[str] = []
    seen: set[str] = set()
    for field in matched:
        if field in seen:
            continue
        seen.add(field)
        deduped.append(field)
    return deduped


def matched_field_labels(fields: list[str]) -> list[str]:
    """Map internal field ids to short Russian labels for UI."""
    labels: list[str] = []
    for field in fields:
        if field.startswith("genre:"):
            labels.append(_FIELD_LABELS["genre"])
            continue
        labels.append(_FIELD_LABELS.get(field, field))
    return labels

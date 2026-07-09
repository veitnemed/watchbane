"""Deterministic search document builder for FTS indexing."""

from __future__ import annotations

import html
import re

from candidates.models import country_schema, genre_schema
from dataset.language import choose_display_overview, choose_display_title, normalize_data_language

DOCUMENT_VERSION = 1
OVERVIEW_LIMIT = 200
CAST_LIMIT = 3

_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(value: str) -> str:
    text = _HTML_TAG_RE.sub(" ", str(value or ""))
    return html.unescape(text).strip()


def _truncate_overview(value: str, *, limit: int = OVERVIEW_LIMIT) -> str:
    text = _strip_html(value)
    if len(text) <= limit:
        return text
    return text[:limit].rstrip()


def _iter_title_parts(candidate: dict) -> list[str]:
    parts = [
        candidate.get("title"),
        candidate.get("name"),
        candidate.get("alternative_title"),
        candidate.get("alternativeName"),
        candidate.get("enName"),
        candidate.get("original_title"),
        candidate.get("original_name"),
    ]
    localized = candidate.get("localized")
    if isinstance(localized, dict):
        for language in ("ru", "en"):
            block = localized.get(language)
            if isinstance(block, dict):
                parts.append(block.get("title"))
    for language in ("ru", "en"):
        parts.append(choose_display_title(candidate, language))
    return [str(part).strip() for part in parts if part not in (None, "")]


def _iter_genre_parts(candidate: dict) -> list[str]:
    parts: list[str] = []
    genre_keys = candidate.get("genre_keys")
    if isinstance(genre_keys, list) and genre_keys:
        parts.extend(genre_schema.build_genres_display(genre_keys))
    else:
        parts.extend(genre_schema.candidate_genres_for_display(candidate))
    for field_name in ("genres_tmdb", "genres"):
        raw = candidate.get(field_name)
        if isinstance(raw, list):
            parts.extend(str(item).strip() for item in raw if str(item or "").strip())
        elif isinstance(raw, str) and raw.strip():
            parts.append(raw.strip())
    return parts


def _iter_country_parts(candidate: dict) -> list[str]:
    parts: list[str] = []
    codes = candidate.get("country_codes")
    if not isinstance(codes, list) or not codes:
        codes = country_schema.build_country_codes(candidate)
    for iso2 in codes:
        parts.append(str(iso2).strip())
        for language in ("ru", "en"):
            label = country_schema.build_country_display([iso2], language=language)
            if label:
                parts.append(label)
    for field_name in ("countries", "tmdb_production_countries", "tmdb_origin_countries"):
        raw = candidate.get(field_name)
        if isinstance(raw, list):
            parts.extend(str(item).strip() for item in raw if str(item or "").strip())
        elif isinstance(raw, str) and raw.strip():
            parts.append(raw.strip())
    return parts


def _iter_cast_parts(candidate: dict) -> list[str]:
    actors = candidate.get("actors_top")
    if not isinstance(actors, list):
        return []
    names: list[str] = []
    for actor in actors[:CAST_LIMIT]:
        if isinstance(actor, dict):
            name = str(actor.get("name") or "").strip()
            if name:
                names.append(name)
        else:
            text = str(actor or "").strip()
            if text:
                names.append(text)
    return names


def _dedupe_tokens(text: str) -> str:
    seen: set[str] = set()
    tokens: list[str] = []
    for token in text.split():
        if token in seen:
            continue
        seen.add(token)
        tokens.append(token)
    return " ".join(tokens)


def build_search_document(candidate: dict, *, data_language: str = "ru") -> str:
    """Build lowercase FTS document from candidate metadata."""
    language = normalize_data_language(data_language)
    parts: list[str] = []
    parts.extend(_iter_title_parts(candidate))
    parts.extend(_iter_genre_parts(candidate))
    parts.extend(_iter_country_parts(candidate))

    overview = choose_display_overview(candidate, language)
    if overview:
        parts.append(_truncate_overview(overview))
    for alt_language in ("ru", "en"):
        if alt_language == language:
            continue
        alt_overview = choose_display_overview(candidate, alt_language)
        if alt_overview:
            parts.append(_truncate_overview(alt_overview))

    parts.extend(_iter_cast_parts(candidate))

    normalized = " ".join(
        str(part).strip().casefold()
        for part in parts
        if str(part or "").strip()
    )
    return _dedupe_tokens(normalized)

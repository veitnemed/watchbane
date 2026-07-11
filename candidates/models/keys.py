"""Key helpers for candidate identity and candidate-pool storage."""

from __future__ import annotations

from typing import Any

from dataset.models.media_type import MEDIA_TYPE_MOVIE, normalize_media_type


COMMON_POOL_CRITERIA_NAME = "pool"
DEFAULT_CRITERIA_NAME = COMMON_POOL_CRITERIA_NAME
_KEY_PART_SPACES = [
    ".",
    ",",
    "!",
    "?",
    ":",
    ";",
    "\"",
    "'",
    "`",
    "«",
    "»",
    "(",
    ")",
    "[",
    "]",
]


def normalize_key_part(value: Any) -> str:
    """Normalizes one key fragment to a stable lowercase form."""
    text = str(value or "").strip().casefold()
    text = text.replace("ё", "е")
    for char in _KEY_PART_SPACES:
        text = text.replace(char, " ")
    while "  " in text:
        text = text.replace("  ", " ")
    return text.strip()


def _candidate_title(candidate: dict) -> str:
    return (
        candidate.get("title")
        or candidate.get("alternative_title")
        or candidate.get("name")
        or candidate.get("alternativeName")
        or candidate.get("enName")
        or ""
    )


def title_identity_key(candidate: dict) -> str:
    """Builds normalized_title|year identity for watched matching/title identity."""
    title = normalize_key_part(_candidate_title(candidate))
    year = str(candidate.get("year") or "").strip()
    return f"{title}|{year}"


def candidate_state_identity_key(candidate: dict) -> str:
    """Build a media-aware identity for user state transitions."""
    return f"{title_identity_key(candidate)}|{normalize_media_type(candidate.get('media_type'))}"


def candidate_state_identity_keys(candidate: dict) -> tuple[str, ...]:
    """Return current and legacy identities used by candidate actions."""
    current = candidate_state_identity_key(candidate)
    legacy = title_identity_key(candidate)
    return (current,) if current == legacy else (current, legacy)


def pool_entry_key(candidate: dict) -> str:
    """Builds a storage key for the single shared candidate pool."""
    key = title_identity_key(candidate)
    if key == "|":
        return key
    if normalize_media_type(candidate.get("media_type")) == MEDIA_TYPE_MOVIE:
        return f"{key}|{MEDIA_TYPE_MOVIE}"
    return key

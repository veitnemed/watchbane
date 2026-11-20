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


def candidate_typed_state_key(candidate: dict) -> str | None:
    """Only a positive integral TMDb ID can act as a stable action identity."""
    value = candidate.get("tmdb_id")
    if type(value) is int:
        tmdb_id = value
    elif type(value) is str and (text := value.strip()).isascii() and text.isdecimal() and len(text) <= 20:
        tmdb_id = int(text)
    else:
        return None
    if tmdb_id <= 0:
        return None
    return f"tmdb:{normalize_media_type(candidate.get('media_type'))}:{tmdb_id}"


def candidate_legacy_state_keys(candidate: dict) -> tuple[str, str]:
    legacy = title_identity_key(candidate)
    return f"{legacy}|{normalize_media_type(candidate.get('media_type'))}", legacy


def candidate_state_identity_key(candidate: dict) -> str:
    """Return the legacy media-aware title key used by recommendation history."""
    return candidate_legacy_state_keys(candidate)[0]


def candidate_action_identity_key(candidate: dict) -> str:
    """Return the stable typed action identity, or a scoped title key without an ID."""
    return candidate_typed_state_key(candidate) or candidate_state_identity_key(candidate)


def candidate_state_identity_keys(candidate: dict) -> tuple[str, ...]:
    """A typed identity must never fall through to a conflicting title key."""
    typed = candidate_typed_state_key(candidate)
    return (typed,) if typed else candidate_legacy_state_keys(candidate)


def pool_entry_key(candidate: dict) -> str:
    """Builds a storage key for the single shared candidate pool."""
    key = title_identity_key(candidate)
    if key == "|":
        return key
    if normalize_media_type(candidate.get("media_type")) == MEDIA_TYPE_MOVIE:
        return f"{key}|{MEDIA_TYPE_MOVIE}"
    return key

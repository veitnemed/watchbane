"""Key helpers for candidate identity and candidate-pool storage."""

from __future__ import annotations

from typing import Any


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
        candidate.get("name")
        or candidate.get("title")
        or candidate.get("alternativeName")
        or candidate.get("alternative_title")
        or candidate.get("enName")
        or ""
    )


def title_identity_key(candidate: dict) -> str:
    """Builds normalized_title|year identity for watched matching/title identity."""
    title = normalize_key_part(_candidate_title(candidate))
    year = str(candidate.get("year") or "").strip()
    return f"{title}|{year}"


def pool_entry_key(candidate: dict) -> str:
    """Builds title|year key for the single shared candidate pool."""
    return title_identity_key(candidate)

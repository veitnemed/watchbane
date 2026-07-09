"""Query token expansion: aliases and narrow typo/prefix fallback."""

from __future__ import annotations

import json
from pathlib import Path

_ALIASES_PATH = Path(__file__).with_name("title_aliases.json")
_ALIASES_CACHE: dict[str, list[str]] | None = None


def _load_aliases() -> dict[str, list[str]]:
    global _ALIASES_CACHE
    if _ALIASES_CACHE is not None:
        return _ALIASES_CACHE
    aliases: dict[str, list[str]] = {}
    try:
        payload = json.loads(_ALIASES_PATH.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            for key, values in payload.items():
                normalized_key = str(key or "").strip().casefold()
                if normalized_key == "":
                    continue
                expanded = [normalized_key]
                if isinstance(values, list):
                    for value in values:
                        text = str(value or "").strip().casefold()
                        if text and text not in expanded:
                            expanded.append(text)
                aliases[normalized_key] = expanded
    except (OSError, json.JSONDecodeError):
        aliases = {}
    _ALIASES_CACHE = aliases
    return aliases


def _one_edit_variants(token: str, *, limit: int = 12) -> list[str]:
    if len(token) < 4:
        return []
    alphabet = "абвгдежзийклмнопрстуфхцчшщъыьэюяabcdefghijklmnopqrstuvwxyz0123456789"
    variants: list[str] = []
    for index, char in enumerate(token):
        prefix = token[:index]
        suffix = token[index + 1 :]
        deletion = prefix + suffix
        if deletion and deletion != token:
            variants.append(deletion)
        for replacement in alphabet:
            if replacement == char:
                continue
            candidate = prefix + replacement + suffix
            if candidate and candidate != token:
                variants.append(candidate)
            if len(variants) >= limit:
                return variants
    return variants[:limit]


def expand_query_token_groups(query: str) -> list[list[str]]:
    """Return OR-groups for FTS MATCH (AND across groups)."""
    normalized = str(query or "").strip().casefold()
    if normalized == "":
        return []

    aliases = _load_aliases()
    phrase_aliases = aliases.get(normalized)
    if phrase_aliases:
        return [list(phrase_aliases)]

    groups: list[list[str]] = []
    for token in (part for part in normalized.split() if part):
        group = [token]
        if len(token) >= 4:
            prefix = token[:4]
            if prefix not in group:
                group.append(prefix)
        for alias in aliases.get(token, ()):
            if alias not in group:
                group.append(alias)
        groups.append(group)
    return groups


def expand_query_typo_groups(query: str) -> list[list[str]]:
    """Fallback OR-groups with a small 1-edit neighborhood per token."""
    groups = expand_query_token_groups(query)
    if not groups:
        return []
    typo_groups: list[list[str]] = []
    for group in groups:
        token = group[0]
        variants = _one_edit_variants(token)
        if not variants:
            continue
        typo_groups.append([token, *variants])
    return typo_groups


def expand_query_tokens(query: str) -> list[str]:
    """Flat token list for substring-style field matching."""
    tokens: list[str] = []
    seen: set[str] = set()

    def add_token(token: str) -> None:
        text = str(token or "").strip().casefold()
        if text == "" or text in seen:
            return
        seen.add(text)
        tokens.append(text)

    for group in expand_query_token_groups(query):
        for token in group:
            add_token(token)
    for group in expand_query_typo_groups(query):
        for token in group:
            add_token(token)
    return tokens

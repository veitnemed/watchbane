"""TMDb title identity matching for poster search and diagnostics."""

from __future__ import annotations

from difflib import SequenceMatcher

from common.text_match import normalize_for_match, transliterate_to_latin
from dataset.resolve.helpers import add_title_value


def extract_api_identity_titles(candidate: dict | None) -> list:
    """Собирает названия API-кандидата, по которым можно проверять identity."""
    if not isinstance(candidate, dict):
        return []

    titles = []
    for key in ("title", "name", "original_title", "original_name", "originalName", "alternativeName", "enName"):
        add_title_value(titles, candidate.get(key))
    return titles


def normalize_identity_title(value) -> str:
    """Нормализует название для безопасного сравнения identity."""
    return normalize_for_match(value).replace("ё", "е")


def title_identity_match(left, right) -> bool:
    """Проверяет, похожи ли два названия достаточно для identity gate."""
    left_norm = normalize_identity_title(left)
    right_norm = normalize_identity_title(right)
    if left_norm == "" or right_norm == "":
        return False
    if left_norm == right_norm:
        return True
    if min(len(left_norm), len(right_norm)) >= 4 and (left_norm in right_norm or right_norm in left_norm):
        return True

    left_translit = transliterate_to_latin(left_norm)
    right_translit = transliterate_to_latin(right_norm)
    if left_translit and right_translit and left_translit == right_translit:
        return True

    ratio = SequenceMatcher(None, left_norm, right_norm).ratio()
    if ratio >= 0.82:
        return True

    left_tokens = set(left_norm.split())
    right_tokens = set(right_norm.split())
    common = left_tokens & right_tokens
    if len(common) >= 2:
        return True
    return len(common) == 1 and min(len(left_tokens), len(right_tokens)) == 1

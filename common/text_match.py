"""Text normalization helpers for title identity matching."""

from __future__ import annotations

import re

CYRILLIC_TO_LATIN = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d",
    "е": "e", "ё": "e", "ж": "zh", "з": "z", "и": "i",
    "й": "y", "к": "k", "л": "l", "м": "m", "н": "n",
    "о": "o", "п": "p", "р": "r", "с": "s", "т": "t",
    "у": "u", "ф": "f", "х": "h", "ц": "ts", "ч": "ch",
    "ш": "sh", "щ": "sch", "ъ": "", "ы": "y", "ь": "",
    "э": "e", "ю": "yu", "я": "ya",
}


def normalize_text(value) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def normalize_for_match(value) -> str:
    text = normalize_text(value).casefold()
    text = re.sub(r"[^0-9a-z\u0400-\u04FF]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def transliterate_to_latin(text: str) -> str:
    if not text:
        return ""
    return "".join(CYRILLIC_TO_LATIN.get(char, char) for char in text)

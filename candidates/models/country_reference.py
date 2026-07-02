"""Country aliases shared by candidate and dataset metadata helpers."""

from __future__ import annotations


COUNTRY_NAME_BY_ISO2 = {
    "RU": "Россия",
    "US": "США",
    "GB": "Великобритания",
    "KR": "Южная Корея",
    "JP": "Япония",
    "FR": "Франция",
    "DE": "Германия",
    "ES": "Испания",
    "IT": "Италия",
    "TR": "Турция",
    "CN": "Китай",
    "IN": "Индия",
    "CA": "Канада",
    "AU": "Австралия",
    "BR": "Бразилия",
    "MX": "Мексика",
    "AR": "Аргентина",
    "SE": "Швеция",
    "NO": "Норвегия",
    "DK": "Дания",
    "FI": "Финляндия",
    "PL": "Польша",
    "NL": "Нидерланды",
    "BE": "Бельгия",
    "IE": "Ирландия",
    "UA": "Украина",
}

KR_COUNTRY_ALIASES = (
    "Южная Корея",
    "Корея Южная",
    "Республика Корея",
    "South Korea",
    "Republic of Korea",
    "Korea, Republic of",
    "KR",
)

_COUNTRY_ALIAS_TO_CANONICAL: dict[str, str] = {}


def _normalize_country_key(value: str) -> str:
    text = str(value or "").strip().casefold().replace("ё", "е")
    while "  " in text:
        text = text.replace("  ", " ")
    return text.strip()


def _register_country_aliases(canonical: str, *aliases: str) -> None:
    for alias in aliases:
        key = _normalize_country_key(alias)
        if key:
            _COUNTRY_ALIAS_TO_CANONICAL[key] = canonical


def _init_country_alias_map() -> None:
    for iso2, name in COUNTRY_NAME_BY_ISO2.items():
        _register_country_aliases(iso2, iso2, name)
    _register_country_aliases("KR", *KR_COUNTRY_ALIASES)


_init_country_alias_map()


def normalize_iso2_country(value: str | None) -> str:
    return str(value or "").strip().upper()


def normalize_country_alias(value: str) -> str:
    """Maps a country label/code to canonical ISO-2 when alias is known."""
    key = _normalize_country_key(value)
    if key == "":
        return ""
    return _COUNTRY_ALIAS_TO_CANONICAL.get(key, key)


def country_value_to_iso2(value: str) -> str | None:
    """Map one raw country label/code to ISO-2 when alias is known."""
    text = str(value or "").strip()
    if text == "":
        return None

    iso2 = normalize_iso2_country(text)
    if iso2 in COUNTRY_NAME_BY_ISO2:
        return iso2

    canonical = normalize_country_alias(text)
    if canonical in COUNTRY_NAME_BY_ISO2:
        return canonical
    return None

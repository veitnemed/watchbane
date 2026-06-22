"""Список стран для выбора TMDb Discover country в консольном UI.

Русские названия синхронизированы с candidates.kp_enrichment.KP_COUNTRY_BY_ISO2
для перевода ISO-2 -> country label в KP API enrichment.
"""

from __future__ import annotations


COUNTRY_NAMES_RU_BY_CODE: dict[str, str] = {
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

COUNTRY_CODE_ORDER: list[str] = [
    "RU",
    "US",
    "GB",
    "KR",
    "JP",
    "FR",
    "DE",
    "ES",
    "IT",
    "TR",
    "CN",
    "IN",
    "CA",
    "AU",
    "BR",
    "MX",
    "AR",
    "SE",
    "NO",
    "DK",
    "FI",
    "PL",
    "NL",
    "BE",
    "IE",
    "UA",
]


def country_options() -> list[dict[str, str]]:
    """Возвращает страны в порядке показа в UI."""
    return [
        {"code": code, "label": COUNTRY_NAMES_RU_BY_CODE[code]}
        for code in COUNTRY_CODE_ORDER
    ]


def parse_country_indexes(value: str, options: list[dict[str, str]] | None = None) -> list[str] | None:
    """Разбирает ввод номеров стран через запятую или пробел в список ISO-2 кодов."""
    text = str(value or "").strip()
    if text == "":
        return [COUNTRY_CODE_ORDER[0]]

    options = options or country_options()
    codes = []
    for part in text.replace(",", " ").split():
        try:
            index = int(part)
        except ValueError:
            return None
        if index < 1 or index > len(options):
            return None
        code = options[index - 1]["code"]
        if code not in codes:
            codes.append(code)
    return codes


def country_label(code: str) -> str:
    """Возвращает русское название страны или сам код, если он неизвестен."""
    normalized_code = str(code or "").strip().upper()
    return COUNTRY_NAMES_RU_BY_CODE.get(normalized_code, normalized_code)


def country_labels(codes: list[str]) -> list[str]:
    """Возвращает русские названия выбранных стран."""
    return [country_label(code) for code in codes]


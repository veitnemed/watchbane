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


ADD_TITLE_COUNTRY_ANY_LABEL = "Не важно"


def add_title_country_combo_options() -> list[tuple[str, str]]:
    """Return (label, value) pairs for add-title country selector."""
    return [(ADD_TITLE_COUNTRY_ANY_LABEL, "")] + [
        (option["label"], option["label"])
        for option in country_options()
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


def print_country_options(output_func=print) -> None:
    """Печатает нумерованный список стран для консольного выбора."""
    options = country_options()
    parts = [
        f"{index}. {option['label']}"
        for index, option in enumerate(options, start=1)
    ]
    output_func("Список:")
    for start in range(0, len(parts), 5):
        output_func("; ".join(parts[start:start + 5]))


def parse_single_country_index(value: str, options_count: int) -> int | None:
    """Разбирает один номер страны; пустой ввод = 1 (Россия); 0 = без фильтра KP."""
    text = str(value or "").strip()
    if text == "":
        return 1

    parts = text.replace(",", " ").split()
    if len(parts) != 1:
        return None
    try:
        index = int(parts[0])
    except ValueError:
        return None
    if index == 0:
        return 0
    if index < 1 or index > options_count:
        return None
    return index


def choose_single_country_label(input_func=input, output_func=print) -> str:
    """Запрашивает одну страну по номеру; '' = KP без фильтра страны."""
    options = country_options()
    output_func("\nСтрана производства:")
    output_func("0 >> KP без фильтра страны")
    output_func("Введите номер страны из списка:")
    print_country_options(output_func)

    while True:
        answer = input_func(">> [1] ").strip()
        index = parse_single_country_index(answer, len(options))
        if index is None:
            output_func("Введите номер страны: 0 или 1–26, например: 2")
            continue
        if index == 0:
            return ""
        return options[index - 1]["label"]


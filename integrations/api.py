"""Получает данные о сериале из внешнего API и возвращает единый JSON-словарь."""

import json
import os
from json import JSONDecodeError
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


API_URL = os.getenv("KINOPOISK_API_URL", "https://api.kinopoisk.dev/v1.4")
TOKEN = os.getenv("KINOPOISK_API_KEY") or os.getenv("POISKKINO_API_KEY")
DEFAULT_LIMIT = 10
SERIES_TYPES = {"tv-series", "series", "mini-series", "animated-series"}

if TOKEN is None:
    try:
        from integrations.api_token import TOKEN
    except ImportError:
        try:
            from api_token import TOKEN
        except ImportError:
            TOKEN = None


def make_response(ok: bool, data=None, error: str = None, details: str = None) -> dict:
    """Собирает единый ответ API-модуля."""
    return {
        "ok": ok,
        "data": data,
        "error": error,
        "details": details,
    }


def normalize_text(value) -> str:
    """Приводит пользовательский ввод к строке без лишних пробелов."""
    return str(value or "").strip()


def validate_series_request(title, country) -> dict:
    """Проверяет входные данные запроса сериала."""
    title = normalize_text(title)
    country = normalize_text(country)

    if title == "":
        return make_response(False, error="empty_title", details="Название сериала не задано.")
    if country == "":
        return make_response(False, error="empty_country", details="Страна не задана.")

    return make_response(True, data={"title": title, "country": country})


def build_search_url(title: str, limit: int = DEFAULT_LIMIT) -> str:
    """Собирает URL поиска по названию."""
    query = urlencode({
        "query": title,
        "limit": limit,
        "page": 1,
    })
    return f"{API_URL}/movie/search?{query}"


def fetch_json(url: str, token: str, timeout: int = 10, opener=urlopen) -> dict:
    """Загружает JSON с обработкой сетевых ошибок и ошибок формата ответа."""
    if token is None:
        return make_response(False, error="missing_token", details="Не задан KINOPOISK_API_KEY.")

    request = Request(url, headers={
        "X-API-KEY": token,
        "Accept": "application/json",
    })

    try:
        with opener(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except HTTPError as error:
        return make_response(False, error="http_error", details=f"HTTP {error.code}")
    except URLError as error:
        return make_response(False, error="network_error", details=str(error.reason))
    except TimeoutError:
        return make_response(False, error="timeout", details="Внешний API не ответил вовремя.")
    except OSError as error:
        return make_response(False, error="network_error", details=str(error))

    try:
        return make_response(True, data=json.loads(raw))
    except JSONDecodeError:
        return make_response(False, error="invalid_json", details="Внешний API вернул не JSON.")


def get_docs(payload: dict) -> list:
    """Возвращает список найденных объектов из ответа API."""
    if isinstance(payload, dict):
        docs = payload.get("docs", [])
        if isinstance(docs, list):
            return docs
    return []


def normalize_country_name(country: str) -> str:
    """Нормализует название страны для мягкого сравнения."""
    return normalize_text(country).casefold()


def movie_has_country(movie: dict, country: str) -> bool:
    """Проверяет, есть ли нужная страна среди стран объекта."""
    expected = normalize_country_name(country)
    for item in movie.get("countries", []) or []:
        if normalize_country_name(item.get("name")) == expected:
            return True
    return False


def is_series(movie: dict) -> bool:
    """Проверяет, похож ли найденный объект на сериал."""
    movie_type = normalize_text(movie.get("type"))
    return movie_type in SERIES_TYPES


def choose_series(docs: list, country: str) -> dict:
    """Выбирает первый сериал из нужной страны."""
    for movie in docs:
        if isinstance(movie, dict) and is_series(movie) and movie_has_country(movie, country):
            return movie
    return None


def safe_nested(data: dict, section: str, field: str):
    """Достает вложенное поле из словаря, если оно есть."""
    value = data.get(section)
    if isinstance(value, dict):
        return value.get(field)
    return None


def extract_series_info(movie: dict) -> dict:
    """Извлекает полезные поля сериала для датасета и диагностики."""
    countries = [
        item.get("name")
        for item in movie.get("countries", []) or []
        if isinstance(item, dict) and item.get("name")
    ]

    return {
        "id": movie.get("id"),
        "title": movie.get("name") or movie.get("alternativeName") or movie.get("enName"),
        "alternative_title": movie.get("alternativeName") or movie.get("enName"),
        "year": movie.get("year"),
        "type": movie.get("type"),
        "description": movie.get("description") or movie.get("shortDescription"),
        "countries": countries,
        "kp_score": safe_nested(movie, "rating", "kp"),
        "kp_votes": safe_nested(movie, "votes", "kp"),
        "imdb_score": safe_nested(movie, "rating", "imdb"),
        "imdb_votes": safe_nested(movie, "votes", "imdb"),
    }


def dict_to_lines(data: dict, indent: int = 0) -> list:
    """Преобразует словарь в строки формата key: value."""
    lines = []
    prefix = " " * indent
    for key, value in data.items():
        if isinstance(value, dict):
            lines.append(f"{prefix}{key}:")
            lines.extend(dict_to_lines(value, indent + 4))
        else:
            lines.append(f"{prefix}{key}: {value}")
    return lines


def print_dict(data: dict) -> None:
    """Печатает словарь построчно в формате key: value."""
    for line in dict_to_lines(data):
        print(line)


def get_nested(data: dict, *keys):
    """Достает вложенное значение по цепочке ключей."""
    value = data
    for key in keys:
        if isinstance(value, dict) is False:
            return None
        value = value.get(key)
    return value


def names_from_list(items: list, key: str = "name", limit: int = None) -> str:
    """Собирает строку с названиями из списка словарей."""
    if isinstance(items, list) is False:
        return "None"

    names = []
    for item in items:
        if isinstance(item, dict) and item.get(key):
            names.append(str(item[key]))
        elif isinstance(item, str):
            names.append(item)

    if limit is not None:
        names = names[:limit]

    if len(names) == 0:
        return "None"
    return ", ".join(names)


def format_api_value(value) -> str:
    """Форматирует пустые и вложенные значения для красивого вывода."""
    if value is None or value == "":
        return "None"
    if isinstance(value, bool):
        return "да" if value else "нет"
    return str(value)


def add_api_line(lines: list, label: str, value) -> None:
    """Добавляет строку признака в читаемый API-отчет."""
    lines.append(f"{label}: {format_api_value(value)}")


def add_api_section(lines: list, title: str) -> None:
    """Добавляет заголовок секции в читаемый API-отчет."""
    lines.append("")
    lines.append(title)
    lines.append("-" * 60)


def format_persons(persons: list, limit: int = 10) -> list:
    """Форматирует список персон из API."""
    if isinstance(persons, list) is False or len(persons) == 0:
        return ["None"]

    lines = []
    for person in persons[:limit]:
        if isinstance(person, dict) is False:
            continue
        name = person.get("name") or person.get("enName") or "None"
        profession = person.get("profession") or person.get("enProfession") or "None"
        description = person.get("description")
        if description:
            lines.append(f"{name} | {profession} | {description}")
        else:
            lines.append(f"{name} | {profession}")

    if len(lines) == 0:
        return ["None"]
    return lines


def format_api_movie_lines(movie: dict) -> list:
    """Собирает красивый текстовый вывод полного API-объекта сериала."""
    shown_keys = {
        "id", "externalId", "name", "alternativeName", "enName", "type",
        "typeNumber", "year", "releaseYears", "description",
        "shortDescription", "slogan", "status", "isSeries", "ageRating",
        "rating", "votes", "countries", "genres", "movieLength",
        "seriesLength", "totalSeriesLength", "seasonsInfo", "networks",
        "productionCompanies", "persons", "premiere", "watchability",
    }

    lines = []
    lines.append("API признаки сериала")
    lines.append("=" * 60)

    add_api_section(lines, "Основное")
    add_api_line(lines, "ID", movie.get("id"))
    add_api_line(lines, "Название", movie.get("name"))
    add_api_line(lines, "Альтернативное название", movie.get("alternativeName"))
    add_api_line(lines, "Английское название", movie.get("enName"))
    add_api_line(lines, "Год", movie.get("year"))
    add_api_line(lines, "Тип", movie.get("type"))
    add_api_line(lines, "Статус", movie.get("status"))
    add_api_line(lines, "Сериал", movie.get("isSeries"))
    add_api_line(lines, "Возрастной рейтинг", movie.get("ageRating"))

    add_api_section(lines, "Описание")
    add_api_line(lines, "Краткое", movie.get("shortDescription"))
    add_api_line(lines, "Полное", movie.get("description"))
    add_api_line(lines, "Слоган", movie.get("slogan"))

    add_api_section(lines, "Рейтинги")
    rating = movie.get("rating") or {}
    if len(rating) == 0:
        lines.append("None")
    else:
        for key, value in rating.items():
            add_api_line(lines, key, value)

    add_api_section(lines, "Голоса")
    votes = movie.get("votes") or {}
    if len(votes) == 0:
        lines.append("None")
    else:
        for key, value in votes.items():
            add_api_line(lines, key, value)

    add_api_section(lines, "Страны и жанры")
    add_api_line(lines, "Страны", names_from_list(movie.get("countries")))
    add_api_line(lines, "Жанры", names_from_list(movie.get("genres")))

    add_api_section(lines, "Длительность и сезоны")
    add_api_line(lines, "Длина фильма", movie.get("movieLength"))
    add_api_line(lines, "Длина серии", movie.get("seriesLength"))
    add_api_line(lines, "Общая длина серий", movie.get("totalSeriesLength"))
    seasons = movie.get("seasonsInfo")
    if isinstance(seasons, list) and len(seasons) > 0:
        for season in seasons:
            season_number = season.get("number")
            episodes_count = season.get("episodesCount")
            lines.append(f"Сезон {season_number}: серий {format_api_value(episodes_count)}")
    else:
        lines.append("Сезоны: None")

    add_api_section(lines, "Площадки и производство")
    add_api_line(lines, "Сети", names_from_list(get_nested(movie, "networks", "items")))
    add_api_line(lines, "Где смотреть", names_from_list(get_nested(movie, "watchability", "items"), limit=10))
    add_api_line(lines, "Производство", names_from_list(movie.get("productionCompanies")))

    add_api_section(lines, "Премьеры")
    premiere = movie.get("premiere") or {}
    if len(premiere) == 0:
        lines.append("None")
    else:
        for key, value in premiere.items():
            add_api_line(lines, key, value)

    add_api_section(lines, "Персоны")
    lines.extend(format_persons(movie.get("persons")))

    other_keys = sorted(key for key in movie.keys() if key not in shown_keys)
    add_api_section(lines, "Остальные поля JSON")
    if len(other_keys) == 0:
        lines.append("None")
    else:
        lines.append(", ".join(other_keys))

    return lines


def find_series(title, country, token: str = TOKEN, opener=urlopen) -> dict:
    """Ищет сериал по названию и стране, возвращая JSON-совместимый словарь."""
    validation = validate_series_request(title, country)
    if validation["ok"] is False:
        return validation

    params = validation["data"]
    response = fetch_json(build_search_url(params["title"]), token=token, opener=opener)
    if response["ok"] is False:
        return response

    docs = get_docs(response["data"])
    if len(docs) == 0:
        return make_response(
            False,
            error="not_found",
            details="По внешнему API ничего не найдено.",
        )

    series = choose_series(docs, params["country"])
    if series is None:
        return make_response(
            False,
            error="country_not_found",
            details="Сериал найден, но подходящей страны в результатах нет.",
        )

    return make_response(True, data=extract_series_info(series))


def find_series_raw(title, country="Россия", token: str = TOKEN, opener=urlopen) -> dict:
    """Ищет сериал и возвращает полный JSON найденного объекта из списка API."""
    validation = validate_series_request(title, country)
    if validation["ok"] is False:
        return validation

    params = validation["data"]
    response = fetch_json(build_search_url(params["title"]), token=token, opener=opener)
    if response["ok"] is False:
        return response

    docs = get_docs(response["data"])
    if len(docs) == 0:
        return make_response(
            False,
            error="not_found",
            details="По внешнему API ничего не найдено.",
        )

    series = choose_series(docs, params["country"])
    if series is None:
        return make_response(
            False,
            error="country_not_found",
            details="Сериал найден в выдаче, но подходящей страны среди сериалов нет.",
        )

    return make_response(True, data=series)


def request_series_info(token: str = TOKEN, opener=urlopen) -> dict:
    """Запрашивает название сериала и страну, затем печатает результат API."""
    title = input("Название сериала >> ")
    country = input("Страна [Россия] >> ").strip()
    if country == "":
        country = "Россия"
    result = find_series(title, country, token=token, opener=opener)
    print_dict(result)
    return result

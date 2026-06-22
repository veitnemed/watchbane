"""Получает данные о сериале из внешнего API и возвращает единый JSON-словарь."""

import json
import os
import time
from datetime import datetime
from difflib import SequenceMatcher
from json import JSONDecodeError
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from config import constant


API_URL = os.getenv("KINOPOISK_API_URL", "https://api.kinopoisk.dev/v1.4")
TOKEN = os.getenv("KINOPOISK_API_KEY") or os.getenv("POISKKINO_API_KEY")
SECONDARY_TOKEN = (
    os.getenv("KINOPOISK_API_KEY_SECONDARY")
    or os.getenv("POISKKINO_API_KEY_SECONDARY")
)
DEFAULT_LIMIT = 10
SERIES_TYPES = {
    "tv-series",
    "series",
    "mini-series",
    "animated-series",
    "anime",
    "tv-show",
}
ANIMATED_SERIAL_TYPES = {
    "cartoon",
    "anime",
    "animated-series",
}
MOVIE_TYPES = {
    "movie",
    "film",
    "video",
    "short",
    "short-film",
    "music-video",
}
SERIES_TYPE_NUMBERS = {2, 3, 4, 5, 6}

if TOKEN is None:
    try:
        from apis.api_token import TOKEN
    except ImportError:
        try:
            from api_token import TOKEN
        except ImportError:
            TOKEN = None

if SECONDARY_TOKEN is None:
    try:
        from apis.api_token import TOKEN_SECONDARY as SECONDARY_TOKEN
    except ImportError:
        try:
            from api_token import TOKEN_SECONDARY as SECONDARY_TOKEN
        except ImportError:
            SECONDARY_TOKEN = None


def get_api_tokens(preferred_token: str = None) -> list:
    """Возвращает список API-ключей в порядке использования."""
    tokens = []
    for value in [preferred_token, SECONDARY_TOKEN]:
        if value is not None and value not in tokens:
            tokens.append(value)
    return tokens


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


def write_api_log(event: str, **fields) -> None:
    """Пишет строку лога API в JSONL-файл."""
    try:
        os.makedirs(constant.DATA_DIR, exist_ok=True)
        payload = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "event": event,
        }
        payload.update(fields)
        with open(constant.API_LOG_FILE, "a", encoding="utf-8") as file:
            file.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except OSError:
        pass


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


def build_discover_url(filters: dict, page: int = 1, limit: int = DEFAULT_LIMIT) -> str:
    """Собирает URL подбора сериалов по фильтрам."""
    params = {
        "page": page,
        "limit": limit,
        "sortField": "votes.kp",
        "sortType": "-1",
        "isSeries": "true",
    }

    min_year = filters.get("min_year")
    max_year = filters.get("max_year")
    if min_year is not None or max_year is not None:
        year_from = min_year if min_year is not None else 2000
        year_to = max_year if max_year is not None else constant.NOW_YEAR
        params["year"] = f"{year_from}-{year_to}"

    min_kp = filters.get("min_kp")
    if min_kp is not None:
        params["rating.kp"] = f"{min_kp}-10"

    min_imdb = filters.get("min_imdb")
    if min_imdb is not None:
        params["rating.imdb"] = f"{min_imdb}-10"

    min_kp_votes = filters.get("min_kp_votes")
    if min_kp_votes is not None:
        params["votes.kp"] = f"{min_kp_votes}-5000000"

    min_imdb_votes = filters.get("min_imdb_votes")
    if min_imdb_votes is not None:
        params["votes.imdb"] = f"{min_imdb_votes}-1000000"

    query = urlencode(params, doseq=True)
    return f"{API_URL}/movie?{query}"


def fetch_json(url: str, token: str, timeout: int = 20, opener=urlopen, retries: int = 2) -> dict:
    """Загружает JSON с обработкой сетевых ошибок и ошибок формата ответа."""
    tokens = get_api_tokens(token)
    if len(tokens) == 0:
        write_api_log("api_missing_token", url=url)
        return make_response(False, error="missing_token", details="Не задан KINOPOISK_API_KEY.")

    write_api_log("api_request_start", url=url, timeout=timeout, retries=retries)
    last_error = None
    raw = None
    total_attempts = len(tokens) * (retries + 1)
    global_attempt = 0

    for token_index, current_token in enumerate(tokens):
        for attempt in range(retries + 1):
            global_attempt += 1
            request = Request(url, headers={
                "X-API-KEY": current_token,
                "Accept": "application/json",
            })
            write_api_log(
                "api_request_attempt",
                url=url,
                attempt=global_attempt,
                total_attempts=total_attempts,
                token_index=token_index + 1,
                using_secondary=token_index > 0,
            )
            try:
                with opener(request, timeout=timeout) as response:
                    raw = response.read().decode("utf-8")
                write_api_log(
                    "api_request_success",
                    url=url,
                    attempt=global_attempt,
                    token_index=token_index + 1,
                    using_secondary=token_index > 0,
                    status=getattr(response, "status", None),
                    bytes=len(raw),
                )
                break
            except HTTPError as error:
                write_api_log(
                    "api_request_http_error",
                    url=url,
                    attempt=global_attempt,
                    token_index=token_index + 1,
                    using_secondary=token_index > 0,
                    code=error.code,
                    reason=str(getattr(error, "reason", "")),
                )
                if error.code == 403:
                    if attempt < retries:
                        time.sleep(3 + attempt * 3)
                        continue
                    if token_index + 1 < len(tokens):
                        write_api_log(
                            "api_switch_token_after_403",
                            url=url,
                            failed_token_index=token_index + 1,
                            next_token_index=token_index + 2,
                        )
                        break
                if error.code == 400:
                    write_api_log("api_bad_request_parameters", url=url)
                return make_response(False, error="http_error", details=f"HTTP {error.code}")
            except URLError as error:
                write_api_log(
                    "api_request_network_error",
                    url=url,
                    attempt=global_attempt,
                    token_index=token_index + 1,
                    using_secondary=token_index > 0,
                    reason=str(error.reason),
                )
                last_error = make_response(False, error="network_error", details=str(error.reason))
            except TimeoutError:
                write_api_log(
                    "api_request_timeout",
                    url=url,
                    attempt=global_attempt,
                    token_index=token_index + 1,
                    using_secondary=token_index > 0,
                )
                last_error = make_response(False, error="timeout", details="Внешний API не ответил вовремя.")
            except OSError as error:
                write_api_log(
                    "api_request_os_error",
                    url=url,
                    attempt=global_attempt,
                    token_index=token_index + 1,
                    using_secondary=token_index > 0,
                    reason=str(error),
                )
                last_error = make_response(False, error="network_error", details=str(error))

            if attempt < retries:
                time.sleep(1 + attempt)
        if raw is not None:
            break
    else:
        write_api_log(
            "api_request_failed",
            url=url,
            error=last_error["error"] if last_error else None,
            details=last_error["details"] if last_error else None,
        )
        return last_error

    try:
        data = json.loads(raw)
        write_api_log(
            "api_json_ok",
            url=url,
            docs_count=len(get_docs(data)) if isinstance(data, dict) else None,
        )
        return make_response(True, data=data)
    except JSONDecodeError:
        write_api_log("api_invalid_json", url=url)
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
    from candidates import kp_enrichment

    kp_countries = kp_enrichment.extract_kp_country_values(movie)
    return kp_enrichment.countries_match(country, kp_countries)


def _normalize_kp_type(value) -> str:
    text = normalize_text(value).casefold()
    text = text.replace("_", "-")
    while "  " in text:
        text = text.replace("  ", " ")
    return text.replace(" ", "-")


def _normalized_type_set(values: set[str]) -> set[str]:
    return {_normalize_kp_type(item) for item in values}


_NORMALIZED_SERIES_TYPES = _normalized_type_set(SERIES_TYPES)
_NORMALIZED_ANIMATED_SERIAL_TYPES = _normalized_type_set(ANIMATED_SERIAL_TYPES)
_NORMALIZED_MOVIE_TYPES = _normalized_type_set(MOVIE_TYPES)


def _truthy_flag(value) -> bool:
    if isinstance(value, bool):
        return value
    if value in (None, ""):
        return False
    return str(value).strip().casefold() in {"1", "true", "yes", "y", "да"}


def _positive_int(value) -> int | None:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _has_serial_length_markers(movie: dict) -> bool:
    if _truthy_flag(movie.get("isSeries")):
        return True
    seasons = movie.get("seasonsInfo")
    if isinstance(seasons, list) and len(seasons) > 0:
        return True
    if _positive_int(movie.get("seriesLength")) is not None:
        return True
    if _positive_int(movie.get("totalSeriesLength")) is not None:
        return True
    return False


def series_type_check(movie: dict) -> tuple[bool, str]:
    """Returns whether KP item is an allowed serial candidate and why."""
    if isinstance(movie, dict) is False:
        return False, "blocked_not_a_dict"

    kp_type = _normalize_kp_type(movie.get("type"))
    type_number = movie.get("typeNumber")
    has_serial_markers = _has_serial_length_markers(movie)

    if kp_type in _NORMALIZED_SERIES_TYPES:
        return True, f"allowed_type:{kp_type or 'empty'}"

    if kp_type == "" and has_serial_markers:
        return True, "allowed_empty_type_with_serial_markers"

    try:
        if int(type_number) in SERIES_TYPE_NUMBERS:
            return True, f"allowed_type_number:{int(type_number)}"
    except (TypeError, ValueError):
        pass

    if kp_type in _NORMALIZED_ANIMATED_SERIAL_TYPES and has_serial_markers:
        return True, f"allowed_animated_serial:{kp_type}"

    if has_serial_markers and kp_type not in _NORMALIZED_MOVIE_TYPES:
        return True, f"allowed_serial_markers:{kp_type or 'empty'}"

    if kp_type in _NORMALIZED_MOVIE_TYPES:
        return False, f"blocked_movie_type:{kp_type}"

    if kp_type == "cartoon" and has_serial_markers is False:
        return False, "blocked_cartoon_film"

    return False, f"blocked_type:{kp_type or 'empty'}"


def describe_kp_type_filter(movie: dict) -> dict:
    """Returns raw KP type fields and type-filter decision for debug JSON."""
    accepted, reason = series_type_check(movie)
    return {
        "title": movie.get("name") if isinstance(movie, dict) else None,
        "year": movie.get("year") if isinstance(movie, dict) else None,
        "type": movie.get("type") if isinstance(movie, dict) else None,
        "typeNumber": movie.get("typeNumber") if isinstance(movie, dict) else None,
        "isSeries": movie.get("isSeries") if isinstance(movie, dict) else None,
        "seriesLength": movie.get("seriesLength") if isinstance(movie, dict) else None,
        "totalSeriesLength": movie.get("totalSeriesLength") if isinstance(movie, dict) else None,
        "accepted_as_series": accepted,
        "type_filter_reason": reason,
    }


def is_series(movie: dict) -> bool:
    """Проверяет, похож ли найденный объект на сериал."""
    return series_type_check(movie)[0]


def choose_series(docs: list, country: str) -> dict:
    """Выбирает первый сериал из нужной страны."""
    for movie in docs:
        if isinstance(movie, dict) and is_series(movie) and movie_has_country(movie, country):
            return movie
    return None


def normalize_title_for_match(title: str) -> str:
    text = normalize_text(title).casefold()
    for char in [".", ",", "!", "?", ":", ";", "\"", "'", "`", "«", "»", "(", ")", "[", "]"]:
        text = text.replace(char, " ")
    return " ".join(text.split())


def movie_title_candidates(movie: dict) -> list:
    titles = []
    for key in ("name", "alternativeName", "enName"):
        value = normalize_text(movie.get(key))
        if value != "" and value not in titles:
            titles.append(value)
    return titles


def title_match_score(query_title: str, movie: dict) -> float:
    query = normalize_title_for_match(query_title)
    if query == "":
        return 0

    best = 0.0
    for title in movie_title_candidates(movie):
        candidate = normalize_title_for_match(title)
        if candidate == "":
            continue
        if candidate == query:
            best = max(best, 1.0)
        elif query in candidate or candidate in query:
            best = max(best, 0.9)
        else:
            best = max(best, SequenceMatcher(None, query, candidate).ratio())
    return best


def choose_best_series(docs: list, country: str = "", title: str = "", year=None) -> tuple[dict | None, str | None]:
    """Chooses the best API series result by country, title and year."""
    series_docs = [movie for movie in docs if isinstance(movie, dict) and is_series(movie)]
    if len(series_docs) == 0:
        return None, "not_found"

    country = normalize_text(country)
    if country != "":
        country_docs = [movie for movie in series_docs if movie_has_country(movie, country)]
        if len(country_docs) == 0:
            return None, "country_not_found"
    else:
        country_docs = series_docs

    expected_year = None
    try:
        expected_year = int(year) if year not in (None, "") else None
    except (TypeError, ValueError):
        expected_year = None

    def score(movie: dict) -> tuple:
        movie_year = movie.get("year")
        year_score = 0
        if expected_year is not None and movie_year is not None:
            try:
                year_delta = abs(int(movie_year) - expected_year)
                year_score = 2 if year_delta == 0 else 1 if year_delta <= 1 else 0
            except (TypeError, ValueError):
                year_score = 0
        return (
            title_match_score(title, movie),
            year_score,
            safe_nested(movie, "votes", "kp") or 0,
            safe_nested(movie, "rating", "kp") or 0,
        )

    return max(country_docs, key=score), None


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


def find_series(title, country, year=None, token: str = TOKEN, opener=urlopen) -> dict:
    """Ищет сериал по названию и стране, возвращая JSON-совместимый словарь."""
    validation = validate_series_request(title, country)
    if validation["ok"] is False:
        return validation

    title = validation["data"]["title"]
    country = validation["data"]["country"]
    url = build_search_url(title, limit=DEFAULT_LIMIT)
    response = fetch_json(url, token=token, opener=opener)
    if response["ok"] is False:
        return response
    docs = get_docs(response["data"])
    series_docs = [movie for movie in docs if isinstance(movie, dict) and is_series(movie)]
    if len(series_docs) == 0:
        return make_response(False, error="not_found", details="series_not_found")

    selected, reason = choose_best_series(series_docs, country=country, title=title, year=year)
    if selected is None:
        return make_response(False, error=reason, details=f"series_{reason}")
    return make_response(True, data=extract_series_info(selected))


def find_series_raw(title, country="Россия", year=None, token: str = TOKEN, opener=urlopen) -> dict:
    """Ищет сериал и возвращает полный JSON найденного объекта из списка API."""
    validation = validate_series_request(title, country)
    if validation["ok"] is False:
        return validation

    title = validation["data"]["title"]
    country = validation["data"]["country"]
    url = build_search_url(title, limit=DEFAULT_LIMIT)
    response = fetch_json(url, token=token, opener=opener)
    if response["ok"] is False:
        return response
    docs = get_docs(response["data"])
    series_docs = [movie for movie in docs if isinstance(movie, dict) and is_series(movie)]
    if len(series_docs) == 0:
        return make_response(False, error="not_found", details="series_not_found")

    selected, reason = choose_best_series(series_docs, country=country, title=title, year=year)
    if selected is None:
        return make_response(False, error=reason, details=f"series_{reason}")
    return make_response(True, data=selected)


def discover_series_by_filters(filters: dict, page: int = 1, limit: int = 50, token: str = TOKEN, opener=urlopen) -> dict:
    """Возвращает сериалы из общего каталога API по фильтрам."""
    country = normalize_text(filters.get("country") or "Россия")
    url = build_discover_url(filters, page=page, limit=limit)
    response = fetch_json(url, token=token, opener=opener)
    if response["ok"] is False:
        if response["error"] == "network_error":
            details = response["details"] or "network_error"
            return make_response(
                False,
                error="network_error",
                details=f"{details}. URL: {url}"
            )
        return response

    docs = get_docs(response["data"])
    series_docs = [
        movie for movie in docs
        if isinstance(movie, dict) and is_series(movie) and movie_has_country(movie, country)
    ]
    return make_response(True, data=series_docs)


def check_api_available(token: str = TOKEN, opener=urlopen) -> dict:
    """Проверяет базовую доступность API коротким запросом."""
    url = f"{API_URL}/movie/search?query=test&limit=1&page=1"
    response = fetch_json(url, token=token, opener=opener, timeout=10, retries=0)
    if response["ok"] is False:
        details = response["details"] or response["error"] or "unknown_error"
        return make_response(False, error=response["error"], details=f"{details}. URL: {url}")
    return make_response(True, data=True)


def request_series_info(token: str = TOKEN, opener=urlopen) -> dict:
    """Запрашивает название сериала и страну, затем печатает результат API."""
    title = input("Название сериала >> ")
    country = input("Страна [Россия] >> ").strip()
    if country == "":
        country = "Россия"
    result = find_series(title, country, token=token, opener=opener)
    print_dict(result)
    return result

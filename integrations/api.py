"""Получает данные из внешнего API и извлекает полезные поля."""

import json
import os
import re
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from config import tags_work
from data_work import storage


API_URL = "https://api.poiskkino.dev"
TOKEN = os.getenv("POISKKINO_API_KEY")

if TOKEN is None:
    try:
        from api_token import TOKEN
    except ImportError:
        TOKEN = None

SERIALS = storage.get_all_titles()
RUSSIAN_COUNTRY = "Россия"
PLATFORM_TAG_PREFIX = "is_"


TRANSLIT = {
    "а": "a",
    "б": "b",
    "в": "v",
    "г": "g",
    "д": "d",
    "е": "e",
    "ё": "e",
    "ж": "zh",
    "з": "z",
    "и": "i",
    "й": "y",
    "к": "k",
    "л": "l",
    "м": "m",
    "н": "n",
    "о": "o",
    "п": "p",
    "р": "r",
    "с": "s",
    "т": "t",
    "у": "u",
    "ф": "f",
    "х": "h",
    "ц": "ts",
    "ч": "ch",
    "ш": "sh",
    "щ": "sch",
    "ъ": "",
    "ы": "y",
    "ь": "",
    "э": "e",
    "ю": "yu",
    "я": "ya",
}


def api_request(path: str, params: dict = None) -> dict:
    """Выполняет запрос к API."""
    url = API_URL + path

    if params is not None:
        url += "?" + urlencode(params, doseq=True)

    request = Request(
        url,
        headers={"X-API-KEY": TOKEN}
    )

    with urlopen(request, timeout=20) as response:
        return json.load(response)


def unique_values(values: list) -> list:
    """Возвращает список без дублей с сохранением порядка."""
    result = []
    for value in values:
        if value is not None and value not in result:
            result.append(value)
    return result


def find_serial(title: str) -> dict:
    """Ищет сериал по названию."""
    data = api_request(
        path="/v1.4/movie/search",
        params={
            "query": title,
            "page": 1,
            "limit": 10
        }
    )

    movies = data.get("docs", [])
    title = title.strip().lower()

    for movie in movies:
        if movie.get("name", "").strip().lower() == title:
            return movie

    if len(movies) > 0:
        return movies[0]

    return None


def get_serial_info(movie_id: int) -> dict:
    """Загружает полную информацию о сериале."""
    return api_request(path=f"/v1.4/movie/{movie_id}")


def get_country_names(serial: dict) -> list:
    """Возвращает страны из API-ответа."""
    return get_names(serial, "countries")


def is_russian_serial(serial: dict) -> bool:
    """Проверяет, что сериал произведен в России."""
    return RUSSIAN_COUNTRY in get_country_names(serial)


def get_keywords(movie_id: int) -> list:
    """Загружает ключевые слова сериала."""
    data = api_request(
        path="/v1.4/keyword",
        params={
            "movies.id": movie_id,
            "page": 1,
            "limit": 250
        }
    )

    keywords = []
    for keyword in data.get("docs", []):
        title = keyword.get("title")
        if title is not None:
            keywords.append(title)

    return keywords


def get_genres(serial: dict) -> list:
    """Возвращает жанры сериала."""
    genres = []

    for genre in serial.get("genres", []):
        name = genre.get("name")
        if name is not None:
            genres.append(name)

    return genres


def get_names(serial: dict, field: str) -> list:
    """Возвращает имена из поля API-ответа."""
    names = []

    for obj in serial.get(field, []):
        name = obj.get("name")
        if name is not None:
            names.append(name)

    return names


def get_platform_names(serial: dict) -> list:
    """Возвращает площадки и дистрибьюторов сериала."""
    platforms = []
    networks = serial.get("networks") or {}

    for network in networks.get("items", []):
        name = network.get("name")
        if name is not None:
            platforms.append(str(name).strip())

    distributors = serial.get("distributors") or {}
    for name in distributors.values():
        if name is not None:
            platforms.append(str(name).strip())

    return unique_values([platform for platform in platforms if platform != ""])


def platform_to_tag(platform: str) -> str:
    """Преобразует название площадки в имя тега."""
    value = platform.strip().lower()
    value = "".join(TRANSLIT.get(char, char) for char in value)
    value = re.sub(r"[^a-z0-9]+", "_", value).strip("_")
    return PLATFORM_TAG_PREFIX + value


def make_platform_tag_settings(platform: str) -> dict:
    """Собирает описание тега площадки."""
    return {
        "label": f"Площадка: {platform}",
        "title": platform,
        "question": f"Сериал выходил на площадке {platform}?",
        "scale": [
            "Нет",
            "Да"
        ],
        "translation": platform_to_tag(platform)
    }


def sync_platform_tags_from_api() -> dict:
    """Добавляет теги площадок из API и проставляет их сериалам."""
    from config import constant

    data = storage.load_dataset()
    tags = tags_work.load_tags()
    weights = storage.load_weights()
    movie_platform_tags = {}
    platform_by_tag = {}
    errors = []

    for title in data.keys():
        try:
            movie = find_serial(title)
            if movie is None:
                errors.append(f"{title}: сериал не найден")
                continue

            serial = get_serial_info(movie["id"])
            if is_russian_serial(serial) is False:
                countries = ", ".join(get_country_names(serial)) or "нет данных"
                errors.append(f"{title}: найден не российский сериал ({countries})")
                continue

            platforms = get_platform_names(serial)
            if len(platforms) == 0:
                errors.append(f"{title}: площадки не найдены")
                continue

            movie_platform_tags[title] = []
            for platform in platforms:
                feature = platform_to_tag(platform)
                platform_by_tag[feature] = platform
                movie_platform_tags[title].append(feature)
        except Exception as error:
            errors.append(f"{title}: ошибка API: {error}")

    storage.create_backup()
    tags_work.backup_tag_files()

    for feature, platform in platform_by_tag.items():
        tags.setdefault(feature, make_platform_tag_settings(platform))
        weights.setdefault(feature, 0)

    platform_features = list(platform_by_tag.keys())
    for title, movie in data.items():
        movie_tags = movie.setdefault(constant.TAGS_VIBE_SECTION, {})
        for feature in platform_features:
            movie_tags[feature] = 0
        for feature in movie_platform_tags.get(title, []):
            movie_tags[feature] = 1

    tags_work.save_tags(tags)
    tags_work.save_json(constant.FILE_NAME, data)
    tags_work.save_json(constant.WEIGHTS_JSON, weights)
    tags_work.move_edit_files_to_backup()

    print(f"Обработано сериалов: {len(data)}")
    print(f"Добавлено/обновлено тегов площадок: {len(platform_by_tag)}")
    if len(errors) > 0:
        print("\nОшибки:")
        for error in errors:
            print("-", error)

    return {
        "movies_count": len(data),
        "platform_tags": platform_by_tag,
        "errors": errors
    }


def get_persons(serial: dict, profession: str, limit: int = 5) -> list:
    """Возвращает персон указанной профессии."""
    names = []

    for person in serial.get("persons", []):
        if person.get("profession") == profession:
            name = person.get("name") or person.get("enName")
            if name is not None and name not in names:
                names.append(name)

        if len(names) == limit:
            break

    return names


def get_seasons_count(serial: dict) -> int:
    """Возвращает количество сезонов."""
    seasons = serial.get("seasonsInfo", [])
    return len(seasons)


def get_rating(serial: dict, source: str):
    """Возвращает рейтинг из API-ответа."""
    return serial.get("rating", {}).get(source)


def get_votes(serial: dict, source: str):
    """Возвращает количество голосов из API-ответа."""
    return serial.get("votes", {}).get(source)


def get_description(serial: dict) -> str:
    """Возвращает описание сериала."""
    description = serial.get("description") or serial.get("shortDescription")
    if description is None or str(description).strip() == "":
        return "нет данных"
    return str(description).strip()


def show_serial_tags(title: str) -> None:
    """Показывает подсказки тегов по сериалу."""
    print("=" * 60)

    movie = find_serial(title)

    if movie is None:
        print("Название:", title)
        print("Год:", 0)
        print("Описание:", "сериал не найден")
        return

    serial = get_serial_info(movie["id"])

    print("Название:", serial.get("name") or title)
    print("Год:", serial.get("year") or 0)
    print("Описание:", get_description(serial))


def run_test() -> None:
    """Запускает ручную проверку API."""
    if TOKEN is None:
        print("Ошибка! Не задана переменная окружения POISKKINO_API_KEY")
        return

    for title in SERIALS:
        try:
            show_serial_tags(title)
        except Exception as error:
            print("Ошибка API:", error)


if __name__ == "__main__":
    run_test()

import json
import os
from urllib.parse import urlencode
from urllib.request import Request, urlopen


API_URL = "https://api.poiskkino.dev"
TOKEN = os.getenv("POISKKINO_API_KEY")

if TOKEN is None:
    try:
        from api_token import TOKEN
    except ImportError:
        TOKEN = None

SERIALS = [
    "Чужие деньги",
    "Триггер",
    "Аутсорс",
    "Чернобыль зона отчуждения",
    "Игра на выживание",
    "Хрустальный",
    "Слово пацана",
    "Фарма",
    "Химера",
    "Санкционер",
    "Открытый брак",
    "Калимба",
    "Урок",
    "Haappy End",
    "Индентификация",
    "Закон каменных джунглей"
]


def api_request(path: str, params: dict = None) -> dict:
    url = API_URL + path

    if params is not None:
        url += "?" + urlencode(params, doseq=True)

    request = Request(
        url,
        headers={"X-API-KEY": TOKEN}
    )

    with urlopen(request, timeout=20) as response:
        return json.load(response)


def find_serial(title: str) -> dict:
    data = api_request(
        path="/v1.4/movie/search",
        params={
            "query": title,
            "page": 1,
            "limit": 10
        }
    )

    movies = data.get("docs", [])

    for movie in movies:
        if movie.get("name", "").strip().lower() == title.strip().lower():
            return movie

    if len(movies) > 0:
        return movies[0]

    return None


def get_serial_info(movie_id: int) -> dict:
    return api_request(path=f"/v1.4/movie/{movie_id}")


def get_keywords(movie_id: int) -> list:
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
    genres = []

    for genre in serial.get("genres", []):
        name = genre.get("name")
        if name is not None:
            genres.append(name)

    return genres


def get_names(serial: dict, field: str) -> list:
    names = []

    for obj in serial.get(field, []):
        name = obj.get("name")
        if name is not None:
            names.append(name)

    return names


def get_persons(serial: dict, profession: str, limit: int = 5) -> list:
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
    seasons = serial.get("seasonsInfo", [])
    return len(seasons)


def get_rating(serial: dict, source: str):
    return serial.get("rating", {}).get(source)


def get_votes(serial: dict, source: str):
    return serial.get("votes", {}).get(source)


def show_list(title: str, values: list) -> None:
    print(title + ":", ", ".join(values) or "нет данных")


def show_serial_tags(title: str) -> None:
    print("=" * 60)
    print("Ищем:", title)

    movie = find_serial(title)

    if movie is None:
        print("Сериал не найден")
        return

    serial = get_serial_info(movie["id"])
    genres = get_genres(serial)
    countries = get_names(serial, "countries")
    keywords = get_keywords(serial["id"])
    directors = get_persons(serial, "режиссеры")
    actors = get_persons(serial, "актеры")

    print(f"Найдено: {serial.get('name')} ({serial.get('year')})")
    print("ID:", serial.get("id"))
    print("Тип:", serial.get("type"))
    show_list("Жанры", genres)
    show_list("Страны", countries)
    print("Рейтинг Kinopoisk:", get_rating(serial, "kp"))
    print("Голосов Kinopoisk:", get_votes(serial, "kp"))
    print("Рейтинг IMDb:", get_rating(serial, "imdb"))
    print("Голосов IMDb:", get_votes(serial, "imdb"))
    print("Возрастной рейтинг:", serial.get("ageRating"))
    print("Длительность серии:", serial.get("seriesLength"))
    print("Количество сезонов:", get_seasons_count(serial))
    print("Статус:", serial.get("status"))
    print("Входит в топ-10:", serial.get("top10"))
    print("Место в топ-250:", serial.get("top250"))
    show_list("Режиссеры", directors)
    show_list("Актеры", actors)
    print("Количество ключевых слов:", len(keywords))
    print("Ключевые слова:", ", ".join(keywords) or "нет данных")
    print("Краткое описание:", serial.get("shortDescription") or "нет данных")


def run_test() -> None:
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

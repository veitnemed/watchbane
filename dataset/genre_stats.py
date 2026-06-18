"""Собирает и печатает жанры текущего датасета через API."""

from collections import Counter

from data_work import storage
from apis import kp_api as api


def get_dataset_title(dataset_title: str, movie: dict) -> str:
    """Возвращает название сериала из записи датасета."""
    return str(movie.get("main_info", {}).get("title", dataset_title)).strip()


def extract_genres(movie_json: dict) -> list:
    """Достаёт список жанров из полного JSON API."""
    genres = []
    for item in movie_json.get("genres", []) or []:
        if isinstance(item, dict) and item.get("name"):
            genres.append(str(item["name"]).strip())
        elif isinstance(item, str):
            genres.append(item.strip())
    return [genre for genre in genres if genre != ""]


def count_genres_from_api(data: dict, country: str = "Россия") -> dict:
    """Обходит датасет, получает жанры из API и считает количество сериалов."""
    genre_counter = Counter()
    not_found = []
    without_genres = []
    errors = []

    for idx, (dataset_title, movie) in enumerate(data.items(), start=1):
        title = get_dataset_title(dataset_title, movie)
        print(f"{idx}/{len(data)}: {title}")

        result = api.find_series_raw(title, country)
        if result["ok"] is False:
            if result["error"] in {"not_found", "country_not_found"}:
                not_found.append(title)
            else:
                errors.append((title, result["error"], result["details"]))
            continue

        genres = extract_genres(result["data"])
        if len(genres) == 0:
            without_genres.append(title)
            continue

        for genre in genres:
            genre_counter[genre] += 1

    return {
        "genre_counter": genre_counter,
        "not_found": not_found,
        "without_genres": without_genres,
        "errors": errors,
    }


def print_genre_report(result: dict) -> None:
    """Печатает отчет по жанрам текущего датасета."""
    genre_counter = result["genre_counter"]

    print("\nЖАНРЫ")
    print("=" * 50)
    if len(genre_counter) == 0:
        print("Жанры не найдены.")
    else:
        for genre, count in genre_counter.most_common():
            print(f"{genre}: {count}")

    print("\nИТОГО")
    print("=" * 50)
    print(f"Жанров: {len(genre_counter)}")
    print(f"Не найдено в API: {len(result['not_found'])}")
    print(f"Без жанров в API: {len(result['without_genres'])}")
    print(f"Ошибок API: {len(result['errors'])}")

    if len(result["not_found"]) > 0:
        print("\nНе найдено:")
        for title in result["not_found"]:
            print(f"- {title}")

    if len(result["without_genres"]) > 0:
        print("\nБез жанров:")
        for title in result["without_genres"]:
            print(f"- {title}")

    if len(result["errors"]) > 0:
        print("\nОшибки API:")
        for title, error, details in result["errors"]:
            print(f"- {title}: {error} | {details}")


def show_dataset_genres(country: str = "Россия") -> None:
    """Показывает все жанры текущего датасета, загруженные из API."""
    data = storage.load_dataset()
    if len(data) == 0:
        print("Датасет пуст.")
        return

    result = count_genres_from_api(data, country)
    print_genre_report(result)

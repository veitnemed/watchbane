"""Загружает жанровую разметку из API с подтверждением для каждого объекта."""

from typing import Callable

from config import constant
from config import genre_tags
from config import scheme
from data_work import storage
from apis import kp_api as api

CONFIRM_YES = {"y", "yes", "да", "д", "1"}
CONFIRM_NO = {"n", "no", "нет", "н", "0"}


def get_title(dataset_title: str, movie: dict) -> str:
    """Возвращает название объекта из датасета."""
    return str(movie.get("main_info", {}).get("title", dataset_title)).strip()


def extract_genres(movie_json: dict) -> list:
    """Достает жанры из JSON ответа API."""
    genres = []
    for item in movie_json.get("genres", []) or []:
        if isinstance(item, dict) and item.get("name"):
            genres.append(str(item["name"]).strip().casefold())
        elif isinstance(item, str):
            genres.append(item.strip().casefold())
    return genres


def short_text(value, limit: int = 50) -> str:
    """Обрезает текст для короткого предпросмотра."""
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit] + "..."


def detect_genre_tags(movie_json: dict) -> list:
    """Преобразует жанры API в текущие теги проекта."""
    detected = []
    for genre in extract_genres(movie_json):
        tag = genre_tags.genre_to_feature_name(genre)
        if tag not in detected:
            detected.append(tag)
    return detected


def format_tag_list(tag_names: list) -> str:
    """Возвращает читаемую строку с названиями жанров."""
    if len(tag_names) == 0:
        return "нет"
    labels = genre_tags.get_genre_labels()
    formatted = []
    for tag in tag_names:
        if tag in labels:
            formatted.append(labels[tag])
        elif tag.startswith("genre_"):
            source = tag.removeprefix("genre_")
            formatted.append(genre_tags.make_label(source))
        else:
            formatted.append(tag)
    return ", ".join(formatted)


def ask_confirm(prompt: Callable[[str], str], text: str) -> bool:
    """Спрашивает подтверждение и повторяет запрос до корректного ответа."""
    while True:
        answer = prompt(text).strip().casefold()
        if answer in CONFIRM_YES:
            return True
        if answer in CONFIRM_NO:
            return False
        print("Введите yes/no или да/нет.")


def apply_genre_markup(country: str = "Россия", prompt: Callable[[str], str] = input) -> dict:
    """Загружает жанры для текущего датасета и сохраняет подтвержденные изменения."""
    data = storage.load_dataset()
    summary = {
        "total": len(data),
        "updated": 0,
        "skipped": 0,
        "not_found": [],
        "errors": [],
    }

    if len(data) == 0:
        print("Dataset пуст. Жанровая разметка не загружается.")
        return summary

    updated = False
    added_genre_names = set()
    for idx, (dataset_title, movie) in enumerate(data.items(), start=1):
        title = get_title(dataset_title, movie)
        result = api.find_series_raw(title, country)

        if result["ok"] is False:
            if result["error"] in {"not_found", "country_not_found"}:
                summary["not_found"].append(title)
            else:
                summary["errors"].append((title, result["error"], result["details"]))
            print(f"{idx}/{len(data)}: {title} - не найдено")
            continue

        detected_genres = extract_genres(result["data"])
        detected_tags = []
        for genre_name in detected_genres:
            feature = genre_tags.genre_to_feature_name(genre_name)
            if feature not in detected_tags:
                detected_tags.append(feature)
        print(f"{idx}/{len(data)}: {title}")
        print(f"Описание: {short_text(result['data'].get('description'), 50)}")
        print(f"Жанры из API: {format_tag_list(detected_tags)}")

        if len(detected_tags) == 0:
            summary["skipped"] += 1
            print("Подтверждать нечего: жанры из текущего набора не найдены.")
            continue

        confirmed = ask_confirm(prompt, "Подтвердить жанровую принадлежность? >> ")
        if confirmed is False:
            summary["skipped"] += 1
            continue

        for genre_name in detected_genres:
            added_genre_names.add(genre_name)

        movie_tags = dict(movie.get(scheme.GENRE, {}))
        for tag in detected_tags:
            movie_tags[tag] = 1

        movie[scheme.GENRE] = movie_tags
        summary["updated"] += 1
        updated = True

    if updated:
        genre_tags.ensure_genre_fields(list(added_genre_names))
        constant.refresh_dynamic_fields()

        storage.create_backup()
        storage.save_dataset(data)
        weights = storage.load_weights()
        for feature in constant.GENRE:
            weights.setdefault(feature, 0)
        storage.save_weights(weights)
        print("Жанровая разметка сохранена.")
    else:
        print("Подтвержденных изменений нет.")

    return summary

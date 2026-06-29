"""Собирает жанровые теги из API и размечает датасет без дубликатов."""

import datetime
import json
import os
import shutil
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config import constant
from storage import files as storage_files
from dataset import tags_work
from apis import kp_api as api
from model import model

NEW_TAGS = {
    "has_drama": {
        "label": "Драма",
        "title": "Драма",
        "question": "Есть ли у сериала жанр драма?",
        "scale": ["Нет", "Да"],
        "translation": "drama",
    },
    "has_crime": {
        "label": "Криминал",
        "title": "Криминал",
        "question": "Есть ли у сериала жанр криминал?",
        "scale": ["Нет", "Да"],
        "translation": "crime",
    },
    "has_thriller": {
        "label": "Триллер",
        "title": "Триллер",
        "question": "Есть ли у сериала жанр триллер?",
        "scale": ["Нет", "Да"],
        "translation": "thriller",
    },
    "has_comedy": {
        "label": "Комедия",
        "title": "Комедия",
        "question": "Есть ли у сериала жанр комедия?",
        "scale": ["Нет", "Да"],
        "translation": "comedy",
    },
    "has_detective": {
        "label": "Детектив",
        "title": "Детектив",
        "question": "Есть ли у сериала жанр детектив?",
        "scale": ["Нет", "Да"],
        "translation": "detective",
    },
}

GENRE_TO_TAG = {
    "драма": "has_drama",
    "криминал": "has_crime",
    "триллер": "has_thriller",
    "комедия": "has_comedy",
    "детектив": "has_detective",
}


def load_json(file_name: str) -> dict:
    """Загружает JSON."""
    with open(file_name, "r", encoding="utf-8-sig") as file:
        return json.load(file)


def save_json(file_name: str, data: dict) -> None:
    """Сохраняет JSON."""
    with open(file_name, "w", encoding="UTF-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=4)


def backup_file(file_name: str, backup_dir: str, suffix: str) -> str:
    """Копирует файл в backup-папку."""
    if os.path.exists(file_name) is False:
        return None

    os.makedirs(backup_dir, exist_ok=True)
    date_name = datetime.datetime.now().strftime("%d-%m-%Y %H-%M-%S-%f")
    backup_name = os.path.join(backup_dir, f"{date_name} {suffix}")
    shutil.copy(file_name, backup_name)
    return backup_name


def get_title(dataset_title: str, movie: dict) -> str:
    """Возвращает название сериала из датасета."""
    return str(movie.get("main_info", {}).get("title", dataset_title)).strip()


def get_genres(movie_json: dict) -> list:
    """Достает жанры из полного JSON API."""
    genres = []
    for item in movie_json.get("genres", []) or []:
        if isinstance(item, dict) and item.get("name"):
            genres.append(str(item["name"]).strip().casefold())
        elif isinstance(item, str):
            genres.append(item.strip().casefold())
    return genres


def collect_known_genre_tags(data: dict, country: str = "Россия") -> list:
    """Собирает уникальные жанровые теги в порядке NEW_TAGS."""
    detected = set()

    for dataset_title, movie in data.items():
        title = get_title(dataset_title, movie)
        result = api.find_series_raw(title, country)
        if result["ok"] is False:
            continue

        for genre in get_genres(result["data"]):
            tag = GENRE_TO_TAG.get(genre)
            if tag is not None:
                detected.add(tag)

    return [tag for tag in NEW_TAGS.keys() if tag in detected]


def build_tag_settings(tag_names: list) -> dict:
    """Собирает схему тегов только для найденных жанров."""
    return {tag: NEW_TAGS[tag] for tag in tag_names}


def build_movie_tags(movie: dict, tag_names: list) -> dict:
    """Собирает жанровые флаги для одного объекта по найденному каталогу."""
    return {
        tag: int(movie.get(constant.TAGS_VIBE_SECTION, {}).get(tag, 0))
        for tag in tag_names
    }


def run() -> None:
    """Размечает датасет по жанрам API и сохраняет уникальный каталог тегов."""
    data = load_json(constant.FILE_NAME)
    if len(data) == 0:
        print("Dataset пуст. Жанровые теги не создаются.")
        return

    new_tag_names = collect_known_genre_tags(data)
    if len(new_tag_names) == 0:
        print("В датасете не найдено поддерживаемых жанров.")
        return

    storage_files.create_backup()
    tags_work.backup_tag_files()

    weights = load_json(constant.WEIGHTS_JSON)
    old_tags = set(tags_work.load_tags().keys())

    not_found = []
    errors = []
    marked = {tag: 0 for tag in new_tag_names}

    for dataset_title, movie in data.items():
        title = get_title(dataset_title, movie)
        result = api.find_series_raw(title, "Россия")

        if result["ok"] is False:
            if result["error"] in {"not_found", "country_not_found"}:
                not_found.append(title)
            else:
                errors.append((title, result["error"], result["details"]))

            movie_tags = build_movie_tags(movie, new_tag_names)
            movie[constant.TAGS_VIBE_SECTION] = movie_tags
            for tag, value in movie_tags.items():
                marked[tag] += value
            continue

        movie_tags = {tag: 0 for tag in new_tag_names}
        for genre in get_genres(result["data"]):
            tag = GENRE_TO_TAG.get(genre)
            if tag is not None and tag in movie_tags:
                movie_tags[tag] = 1

        for tag, value in movie_tags.items():
            marked[tag] += value

        movie[constant.TAGS_VIBE_SECTION] = movie_tags

    save_json(tags_work.TAGS_JSON, build_tag_settings(new_tag_names))
    save_json(constant.FILE_NAME, data)

    for tag in old_tags:
        weights.pop(tag, None)
    for tag in new_tag_names:
        weights.pop(tag, None)
    weights = model.normalize_weights(weights)
    for tag in new_tag_names:
        weights[tag] = 0
    save_json(constant.WEIGHTS_JSON, weights)

    tags_work.move_edit_files_to_backup()

    print("\nГотово. Новые теги:")
    for tag in new_tag_names:
        print(f"{tag}: {marked[tag]}")

    print(f"\nНе найдено или не Россия: {len(not_found)}")
    for title in not_found:
        print(f"- {title}")

    print(f"\nОшибок API: {len(errors)}")
    for title, error, details in errors:
        print(f"- {title}: {error} / {details}")


if __name__ == "__main__":
    run()

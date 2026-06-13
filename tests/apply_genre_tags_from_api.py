"""Одноразово заменяет vibe-теги на жанровые и размечает датасет через API."""

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
from data_work import storage
from data_work import tags_work
from integrations import api
from model_work import model

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


def run() -> None:
    """Заменяет теги и размечает датасет по жанрам API."""
    storage.create_backup()
    tags_work.backup_tag_files()

    data = load_json(constant.FILE_NAME)
    weights = load_json(constant.WEIGHTS_JSON)
    old_tags = set(tags_work.load_tags().keys())
    new_tag_names = list(NEW_TAGS.keys())

    not_found = []
    errors = []
    marked = {tag: 0 for tag in new_tag_names}

    for idx, (dataset_title, movie) in enumerate(data.items(), start=1):
        title = get_title(dataset_title, movie)
        print(f"{idx}/{len(data)}: {title}")

        old_movie_tags = movie.get(constant.TAGS_VIBE_SECTION, {})
        movie_tags = {
            tag: int(old_movie_tags.get(tag, 0))
            for tag in new_tag_names
        }
        result = api.find_series_raw(title, "Россия")
        if result["ok"] is False:
            if result["error"] in {"not_found", "country_not_found"}:
                not_found.append(title)
            else:
                errors.append((title, result["error"], result["details"]))
            movie[constant.TAGS_VIBE_SECTION] = movie_tags
            for tag, value in movie_tags.items():
                marked[tag] += value
            continue

        movie_tags = {tag: 0 for tag in new_tag_names}
        for genre in get_genres(result["data"]):
            tag = GENRE_TO_TAG.get(genre)
            if tag is not None:
                movie_tags[tag] = 1

        for tag, value in movie_tags.items():
            marked[tag] += value

        movie[constant.TAGS_VIBE_SECTION] = movie_tags

    save_json(tags_work.TAGS_JSON, NEW_TAGS)
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

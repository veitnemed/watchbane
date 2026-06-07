"""Работает с тегами: читает, добавляет, удаляет и синхронизирует их."""

import json
import os
import re
import shutil
from datetime import datetime
from pathlib import Path

TAGS_JSON = str(Path(__file__).with_name("tags.json"))
DEFAULT_TAG = "tag0"


def load_tags() -> dict:
    """Загружает теги из JSON."""
    with open(TAGS_JSON, 'r', encoding='utf-8-sig') as file:
        return json.load(file)


def save_tags(tags: dict) -> None:
    """Сохраняет теги в JSON."""
    with open(TAGS_JSON, 'w', encoding='UTF-8') as file:
        json.dump(tags, file, ensure_ascii=False, indent=4)


def get_tag_fields() -> list:
    """Возвращает имена тегов."""
    return list(load_tags().keys())


def get_tag_rules() -> dict:
    """Возвращает правила ввода тегов."""
    rules = {}
    for feature, settings in load_tags().items():
        rules[feature] = {
            "title": settings["title"],
            "question": settings["question"],
            "scale": settings["scale"]
        }
    return rules


def get_tag_labels() -> dict:
    """Возвращает подписи тегов."""
    return {
        feature: settings["label"]
        for feature, settings in load_tags().items()
    }


def get_tag_translations() -> dict:
    """Возвращает переводы тегов."""
    return {
        feature: settings["translation"]
        for feature, settings in load_tags().items()
    }


def is_correct_tag_name(feature: str) -> bool:
    """Проверяет имя тега."""
    return re.fullmatch(r"[a-z][a-z0-9_]*", feature) is not None


def load_json(file_name: str) -> dict:
    """Загружает JSON-файл."""
    with open(file_name, 'r', encoding='utf-8-sig') as file:
        return json.load(file)


def save_json(file_name: str, data: dict) -> None:
    """Сохраняет JSON-файл."""
    with open(file_name, 'w', encoding='UTF-8') as file:
        json.dump(data, file, ensure_ascii=False, indent=4)


def move_edit_files_to_backup() -> None:
    """Переносит редактируемые файлы в backup."""
    from config import constant

    backup_dir = os.path.join(constant.DIR_TXT, "tags_backup")
    date_name = datetime.now().strftime('%d-%m-%Y %H-%M-%S-%f')

    for file_name in [constant.EDIT_EXCEL]:
        if os.path.exists(file_name):
            os.makedirs(backup_dir, exist_ok=True)
            new_name = date_name + " " + os.path.basename(file_name)
            try:
                shutil.move(file_name, os.path.join(backup_dir, new_name))
            except PermissionError:
                print(f'Не удалось переместить открытый файл: {file_name}')
                print('Закрой его перед следующим открытием датасета.')


def backup_tag_files() -> None:
    """Создает backup файлов тегов и весов."""
    from config import constant

    backup_dir = os.path.join(constant.DIR_TXT, "tags_backup")
    date_name = datetime.now().strftime('%d-%m-%Y %H-%M-%S-%f')
    os.makedirs(backup_dir, exist_ok=True)

    shutil.copy(TAGS_JSON, os.path.join(backup_dir, date_name + " tags.json"))
    shutil.copy(constant.WEIGHTS_JSON, os.path.join(backup_dir, date_name + " weights.json"))


def add_tag_to_data(feature: str) -> None:
    """Добавляет новый тег в данные и веса."""
    from config import constant

    dataset = load_json(constant.FILE_NAME)
    for movie in dataset.values():
        movie.setdefault(constant.TAGS_VIBE_SECTION, {})
        movie[constant.TAGS_VIBE_SECTION][feature] = 0
    save_json(constant.FILE_NAME, dataset)

    weights = load_json(constant.WEIGHTS_JSON)
    weights[feature] = 0
    save_json(constant.WEIGHTS_JSON, weights)


def delete_tag_from_data(feature: str) -> None:
    """Удаляет тег из данных и весов."""
    from config import constant
    from model_work import model

    dataset = load_json(constant.FILE_NAME)
    for movie in dataset.values():
        movie.setdefault(constant.TAGS_VIBE_SECTION, {})
        movie[constant.TAGS_VIBE_SECTION].pop(feature, None)
    save_json(constant.FILE_NAME, dataset)

    weights = load_json(constant.WEIGHTS_JSON)
    weights.pop(feature, None)
    weights = model.normalize_weights(weights)
    save_json(constant.WEIGHTS_JSON, weights)


def remove_default_tag_if_only_tag(tags: dict) -> dict:
    """Удаляет tag0 перед добавлением первого настоящего тега."""
    if list(tags.keys()) != [DEFAULT_TAG]:
        return tags

    delete_tag_from_data(DEFAULT_TAG)
    tags.pop(DEFAULT_TAG, None)
    save_tags(tags)
    return tags

def delete_all_tags() -> None:
    """Удаляет все теги и оставляет технический tag0."""
    from config import constant

    old_tags = load_tags()

    dataset = load_json(constant.FILE_NAME)
    for movie in dataset.values():
        movie[constant.TAGS_VIBE_SECTION] = {
            DEFAULT_TAG: 0
        }
    save_json(constant.FILE_NAME, dataset)

    weights = load_json(constant.WEIGHTS_JSON)
    for feature in old_tags.keys():
        weights.pop(feature, None)
    weights[DEFAULT_TAG] = 0
    save_json(constant.WEIGHTS_JSON, weights)

    tags = {
        DEFAULT_TAG: {
            "label": "Технический тег",
            "title": "Технический тег",
            "question": "Технический тег-заглушка?",
            "scale": [
                "Нет",
                "Да"
            ],
            "translation": DEFAULT_TAG
        }
    }
    save_tags(tags)


def show_tags() -> None:
    """Показывает список тегов."""
    tags = load_tags()
    print('\nТеги вайба:\n')
    for idx, (feature, settings) in enumerate(tags.items(), start=1):
        print(f'{idx}) {feature} | {settings["label"]}')


def request_new_tag() -> None:
    """Запрашивает и добавляет новый тег."""
    from data_work import storage

    tags = load_tags()

    feature = input('Название поля на английском, например imdb_drama >> ').strip()
    if is_correct_tag_name(feature) is False:
        print('Ошибка! Название должно начинаться с английской буквы и содержать только английские буквы, цифры и _.')
        return

    if feature in tags:
        print('Ошибка! Такой тег уже существует.')
        return

    settings = {}
    settings["label"] = input('Название для интерфейса >> ').strip()
    settings["title"] = input('Короткий заголовок >> ').strip()
    settings["question"] = input('Описание-вопрос >> ').strip()
    settings["scale"] = [
        input('Описание значения 0 >> ').strip(),
        input('Описание значения 1 >> ').strip()
    ]
    settings["translation"] = input('Перевод на английский >> ').strip()

    if any(value == "" for value in [
        settings["label"],
        settings["title"],
        settings["question"],
        settings["scale"][0],
        settings["scale"][1],
        settings["translation"]
    ]):
        print('Ошибка! Все поля должны быть заполнены.')
        return

    storage.create_backup()
    backup_tag_files()
    tags = remove_default_tag_if_only_tag(tags)
    add_tag_to_data(feature)
    tags[feature] = settings
    save_tags(tags)
    move_edit_files_to_backup()
    print(f'Тег добавлен: {feature}')
    print('Схема изменилась. Запусти программу снова.')
    raise SystemExit

def request_delete_all_tags() -> None:
    """Запрашивает подтверждение и оставляет только tag0."""
    from data_work import storage
    answer = input("\nУдалить все теги? Введите yes >> ").strip().lower()
    if answer != "yes":
        print('Удаление отменено.')
        return
    
    storage.create_backup()
    backup_tag_files()
    delete_all_tags()
    move_edit_files_to_backup()
    print("Все теги удалены. Оставлен технический tag0.")
    print('Схема изменилась. Запусти программу снова.')
    raise SystemExit

def request_delete_tag() -> None:
    """Запрашивает и удаляет тег."""
    from data_work import storage

    tags = load_tags()
    show_tags()

    idx_answer = input('\nВведи порядковый номер тега >> ').strip()
    if idx_answer.isdigit() is False:
        print('Ошибка! Нужно ввести номер тега.')
        return

    idx_del = int(idx_answer) - 1
    if idx_del < 0 or idx_del >= len(tags):
        print('Ошибка! Такой тег не найден.')
        return

    if len(tags) == 1:
        print('Ошибка! Нельзя удалить последний тег.')
        return

    feature = list(tags.keys())[idx_del]
    answer = input(f'Удалить тег {feature}? Введи yes >> ').strip().lower()
    if answer != "yes":
        print('Удаление отменено.')
        return

    storage.create_backup()
    backup_tag_files()
    delete_tag_from_data(feature)
    tags.pop(feature)
    save_tags(tags)
    move_edit_files_to_backup()
    print(f'Тег удален: {feature}')
    print('Схема изменилась. Запусти программу снова.')
    raise SystemExit

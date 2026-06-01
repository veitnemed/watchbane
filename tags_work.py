import json
import os
import re
import shutil
from datetime import datetime
from pathlib import Path


TAGS_JSON = str(Path(__file__).with_name("tags.json"))


def load_tags() -> dict:
    with open(TAGS_JSON, 'r', encoding='utf-8-sig') as file:
        return json.load(file)


def save_tags(tags: dict) -> None:
    with open(TAGS_JSON, 'w', encoding='UTF-8') as file:
        json.dump(tags, file, ensure_ascii=False, indent=4)


def get_tag_fields() -> list:
    return list(load_tags().keys())


def get_tag_rules() -> dict:
    rules = {}
    for feature, settings in load_tags().items():
        rules[feature] = {
            "title": settings["title"],
            "question": settings["question"],
            "scale": settings["scale"]
        }
    return rules


def get_tag_labels() -> dict:
    return {
        feature: settings["label"]
        for feature, settings in load_tags().items()
    }


def get_tag_translations() -> dict:
    return {
        feature: settings["translation"]
        for feature, settings in load_tags().items()
    }


def is_correct_tag_name(feature: str) -> bool:
    return re.fullmatch(r"[a-z][a-z0-9_]*", feature) is not None


def load_json(file_name: str) -> dict:
    with open(file_name, 'r', encoding='utf-8-sig') as file:
        return json.load(file)


def save_json(file_name: str, data: dict) -> None:
    with open(file_name, 'w', encoding='UTF-8') as file:
        json.dump(data, file, ensure_ascii=False, indent=4)


def move_edit_files_to_backup() -> None:
    import constant

    backup_dir = os.path.join(constant.DIR_TXT, "tags_backup")
    date_name = datetime.now().strftime('%d-%m-%Y %H-%M-%S-%f')

    for file_name in [constant.EDIT_EXCEL, constant.EDIT_CSV]:
        if os.path.exists(file_name):
            os.makedirs(backup_dir, exist_ok=True)
            new_name = date_name + " " + os.path.basename(file_name)
            try:
                shutil.move(file_name, os.path.join(backup_dir, new_name))
            except PermissionError:
                print(f'Не удалось переместить открытый файл: {file_name}')
                print('Закрой его перед следующим открытием датасета.')


def backup_tag_files() -> None:
    import constant

    backup_dir = os.path.join(constant.DIR_TXT, "tags_backup")
    date_name = datetime.now().strftime('%d-%m-%Y %H-%M-%S-%f')
    os.makedirs(backup_dir, exist_ok=True)

    shutil.copy(TAGS_JSON, os.path.join(backup_dir, date_name + " tags.json"))
    shutil.copy(constant.WEIGHTS_JSON, os.path.join(backup_dir, date_name + " weights.json"))


def add_tag_to_data(feature: str) -> None:
    import constant

    dataset = load_json(constant.FILE_NAME)
    for movie in dataset.values():
        movie.setdefault(constant.TAGS_VIBE_SECTION, {})
        movie[constant.TAGS_VIBE_SECTION][feature] = 0
    save_json(constant.FILE_NAME, dataset)

    weights = load_json(constant.WEIGHTS_JSON)
    weights[feature] = 0
    save_json(constant.WEIGHTS_JSON, weights)


def delete_tag_from_data(feature: str) -> None:
    import constant

    dataset = load_json(constant.FILE_NAME)
    for movie in dataset.values():
        movie.setdefault(constant.TAGS_VIBE_SECTION, {})
        movie[constant.TAGS_VIBE_SECTION].pop(feature, None)
    save_json(constant.FILE_NAME, dataset)

    weights = load_json(constant.WEIGHTS_JSON)
    weights.pop(feature, None)
    save_json(constant.WEIGHTS_JSON, weights)


def show_tags() -> None:
    tags = load_tags()
    print('\nТеги вайба:\n')
    for idx, (feature, settings) in enumerate(tags.items(), start=1):
        print(f'{idx}) {feature} | {settings["label"]}')


def request_new_tag() -> None:
    import storage

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
    add_tag_to_data(feature)
    tags[feature] = settings
    save_tags(tags)
    move_edit_files_to_backup()
    print(f'Тег добавлен: {feature}')
    print('Схема изменилась. Запусти программу снова.')
    raise SystemExit


def request_delete_tag() -> None:
    import storage

    tags = load_tags()
    show_tags()

    feature = input('\nНазвание поля для удаления >> ').strip()
    if feature not in tags:
        print('Ошибка! Такой тег не найден.')
        return

    if len(tags) == 1:
        print('Ошибка! Нельзя удалить последний тег.')
        return

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

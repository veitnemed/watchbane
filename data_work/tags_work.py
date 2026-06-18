"""Меняет пользовательские данные при работе с тегами: dataset, weights, backup.

Чистое чтение/валидация каталога тегов живёт в config.tags_work и ре-экспортируется
здесь для обратной совместимости старых импортов ``from data_work import tags_work``.
"""

import os
import shutil
from datetime import datetime

from config.tags_work import (
    TAGS_JSON,
    load_tags,
    save_tags,
    get_tag_fields,
    get_tag_rules,
    get_tag_labels,
    get_tag_translations,
    is_correct_tag_name,
    load_json,
    save_json,
    remove_default_tag_if_only_tag,
)


def move_edit_files_to_backup() -> None:
    """Переносит редактируемые файлы в backup после изменения схемы тегов."""
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
    """Добавляет новый тег в датасет и веса."""
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
    """Удаляет тег из датасета и весов."""
    from config import constant
    from model import model

    dataset = load_json(constant.FILE_NAME)
    for movie in dataset.values():
        movie.setdefault(constant.TAGS_VIBE_SECTION, {})
        movie[constant.TAGS_VIBE_SECTION].pop(feature, None)
    save_json(constant.FILE_NAME, dataset)

    weights = load_json(constant.WEIGHTS_JSON)
    weights.pop(feature, None)
    weights = model.normalize_weights(weights)
    save_json(constant.WEIGHTS_JSON, weights)


def delete_all_tags() -> None:
    """Удаляет все вайб-теги без технических заглушек."""
    from config import constant

    old_tags = load_tags()

    dataset = load_json(constant.FILE_NAME)
    for movie in dataset.values():
        movie[constant.TAGS_VIBE_SECTION] = {}
    save_json(constant.FILE_NAME, dataset)

    weights = load_json(constant.WEIGHTS_JSON)
    for feature in old_tags.keys():
        weights.pop(feature, None)
    save_json(constant.WEIGHTS_JSON, weights)
    save_tags({})

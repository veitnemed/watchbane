"""Vibe tag mutations on watched dataset records."""

from config.tags_work import load_json, load_tags, save_json, save_tags
from dataset.tags.backup import backup_tag_files, move_edit_files_to_backup


def add_tag_to_data(feature: str) -> None:
    """Добавляет новый тег в датасет."""
    from config import constant

    dataset = load_json(constant.FILE_NAME)
    for movie in dataset.values():
        movie.setdefault(constant.TAGS_VIBE_SECTION, {})
        movie[constant.TAGS_VIBE_SECTION][feature] = 0
    save_json(constant.FILE_NAME, dataset)


def delete_tag_from_data(feature: str) -> None:
    """Удаляет тег из датасета."""
    from config import constant

    dataset = load_json(constant.FILE_NAME)
    for movie in dataset.values():
        movie.setdefault(constant.TAGS_VIBE_SECTION, {})
        movie[constant.TAGS_VIBE_SECTION].pop(feature, None)
    save_json(constant.FILE_NAME, dataset)


def delete_all_tags() -> None:
    """Удаляет все вайб-теги без технических заглушек."""
    from config import constant

    dataset = load_json(constant.FILE_NAME)
    for movie in dataset.values():
        movie[constant.TAGS_VIBE_SECTION] = {}
    save_json(constant.FILE_NAME, dataset)

    save_tags({})


def add_tag(feature: str, settings: dict) -> None:
    """Полный сценарий добавления тега: backup, запись в данные, обновление каталога."""
    from storage import files as storage_files

    storage_files.create_backup()
    backup_tag_files()
    add_tag_to_data(feature)
    tags = load_tags()
    tags[feature] = settings
    save_tags(tags)
    move_edit_files_to_backup()


def delete_tag(feature: str) -> None:
    """Полный сценарий удаления одного тега: backup, чистка данных, обновление каталога."""
    from storage import files as storage_files

    storage_files.create_backup()
    backup_tag_files()
    delete_tag_from_data(feature)
    tags = load_tags()
    tags.pop(feature, None)
    save_tags(tags)
    move_edit_files_to_backup()

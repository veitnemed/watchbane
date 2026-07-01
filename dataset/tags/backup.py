"""Backup editable files after tag schema changes."""

import os
import shutil
from datetime import datetime

from config.tags_work import TAGS_JSON


def move_edit_files_to_backup() -> None:
    """Переносит редактируемые файлы в backup после изменения схемы тегов."""
    from config import constant

    backup_dir = os.path.join(constant.DIR_TXT, "tags_backup")
    date_name = datetime.now().strftime("%d-%m-%Y %H-%M-%S-%f")

    for file_name in [constant.EDIT_EXCEL]:
        if os.path.exists(file_name):
            os.makedirs(backup_dir, exist_ok=True)
            new_name = date_name + " " + os.path.basename(file_name)
            try:
                shutil.move(file_name, os.path.join(backup_dir, new_name))
            except PermissionError:
                print(f"Не удалось переместить открытый файл: {file_name}")
                print("Закрой его перед следующим открытием датасета.")


def backup_tag_files() -> None:
    """Создает backup файла тегов."""
    from config import constant

    backup_dir = os.path.join(constant.DIR_TXT, "tags_backup")
    date_name = datetime.now().strftime("%d-%m-%Y %H-%M-%S-%f")
    os.makedirs(backup_dir, exist_ok=True)

    shutil.copy(TAGS_JSON, os.path.join(backup_dir, date_name + " tags.json"))

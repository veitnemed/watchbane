"""Работает с файлами данных: доступ, открытие, backup и стартовая инициализация."""

import json
import os
from datetime import datetime
from pathlib import Path

from config import constant


def is_json_exists(file_name):
    """Проверяет существование JSON-файла."""
    return os.path.exists(file_name)


def open_file(file_name: str) -> None:
    """Открывает файл системной программой Windows."""
    os.startfile(file_name)


def is_file_writable(file_name: str) -> bool:
    """Проверяет, можно ли записывать в файл."""
    try:
        with open(file_name, 'a', encoding='UTF-8'):
            return True
    except PermissionError:
        return False


def dump_json_atomic(path: str | Path, payload: dict, *, trailing_newline: bool = False) -> None:
    """Write a JSON mapping through a same-directory temp file, then replace."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp_path = target.with_name(f"{target.name}.tmp")

    try:
        with temp_path.open("w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=4)
            if trailing_newline:
                file.write("\n")
        os.replace(temp_path, target)
    except Exception:
        try:
            temp_path.unlink()
        except OSError:
            pass
        raise


def create_backup():
    """Создает резервную копию датасета."""
    from storage.data import load_dataset

    dataset = load_dataset()
    date_name = datetime.now().strftime('%d-%m-%Y %H-%M-%S-%f')
    backup_file = constant.BACKUP_DIR + date_name + '.json'
    if is_json_exists(backup_file) is False:
        os.makedirs(constant.BACKUP_DIR, exist_ok=True)

    with open(backup_file, 'w', encoding='UTF-8') as file:
        json.dump(dataset, file, ensure_ascii=False, indent=4)


def get_latest_backups(limit: int = 10) -> list:
    """Возвращает последние backup-файлы датасета."""
    backup_dir = Path(constant.BACKUP_DIR)
    if backup_dir.exists() is False:
        return []

    files = [
        path for path in backup_dir.iterdir()
        if path.is_file() and path.suffix.lower() == ".json"
    ]
    files.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    return files[:limit]


def get_backup_label(file_path: Path) -> str:
    """Собирает короткую подпись backup-файла для меню."""
    size_kb = file_path.stat().st_size / 1024
    changed_at = datetime.fromtimestamp(file_path.stat().st_mtime).strftime("%d.%m.%Y %H:%M:%S")
    return f"{file_path.name} | {changed_at} | {size_kb:.1f} KB"


def restore_backup(file_path: Path) -> int:
    """Загружает выбранный backup в основной датасет и возвращает число записей."""
    from storage.data import save_dataset

    with open(file_path, 'r', encoding='utf-8-sig') as file:
        data = json.load(file)

    if isinstance(data, dict) is False:
        raise ValueError("Backup должен быть JSON-словарем.")

    create_backup()
    save_dataset(data)
    return len(data)


def init_all_dates():
    """Инициализирует все рабочие файлы данных."""
    from storage.runtime import ensure_runtime_data_layout

    ensure_runtime_data_layout(create_initial_backup=True)

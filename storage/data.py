"""Читает, сохраняет, создает и очищает dataset и meta."""

import json

from config import constant
from common import valid
from storage.backend import is_sqlite_backend
from storage.files import dump_json_atomic, is_json_exists
from storage.normalize import normalize_main_info, normalize_movie_tags, normalize_raw_scores


def init_dataset():
    """Создает файл датасета, если его нет."""
    if is_json_exists(constant.FILE_NAME) is False:
        dump_json_atomic(constant.FILE_NAME, {})


def load_dataset() -> dict:
    """Загружает датасет из JSON-файла."""
    if is_sqlite_backend():
        from storage.sqlite.watched_repository import load_dataset_dict

        return load_dataset_dict()

    init_dataset()
    with open(constant.FILE_NAME, 'r', encoding='utf-8-sig') as file:
        data = json.load(file)
    if isinstance(data, dict) is False:
        return {}
    normalized = {}
    for title, movie in data.items():
        if isinstance(movie, dict):
            normalized[title] = normalize_movie_tags(movie)
    return normalized


def save_dataset(data: dict):
    """Сохраняет датасет в JSON-файл."""
    if is_sqlite_backend():
        from storage.sqlite.watched_repository import save_dataset_dict

        save_dataset_dict(data)
        return

    normalized = {title: normalize_movie_tags(movie) for title, movie in data.items()}
    dump_json_atomic(constant.FILE_NAME, normalized)


def clean_dataset():
    """Очищает датасет."""
    if is_sqlite_backend():
        from storage.sqlite.watched_repository import save_dataset_dict

        save_dataset_dict({})
        return

    dump_json_atomic(constant.FILE_NAME, {})


def is_origin_title(new_title: str) -> bool:
    """Проверяет, что такого названия еще нет."""
    if is_sqlite_backend():
        from storage.sqlite.watched_repository import is_origin_title as sqlite_is_origin_title

        return sqlite_is_origin_title(new_title)

    data = load_dataset()

    for title in data.keys():
        if title.strip().lower() == new_title.strip().lower():
            return False
    return True


def get_all_titles() -> list:
    """Возвращает список всех названий в датасете."""
    return list(load_dataset().keys())


def find_exact_title(title: str) -> str | None:
    """Возвращает фактический ключ записи по названию без учета регистра."""
    if is_sqlite_backend():
        from storage.sqlite.watched_repository import find_exact_title as sqlite_find_exact_title

        return sqlite_find_exact_title(title)

    expected = str(title).strip().lower()
    for current_title in load_dataset().keys():
        if current_title.strip().lower() == expected:
            return current_title
    return None


def init_meta():
    """Создает файл meta, если его нет."""
    if is_json_exists(constant.META_JSON) is False:
        dump_json_atomic(constant.META_JSON, {})


def load_meta() -> dict:
    """Загружает meta из JSON-файла."""
    if is_sqlite_backend():
        from storage.sqlite.watched_repository import load_meta_dict

        return load_meta_dict()

    init_meta()
    with open(constant.META_JSON, 'r', encoding='utf-8-sig') as file:
        data = json.load(file)
    if isinstance(data, dict) is False:
        return {}
    return {
        title: meta_obj
        for title, meta_obj in data.items()
        if isinstance(meta_obj, dict)
    }


def save_meta(meta: dict):
    """Сохраняет meta в JSON-файл."""
    if is_sqlite_backend():
        from storage.sqlite.watched_repository import save_meta_dict

        save_meta_dict(meta)
        return

    dump_json_atomic(constant.META_JSON, meta)


def clean_meta():
    """Очищает meta."""
    if is_sqlite_backend():
        from storage.sqlite.watched_repository import save_meta_dict

        save_meta_dict({})
        return

    dump_json_atomic(constant.META_JSON, {})


def add_movies_to_meta(main_info: dict, raw: dict, extra_meta: dict | None = None, *, meta_key: str | None = None) -> bool:
    """Добавляет постоянные raw-данные фильма в meta."""
    title = str(main_info["title"]).strip()
    meta = load_meta()

    if valid.is_correct_title(title) is False:
        return False

    if valid.is_correct_score(str(main_info["user_score"])) is False:
        return False

    if valid.is_correct_year(str(main_info["year"])) is False:
        return False

    if valid.is_valid_raw_meta(raw) is False:
        return False

    meta_obj = {}
    meta_obj["main_info"] = normalize_main_info(main_info)
    meta_obj["raw_scores"] = normalize_raw_scores(raw)
    if isinstance(extra_meta, dict):
        for key, value in extra_meta.items():
            if key in {"main_info", "raw_scores"}:
                continue
            meta_obj[key] = value
    meta[meta_key or title] = meta_obj

    save_meta(meta)
    return True


def title_in_meta(title: str) -> bool:
    """Проверяет наличие названия в meta."""
    if is_sqlite_backend():
        return get_meta_obj(title) is not None

    title = title.strip()
    meta = load_meta()

    return any(meta_title.lower() == title.lower() for meta_title in meta.keys())


def get_meta_obj(title: str) -> dict:
    """Возвращает запись meta по названию."""
    if is_sqlite_backend():
        from storage.sqlite.watched_repository import get_meta_obj as sqlite_get_meta_obj

        return sqlite_get_meta_obj(title)

    title = title.strip()
    meta = load_meta()

    for meta_title, obj in meta.items():
        if meta_title.lower() == title.lower():
            return obj
    return None


def rename_movie_title(old_title: str, new_title: str) -> bool:
    """Безопасно переименовывает запись в dataset и meta."""
    if is_sqlite_backend():
        return _rename_movie_title_sqlite(old_title, new_title)

    old_exact = find_exact_title(old_title)
    if old_exact is None:
        return False

    new_title = str(new_title).strip()
    if valid.is_correct_title(new_title) is False:
        return False

    if old_exact.strip().lower() != new_title.lower() and is_origin_title(new_title) is False:
        return False

    dataset = load_dataset()
    movie = dataset.pop(old_exact)
    movie["main_info"] = normalize_main_info({
        **movie["main_info"],
        "title": new_title,
    })
    dataset[new_title] = movie
    save_dataset(dataset)

    meta = load_meta()
    old_meta_title = None
    for meta_title in meta.keys():
        if meta_title.strip().lower() == old_exact.strip().lower():
            old_meta_title = meta_title
            break

    if old_meta_title is not None:
        meta_obj = meta.pop(old_meta_title)
        meta_obj["main_info"] = normalize_main_info({
            **meta_obj["main_info"],
            "title": new_title,
        })
        meta[new_title] = meta_obj
        save_meta(meta)

    return True


def _rename_movie_title_sqlite(old_title: str, new_title: str) -> bool:
    from storage.sqlite.connection import connect
    from storage.sqlite.migrations import apply_migrations
    from storage.sqlite.watched_repository import (
        find_exact_title as sqlite_find_exact_title,
        is_origin_title as sqlite_is_origin_title,
        load_dataset_dict,
        load_meta_dict,
        save_dataset_dict,
        save_meta_dict,
    )

    conn = connect()
    try:
        apply_migrations(conn)
        with conn:
            old_exact = sqlite_find_exact_title(old_title, conn=conn)
            if old_exact is None:
                return False

            new_title = str(new_title).strip()
            if valid.is_correct_title(new_title) is False:
                return False

            if old_exact.strip().lower() != new_title.lower() and sqlite_is_origin_title(new_title, conn=conn) is False:
                return False

            dataset = load_dataset_dict(conn=conn)
            movie = dataset.pop(old_exact)
            movie["main_info"] = normalize_main_info({
                **movie["main_info"],
                "title": new_title,
            })
            dataset[new_title] = movie

            meta = load_meta_dict(conn=conn)
            old_meta_title = None
            for meta_title in meta.keys():
                if meta_title.strip().lower() == old_exact.strip().lower():
                    old_meta_title = meta_title
                    break

            if old_meta_title is not None:
                meta_obj = meta.pop(old_meta_title)
                meta_obj["main_info"] = normalize_main_info({
                    **meta_obj["main_info"],
                    "title": new_title,
                })
                meta[new_title] = meta_obj

            save_dataset_dict(dataset, conn=conn)
            save_meta_dict(meta, conn=conn)
            return True
    finally:
        conn.close()



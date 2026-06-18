"""Читает, сохраняет, создает и очищает dataset, meta и weights."""

import json
import os

from config import constant
from config import genre_tags
from common import valid
from data_work.storage_files import is_json_exists
from data_work.storage_normalize import LEGACY_TAG_FIELDS, normalize_main_info, normalize_movie_tags, normalize_raw_scores


def init_dataset():
    """Создает файл датасета, если его нет."""
    if is_json_exists(constant.FILE_NAME) is False:
        os.makedirs(constant.DATA_DIR, exist_ok=True)
        with open(constant.FILE_NAME, 'w', encoding='UTF-8') as file:
            json.dump({}, file, ensure_ascii=False, indent=4)


def load_dataset() -> dict:
    """Загружает датасет из JSON-файла."""
    with open(constant.FILE_NAME, 'r', encoding='utf-8-sig') as file:
        data = json.load(file)
    for movie in data.values():
        normalize_movie_tags(movie)
    return data


def save_dataset(data: dict):
    """Сохраняет датасет в JSON-файл."""
    with open(constant.FILE_NAME, 'w', encoding='UTF-8') as file:
        normalized = {title: normalize_movie_tags(movie) for title, movie in data.items()}
        json.dump(normalized, file, ensure_ascii=False, indent=4)


def clean_dataset():
    """Очищает датасет."""
    with open(constant.FILE_NAME, 'w', encoding='UTF-8') as file:
        json.dump({}, file, ensure_ascii=False, indent=4)


def is_origin_title(new_title: str) -> bool:
    """Проверяет, что такого названия еще нет."""
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
    expected = str(title).strip().lower()
    for current_title in load_dataset().keys():
        if current_title.strip().lower() == expected:
            return current_title
    return None


def init_meta():
    """Создает файл meta, если его нет."""
    if is_json_exists(constant.META_JSON) is False:
        os.makedirs(constant.DIR_META, exist_ok=True)
        with open(constant.META_JSON, 'w', encoding='UTF-8') as file:
            json.dump({}, file, ensure_ascii=False, indent=4)


def load_meta() -> dict:
    """Загружает meta из JSON-файла."""
    with open(constant.META_JSON, 'r', encoding='utf-8-sig') as file:
        return json.load(file)


def save_meta(meta: dict):
    """Сохраняет meta в JSON-файл."""
    with open(constant.META_JSON, 'w', encoding='UTF-8') as file:
        json.dump(meta, file, ensure_ascii=False, indent=4)


def clean_meta():
    """Очищает meta."""
    with open(constant.META_JSON, 'w', encoding='UTF-8') as file:
        json.dump({}, file, ensure_ascii=False, indent=4)


def add_movies_to_meta(main_info: dict, raw: dict, extra_meta: dict | None = None) -> bool:
    """Добавляет постоянные raw-данные фильма в meta."""
    title = str(main_info["title"]).strip()
    meta = load_meta()

    if valid.is_correct_title(title) is False:
        print('Ошибка добавления в meta! Некорректное название')
        return False

    if valid.is_correct_score(str(main_info["user_score"])) is False:
        print('Ошибка добавления в meta! Некорректное значение user_score')
        return False

    if valid.is_correct_year(str(main_info["year"])) is False:
        print('Ошибка добавления в meta! Некорректный год')
        return False

    if valid.is_valid_raw_meta(raw) is False:
        print('Ошибка добавления в meta! Некорректные raw-данные')
        return False

    meta_obj = {}
    meta_obj["main_info"] = normalize_main_info(main_info)
    meta_obj["raw_scores"] = normalize_raw_scores(raw)
    if isinstance(extra_meta, dict):
        for key, value in extra_meta.items():
            if key in {"main_info", "raw_scores"}:
                continue
            meta_obj[key] = value
    meta[title] = meta_obj

    save_meta(meta)
    return True


def title_in_meta(title: str) -> bool:
    """Проверяет наличие названия в meta."""
    title = title.strip()
    meta = load_meta()

    return any(meta_title.lower() == title.lower() for meta_title in meta.keys())


def get_meta_obj(title: str) -> dict:
    """Возвращает запись meta по названию."""
    title = title.strip()
    meta = load_meta()

    for meta_title, obj in meta.items():
        if meta_title.lower() == title.lower():
            return obj
    return None


def rename_movie_title(old_title: str, new_title: str) -> bool:
    """Безопасно переименовывает запись в dataset и meta."""
    old_exact = find_exact_title(old_title)
    if old_exact is None:
        print("Ошибка переименования! Старая запись не найдена")
        return False

    new_title = str(new_title).strip()
    if valid.is_correct_title(new_title) is False:
        print("Ошибка переименования! Некорректное новое название")
        return False

    if old_exact.strip().lower() != new_title.lower() and is_origin_title(new_title) is False:
        print("Ошибка переименования! Такое название уже существует")
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


def init_weights():
    """Создает файл весов, если его нет."""
    if is_json_exists(constant.WEIGHTS_JSON) is False:
        with open(constant.WEIGHTS_JSON, 'w', encoding='UTF-8') as file:
            json.dump(constant.DEFAULT_WEIGHTS, file, ensure_ascii=False, indent=4)


def load_weights() -> dict:
    """Загружает веса модели."""
    with open(constant.WEIGHTS_JSON, 'r', encoding='utf-8-sig') as file:
        weights = json.load(file)
    normalized = {}
    for feature in constant.FEATURES:
        normalized[feature] = weights.get(feature, constant.DEFAULT_WEIGHTS[feature])
        for old_feature, active_feature in LEGACY_TAG_FIELDS.items():
            if active_feature == feature and old_feature in weights and feature not in weights:
                normalized[feature] = weights[old_feature]
                break
        legacy_genre_feature = next(
            (old_feature for old_feature, active_feature in genre_tags.get_legacy_feature_map().items() if active_feature == feature),
            None
        )
        if legacy_genre_feature is not None and legacy_genre_feature in weights and feature not in weights:
            normalized[feature] = weights[legacy_genre_feature]
    return normalized


def save_weights(data: dict):
    """Сохраняет веса модели."""
    with open(constant.WEIGHTS_JSON, 'w', encoding='UTF-8') as file:
        normalized = {feature: data.get(feature, constant.DEFAULT_WEIGHTS[feature]) for feature in constant.FEATURES}
        json.dump(normalized, file, ensure_ascii=False, indent=4)


def uppdate_weights(weights: dict):
    """Перезаписывает веса модели."""
    save_weights(weights)


def init_model_metrics() -> None:
    """Создает файл метрик модели, если его нет."""
    if is_json_exists(constant.MODEL_METRICS_JSON) is False:
        os.makedirs(os.path.dirname(constant.MODEL_METRICS_JSON), exist_ok=True)
        save_model_metrics({"loo_mae": None})


def load_model_metrics() -> dict:
    """Загружает сохраненные метрики модели."""
    init_model_metrics()
    with open(constant.MODEL_METRICS_JSON, 'r', encoding='utf-8-sig') as file:
        metrics = json.load(file)

    if isinstance(metrics, dict) is False:
        metrics = {}

    if "loo_mae" not in metrics:
        metrics["loo_mae"] = None
        save_model_metrics(metrics)

    return metrics


def save_model_metrics(metrics: dict) -> None:
    """Сохраняет метрики модели в JSON-файл."""
    os.makedirs(os.path.dirname(constant.MODEL_METRICS_JSON), exist_ok=True)
    with open(constant.MODEL_METRICS_JSON, 'w', encoding='UTF-8') as file:
        normalized = dict(metrics) if isinstance(metrics, dict) else {}
        normalized["loo_mae"] = None if normalized.get("loo_mae") is None else float(normalized["loo_mae"])
        json.dump(normalized, file, ensure_ascii=False, indent=4)


def get_saved_loo_mae() -> float | None:
    """Возвращает сохраненное значение leave-one-out MAE."""
    value = load_model_metrics().get("loo_mae")
    if value is None:
        return None
    return float(value)


def set_saved_loo_mae(value: float | None) -> None:
    """Сохраняет текущее значение leave-one-out MAE."""
    metrics = load_model_metrics()
    metrics["loo_mae"] = None if value is None else float(value)
    save_model_metrics(metrics)

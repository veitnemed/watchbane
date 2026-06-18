"""Читает и валидирует каталог тегов config/tags.json без изменения пользовательских данных."""

import json
import re
from pathlib import Path

TAGS_JSON = str(Path(__file__).resolve().parent / "tags.json")

__all__ = [
    "TAGS_JSON",
    "load_tags",
    "save_tags",
    "get_tag_fields",
    "get_tag_rules",
    "get_tag_labels",
    "get_tag_translations",
    "is_correct_tag_name",
    "load_json",
    "save_json",
    "remove_default_tag_if_only_tag",
]


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


def remove_default_tag_if_only_tag(tags: dict) -> dict:
    """Оставлено для совместимости со старым кодом."""
    return tags

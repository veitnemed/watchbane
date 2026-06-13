"""Читает оценки из TST JSON и переносит их в существующий датасет."""

import json

from config import constant
from core import valid
from data_work.storage_data import load_dataset, save_dataset
from data_work.storage_files import create_backup


def normalize_title(title: str) -> str:
    """Приводит название к виду для сравнения."""
    return str(title).strip().lower()


def load_tst_scores(file_name: str = None) -> dict:
    """Загружает словарь оценок TST из JSON-файла."""
    if file_name is None:
        file_name = constant.TST_SCORES_JSON

    with open(file_name, "r", encoding="utf-8-sig") as file:
        scores = json.load(file)

    if isinstance(scores, dict) is False:
        raise ValueError("TST-файл должен быть словарем вида название: оценка.")

    return scores


def apply_tst_scores(file_name: str = None) -> dict:
    """Обновляет оценки в датасете по совпавшим названиям из TST."""
    tst_scores = load_tst_scores(file_name)
    data = load_dataset()
    title_index = {}

    for dataset_title, movie in data.items():
        title = movie.get("main_info", {}).get("title", dataset_title)
        title_index[normalize_title(title)] = dataset_title

    result = {
        "total": len(tst_scores),
        "updated": 0,
        "unchanged": 0,
        "not_found": [],
        "invalid": []
    }

    for title, score in tst_scores.items():
        title_text = str(title).strip()
        if valid.is_correct_score(str(score)) is False:
            result["invalid"].append(title_text)
            continue

        dataset_title = title_index.get(normalize_title(title_text))
        if dataset_title is None:
            result["not_found"].append(title_text)
            continue

        new_score = valid.parse_float(score)
        main_info = data[dataset_title]["main_info"]
        if float(main_info["user_score"]) == new_score:
            result["unchanged"] += 1
        else:
            main_info["user_score"] = new_score
            result["updated"] += 1

    if result["updated"] > 0:
        create_backup()
        save_dataset(data)

    return result

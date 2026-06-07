"""Хранит общие функции меню и параметры обучения."""

import os
from datetime import datetime

from config import constant
from config import tags_work
from model_work import model
from interface import request
from data_work import storage
from core import valid

TRAIN_STEP = constant.STEP
TRAIN_PLATEAU_SCORE = 500
REPORTS_DIR_NAME = "reports"


def press_enter():
    """Ждет нажатия Enter."""
    input('Enter, чтобы продолжить >>')

def get_one_dict(obj: dict):
    result = {}
    dict_list = list(obj.values())
    for d in dict_list:
        result.update(d)
    return result


def get_stat_params_data():
    """Возвращает статистику числовых параметров датасета."""
    data = storage.load_dataset()
    return get_dataset_stats(data)


def collect_dataset_values(data: dict) -> dict:
    """Собирает числовые значения параметров из датасета."""
    values = {}
    for movie in data.values():
        sections = [
            movie.get("main_info", {}),
            movie.get("raw_scores", {}),
            movie.get("computed_scores", {}),
            movie.get(constant.TAGS_VIBE_SECTION, {})
        ]
        for section in sections:
            for feature, value in section.items():
                if feature == "title" or isinstance(value, bool):
                    continue
                if isinstance(value, (int, float)):
                    values.setdefault(feature, []).append(value)
    return values


def get_dataset_stats(data: dict) -> dict:
    """Считает минимум, максимум и среднее по параметрам датасета."""
    stats = {}
    for feature, values in collect_dataset_values(data).items():
        if len(values) == 0:
            continue
        stats[feature] = {
            "min": min(values),
            "max": max(values),
            "avg": sum(values) / len(values)
        }
    return stats


def build_dataset_info_lines(data: dict) -> list:
    """Собирает строки с информацией о датасете."""
    stats = get_dataset_stats(data)
    lines = []
    lines.append("Данные о датасете")
    lines.append("-" * 60)
    lines.append(f"Количество сериалов: {len(data)}")

    if len(stats) == 0:
        lines.append("Числовых параметров нет.")
        return lines

    ordered_features = []
    fields_order = constant.MAIN_INFO + constant.RAW_SCORES + constant.COMPUTED_SCORES + constant.TAGS_VIBE
    for feature in fields_order:
        if feature in stats and feature not in ordered_features:
            ordered_features.append(feature)
    for feature in stats.keys():
        if feature not in ordered_features:
            ordered_features.append(feature)

    for feature in ordered_features:
        item = stats[feature]
        label = get_feature_label(feature)
        lines.append("")
        lines.append(f"{feature} - {label}")
        lines.append(f"  min: {item['min']:.2f}")
        lines.append(f"  max: {item['max']:.2f}")
        lines.append(f"  avg: {item['avg']:.2f}")

    return lines


def get_menu_state():
    """Собирает состояние для меню."""
    data = storage.load_dataset()
    weights = storage.load_weights()
    movies_counter = len(data)
    abs_error = model.mean_absolute_error(data, weights)
    return data, weights, movies_counter, abs_error


def get_feature_label(feature: str) -> str:
    """Возвращает понятное название признака для отчета."""
    return constant.FIELD_LABELS.get(feature, feature)


def get_tag_usage(data: dict) -> dict:
    """Считает, сколько сериалов используют каждый тег."""
    usage = {feature: 0 for feature in constant.TAGS_VIBE}
    for movie in data.values():
        tags_vibe = movie.get(constant.TAGS_VIBE_SECTION, {})
        for feature in constant.TAGS_VIBE:
            if tags_vibe.get(feature, 0) > 0:
                usage[feature] += 1
    return usage


def get_error_rows(data: dict, weights: dict, limit: int = 10) -> list:
    """Возвращает строки с самыми большими ошибками модели."""
    rows = []
    for movie in model.iter_movies(data):
        features = model.get_features(movie)
        prediction = model.predict_score(features, weights)
        user_score = model.get_user_score(movie)
        error = prediction - user_score
        impacts = []
        for feature, weight in weights.items():
            impact = features[feature] * weight
            impacts.append((impact, feature))
        rows.append({
            "title": model.get_movie_title(movie),
            "user_score": user_score,
            "prediction": prediction,
            "error": error,
            "abs_error": abs(error),
            "top_impacts": sorted(impacts, key=lambda item: abs(item[0]), reverse=True)[:3]
        })
    return sorted(rows, key=lambda row: row["abs_error"], reverse=True)[:limit]


def build_train_report(data: dict, weights: dict) -> list:
    """Собирает строки текстового отчета об обучении."""
    movies_counter = len(data)
    mae = model.mean_absolute_error(data, weights)
    kp_mae = model.kp_mean_absolute_error(data)
    mean_error = model.mean_error(data, weights)
    tag_usage = get_tag_usage(data)
    tags = tags_work.load_tags()

    lines = []
    lines.append("ОТЧЕТ ОБ ОБУЧЕНИИ")
    lines.append("=" * 60)
    lines.append(f"Дата: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")
    lines.append(f"Количество сериалов: {movies_counter}")
    lines.append(f"MAE модели: {mae:.4f} ({mae * 10:.2f}%)")
    lines.append(f"KP_MAE: {kp_mae:.4f} ({kp_mae * 10:.2f}%)")
    lines.append(f"Среднее отклонение модели: {mean_error:.4f}")
    lines.append("")
    lines.append("Параметры обучения")
    lines.append("-" * 60)
    lines.append(f"Шаг обучения: {TRAIN_STEP}")
    lines.append(f"Плато: {TRAIN_PLATEAU_SCORE} попыток без улучшения")
    lines.append("")
    lines.extend(build_dataset_info_lines(data))
    lines.append("")
    lines.append("Веса модели")
    lines.append("-" * 60)
    for feature, weight in sorted(weights.items(), key=lambda item: abs(item[1]), reverse=True):
        lines.append(f"{feature} | {get_feature_label(feature)}: {weight:.4f}")

    lines.append("")
    lines.append("Теги")
    lines.append("-" * 60)
    for feature in constant.TAGS_VIBE:
        settings = tags.get(feature, {})
        label = settings.get("label", get_feature_label(feature))
        weight = weights.get(feature, 0)
        used_count = tag_usage.get(feature, 0)
        lines.append(f"{feature} | {label}: используется {used_count}/{movies_counter}, вес {weight:.4f}")

    lines.append("")
    lines.append("Самые большие ошибки модели")
    lines.append("-" * 60)
    for idx, row in enumerate(get_error_rows(data, weights), start=1):
        lines.append(
            f"{idx}. {row['title']} | "
            f"моя оценка: {row['user_score']:.2f}, "
            f"модель: {row['prediction']:.2f}, "
            f"ошибка: {row['error']:+.2f}"
        )
        impact_text = []
        for impact, feature in row["top_impacts"]:
            impact_text.append(f"{feature}: {impact:+.2f}")
        lines.append(f"   Топ-3 вклада: {', '.join(impact_text)}")

    return lines


def export_train_report() -> str:
    """Выгружает отчет об обучении в TXT-файл."""
    data = storage.load_dataset()
    weights = storage.load_weights()
    reports_dir = os.path.join(constant.DIR_TXT, REPORTS_DIR_NAME)
    os.makedirs(reports_dir, exist_ok=True)

    file_name = "train_report_" + datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + ".txt"
    file_path = os.path.join(reports_dir, file_name)

    with open(file_path, "w", encoding="UTF-8") as file:
        file.write("\n".join(build_train_report(data, weights)))

    print(f"Отчет сохранен: {file_path}")
    return file_path


def setup_train_params():
    """Настраивает параметры обучения."""
    global TRAIN_STEP, TRAIN_PLATEAU_SCORE

    step = request.loop_input(
        text=f'Шаг обучения [{TRAIN_STEP}] >> ',
        funcs_list=[valid.is_correct_train_step]
    )
    plateau_score = request.loop_input(
        text=f'Попыток без улучшения для плато [{TRAIN_PLATEAU_SCORE}] >> ',
        funcs_list=[valid.is_correct_plateau_score]
    )

    if step.strip() != "":
        TRAIN_STEP = valid.parse_float(step)
    if plateau_score.strip() != "":
        TRAIN_PLATEAU_SCORE = int(plateau_score)
    print(f'Параметры обучения обновлены: шаг={TRAIN_STEP}, плато={TRAIN_PLATEAU_SCORE}')

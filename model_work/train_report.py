"""Собирает и сохраняет текстовый отчет о качестве обучения модели."""

import os
from datetime import datetime

from config import constant
from data_work import dataset_stats
from data_work import storage
from data_work import tags_work
from model_work import model

REPORTS_DIR_NAME = "reports"


def get_tag_usage(data: dict) -> dict:
    """Считает, сколько сериалов использует каждый тег."""
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


def build_train_report(data: dict, weights: dict, train_step: float, plateau_score: int) -> list:
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
    lines.append(f"Шаг обучения: {train_step}")
    lines.append(f"Плато: {plateau_score} попыток без улучшения")
    lines.append("")
    lines.extend(dataset_stats.build_dataset_info_lines(data))
    lines.append("")
    lines.append("Веса модели")
    lines.append("-" * 60)
    for feature, weight in sorted(weights.items(), key=lambda item: abs(item[1]), reverse=True):
        label = dataset_stats.get_feature_label(feature)
        lines.append(f"{feature} | {label}: {weight:.4f}")

    lines.append("")
    lines.append("Теги")
    lines.append("-" * 60)
    for feature in constant.TAGS_VIBE:
        settings = tags.get(feature, {})
        label = settings.get("label", dataset_stats.get_feature_label(feature))
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


def export_train_report(train_step: float, plateau_score: int) -> str:
    """Выгружает отчет об обучении в TXT-файл."""
    data = storage.load_dataset()
    weights = storage.load_weights()
    reports_dir = os.path.join(constant.DIR_TXT, REPORTS_DIR_NAME)
    os.makedirs(reports_dir, exist_ok=True)

    file_name = "train_report_" + datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + ".txt"
    file_path = os.path.join(reports_dir, file_name)

    with open(file_path, "w", encoding="UTF-8") as file:
        file.write("\n".join(build_train_report(data, weights, train_step, plateau_score)))

    print(f"Отчет сохранен: {file_path}")
    return file_path

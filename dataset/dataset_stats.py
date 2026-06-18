"""Считает и форматирует статистику датасета для меню и отчетов."""

from config import constant


def get_feature_label(feature: str) -> str:
    """Возвращает понятное название признака."""
    return constant.FIELD_LABELS.get(feature, feature)


def collect_dataset_values(data: dict) -> dict:
    """Собирает числовые значения признаков из всех сериалов датасета."""
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
    """Считает минимум, максимум и среднее по числовым признакам."""
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
    """Собирает строки со сводкой по датасету."""
    stats = get_dataset_stats(data)
    lines = []
    lines.append("Данные о датасете")
    lines.append("-" * 60)
    lines.append(f"Количество сериалов: {len(data)}")

    if len(stats) == 0:
        lines.append("Числовых параметров нет.")
        return lines

    ordered_features = []
    fields_order = constant.MAIN_INFO + [constant.BIAS_FEATURE] + constant.RAW_SCORES + constant.COMPUTED_SCORES + constant.TAGS_VIBE
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

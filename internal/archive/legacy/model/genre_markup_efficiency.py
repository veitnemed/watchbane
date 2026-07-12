"""Read-only diagnostics for genre markup efficiency over public features."""

from model import feature_ablation
from model import model


REPORT_TYPE = "genre_markup_efficiency"
BASE_VARIANT = "public_base"
BASE_LABEL = "Базовая public-модель"
LOW_DATA_COUNT = 5


def _to_float(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _has_valid_user_score(movie_obj) -> bool:
    return _to_float(_get_user_score_or_none(movie_obj), None) is not None


def _get_user_score_or_none(movie_obj):
    try:
        return model.get_user_score(movie_obj)
    except (KeyError, TypeError, ValueError):
        return None


def collect_genre_coverage(data, genre_feature):
    """Count how often a genre is active among diagnostically usable records."""
    count = 0
    total_count = 0

    for movie_obj in model.iter_movies(data):
        if _has_valid_user_score(movie_obj) is False:
            continue

        total_count += 1
        features = model.get_features(movie_obj)
        genre_value = _to_float(features.get(genre_feature, 0.0), 0.0)
        if genre_value > 0:
            count += 1

    coverage_percent = 0.0
    if total_count > 0:
        coverage_percent = count / total_count * 100

    return {
        "genre": genre_feature,
        "count": count,
        "total_count": total_count,
        "coverage_percent": coverage_percent,
    }


def build_genre_efficiency_conclusion(delta, count):
    """Return a short interpretation for one genre result."""
    if count < LOW_DATA_COUNT:
        return "мало данных"
    if delta is None:
        return "нет данных"
    if delta > 0.01:
        return "помогает"
    if delta < -0.01:
        return "ухудшает"
    return "почти нет эффекта"


def collect_base_public_result(data):
    """Collect the read-only public-only baseline for genre efficiency."""
    features = list(feature_ablation.PUBLIC_FEATURES)
    alpha_selection = feature_ablation.select_best_alpha_by_loo(
        data,
        features,
        variant=BASE_VARIANT,
    )
    best_alpha = alpha_selection["best_alpha"]
    _x_data, y_data = feature_ablation.build_subset_xy(data, features)

    return {
        "variant": BASE_VARIANT,
        "label": BASE_LABEL,
        "features": features,
        "best_alpha": best_alpha,
        "loo_mae": alpha_selection["best_mae"],
        "count": len(y_data),
        "weights": feature_ablation.fit_subset_ridge_weights(data, features, best_alpha),
        "errors": alpha_selection.get("best_errors", []),
        "alpha_results": alpha_selection.get("alpha_results", []),
    }


def collect_single_genre_efficiency(data, genre_feature, base_result):
    """Collect read-only diagnostics for public features plus one genre."""
    features = list(feature_ablation.PUBLIC_FEATURES) + [genre_feature]
    alpha_selection = feature_ablation.select_best_alpha_by_loo(
        data,
        features,
        variant=f"public_plus_{genre_feature}",
    )
    best_alpha = alpha_selection["best_alpha"]
    weights = feature_ablation.fit_subset_ridge_weights(data, features, best_alpha)
    coverage = collect_genre_coverage(data, genre_feature)
    genre_loo_mae = alpha_selection["best_mae"]
    delta = _calculate_delta(base_result.get("loo_mae"), genre_loo_mae)
    count = coverage["count"]

    return {
        "genre": genre_feature,
        "label": genre_feature,
        "features": features,
        "count": count,
        "total_count": coverage["total_count"],
        "coverage_percent": coverage["coverage_percent"],
        "base_loo_mae": base_result.get("loo_mae"),
        "genre_loo_mae": genre_loo_mae,
        "delta": delta,
        "best_alpha": best_alpha,
        "genre_weight": weights.get(genre_feature),
        "conclusion": build_genre_efficiency_conclusion(delta, count),
        "errors": alpha_selection.get("best_errors", []),
        "weights": weights,
        "alpha_results": alpha_selection.get("alpha_results", []),
    }


def _calculate_delta(base_loo_mae, genre_loo_mae):
    if base_loo_mae is None or genre_loo_mae is None:
        return None
    return float(base_loo_mae) - float(genre_loo_mae)


def collect_genre_markup_efficiency_report(data):
    """Collect read-only diagnostics for each genre over the public baseline."""
    base_result = collect_base_public_result(data)
    genre_results = [
        collect_single_genre_efficiency(data, genre_feature, base_result)
        for genre_feature in feature_ablation.GENRE_FEATURES
    ]
    genre_results = sorted(
        genre_results,
        key=lambda result: _sort_delta(result.get("delta")),
        reverse=True,
    )

    return {
        "report_type": REPORT_TYPE,
        "base_result": base_result,
        "genre_results": genre_results,
    }


def _sort_delta(delta):
    if delta is None:
        return float("-inf")
    return float(delta)


def format_genre_markup_efficiency_report(report):
    """Format genre markup efficiency diagnostics for future console output."""
    base_result = report.get("base_result", {})
    genre_results = report.get("genre_results", [])
    lines = [
        "Эффективность жанровой разметки",
        "",
        "Базовая модель:",
        f"Признаки: {', '.join(base_result.get('features', []))}",
        f"LOO MAE: {_format_mae(base_result.get('loo_mae'))}",
        f"Alpha: {_format_alpha(base_result.get('best_alpha'))}",
        f"Всего записей: {int(base_result.get('count', 0))}",
        "",
        (
            f"{'Жанр':<18} {'Кол-во':>6} {'Доля':>7} {'Alpha':>8} "
            f"{'LOO MAE':>8} {'Delta':>8} {'Вес':>8} {'Вывод'}"
        ),
    ]

    if len(genre_results) == 0:
        lines.append("Нет данных для расчёта жанровой эффективности.")
    else:
        for result in genre_results:
            lines.append(_format_genre_result_row(result))

    lines.extend([
        "",
        (
            "Примечание: это диагностический отчёт. Веса и alpha не сохраняются "
            "как рабочая модель."
        ),
    ])

    return lines


def _format_genre_result_row(result):
    return (
        f"{result.get('label', result.get('genre', '')):<18} "
        f"{int(result.get('count', 0)):>6} "
        f"{_format_percent(result.get('coverage_percent')):>7} "
        f"{_format_alpha(result.get('best_alpha')):>8} "
        f"{_format_mae(result.get('genre_loo_mae')):>8} "
        f"{_format_signed(result.get('delta')):>8} "
        f"{_format_signed(result.get('genre_weight')):>8} "
        f"{result.get('conclusion', '')}"
    )


def _format_alpha(value) -> str:
    if value is None:
        return "-"
    return str(float(value))


def _format_mae(value) -> str:
    if value is None:
        return "н/д"
    return f"{float(value):.2f}"


def _format_signed(value) -> str:
    if value is None:
        return "н/д"
    return f"{float(value):+.2f}"


def _format_percent(value) -> str:
    if value is None:
        return "н/д"
    return f"{float(value):.0f}%"

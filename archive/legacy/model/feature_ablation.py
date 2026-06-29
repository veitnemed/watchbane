"""Read-only helpers for feature group ablation diagnostics."""

from model import linear_regression_train
from model import model


PUBLIC_FEATURES = [
    "kp_score",
    "kp_popularity",
    "imdb_score",
    "imdb_popularity",
]

GENRE_FEATURES = [
    "has_drama",
    "has_crime",
    "has_thriller",
    "has_comedy",
    "has_detective",
    "has_melodrama",
    "has_action",
    "has_fantasy",
    "has_romance",
]

FEATURE_ABLATION_VARIANTS = {
    "public_only_model": PUBLIC_FEATURES,
    "genres_only_model": GENRE_FEATURES,
    "public_plus_genres_model": PUBLIC_FEATURES + GENRE_FEATURES,
}

FEATURE_ABLATION_ALPHA_GRID = list(linear_regression_train.LOO_TRAINING_ALPHAS)
TOP_CONTRIBUTIONS_LIMIT = 4

VARIANT_LABELS = {
    "imdb_baseline": "Базовый IMDb",
    "kp_baseline": "Базовый KP",
    "public_only_model": "Модель только public",
    "genres_only_model": "Модель только жанры",
    "public_plus_genres_model": "Public + жанры",
}

KIND_LABELS = {
    "baseline": "база",
    "model": "модель",
}


def _to_float(value, default: float | None = 0.0) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def select_feature_subset(feature_dict, feature_names):
    """Return feature values for the selected names without mutating input."""
    return [
        _to_float(feature_dict.get(feature), 0.0)
        for feature in feature_names
    ]


def with_bias(values):
    """Return a new vector with the leading bias value."""
    return [1.0] + list(values)


def feature_names_with_bias(feature_names):
    """Return diagnostic weight names for a subset model."""
    return ["bias"] + list(feature_names)


def build_subset_xy(data, feature_names):
    """Build X/y for a selected feature subset without mutating dataset."""
    x_data, y_data, _movie_data = _build_subset_xy_with_movies(data, feature_names)
    return x_data, y_data


def _build_subset_xy_with_movies(data, feature_names):
    """Build aligned X/y/movie rows for LOO diagnostics."""
    x_data = []
    y_data = []
    movie_data = []

    for movie_obj in model.iter_movies(data):
        user_score = _to_float(_get_user_score_or_none(movie_obj), None)
        if user_score is None:
            continue

        features = model.get_features(movie_obj)
        x_data.append(with_bias(select_feature_subset(features, feature_names)))
        y_data.append(user_score)
        movie_data.append(movie_obj)

    return x_data, y_data, movie_data


def _get_user_score_or_none(movie_obj):
    try:
        return model.get_user_score(movie_obj)
    except (KeyError, TypeError, ValueError):
        return None


def _build_error_row(movie_obj, user_score, predicted_score, variant: str, contributions=None) -> dict:
    user_score = float(user_score)
    predicted_score = float(predicted_score)
    raw_scores = movie_obj.get("raw_scores", {}) if isinstance(movie_obj, dict) else {}
    row = {
        "title": _get_movie_title(movie_obj),
        "year": _get_movie_year(movie_obj),
        "user_score": user_score,
        "predicted_score": predicted_score,
        "error": abs(user_score - predicted_score),
        "variant": variant,
        "contributions": contributions or [],
    }

    for score_field in ["kp_score", "imdb_score"]:
        raw_score = _to_float(raw_scores.get(score_field), None)
        if raw_score is not None:
            row[score_field] = raw_score

    return row


def build_baseline_contributions(score_field: str, raw_score) -> list[dict]:
    """Return direct raw-score contribution for a baseline variant."""
    raw_score = float(raw_score)
    return [{
        "feature": score_field,
        "value": raw_score,
        "weight": 1.0,
        "contribution": raw_score,
    }]


def build_model_contributions(feature_names, values, weights, limit=TOP_CONTRIBUTIONS_LIMIT) -> list[dict]:
    """Return top diagnostic feature impacts for one LOO prediction."""
    contributions = []
    for feature, value, weight in zip(feature_names_with_bias(feature_names), values, weights):
        value = float(value)
        weight = float(weight)
        contributions.append({
            "feature": feature,
            "value": value,
            "weight": weight,
            "contribution": value * weight,
        })

    return sorted(
        contributions,
        key=lambda row: abs(float(row["contribution"])),
        reverse=True,
    )[:limit]


def _get_movie_title(movie_obj) -> str:
    if isinstance(movie_obj, dict):
        main_info = movie_obj.get("main_info", {})
        title = main_info.get("title")
        if title not in (None, ""):
            return str(title)
    return "Без названия"


def _get_movie_year(movie_obj):
    if isinstance(movie_obj, dict):
        main_info = movie_obj.get("main_info", {})
        return main_info.get("year")
    return None


def _sort_error_rows(errors: list[dict]) -> list[dict]:
    return sorted(errors, key=lambda row: float(row.get("error", 0.0)), reverse=True)


def _calculate_raw_score_baseline_mae(data, score_field: str, variant: str) -> dict:
    absolute_error = 0.0
    count = 0
    errors = []

    for movie_obj in model.iter_movies(data):
        user_score = _to_float(_get_user_score_or_none(movie_obj), None)
        if user_score is None:
            continue

        raw_scores = movie_obj.get("raw_scores", {})
        raw_score = _to_float(raw_scores.get(score_field), None)
        if raw_score is None:
            continue

        error_row = _build_error_row(
            movie_obj,
            user_score,
            raw_score,
            variant,
            build_baseline_contributions(score_field, raw_score),
        )
        errors.append(error_row)
        absolute_error += error_row["error"]
        count += 1

    return {
        "variant": variant,
        "kind": "baseline",
        "features": [score_field],
        "mae": None if count == 0 else absolute_error / count,
        "count": count,
        "errors": _sort_error_rows(errors),
    }


def calculate_imdb_baseline_mae(data):
    """Calculate IMDb raw rating MAE without training."""
    return _calculate_raw_score_baseline_mae(data, "imdb_score", "imdb_baseline")


def calculate_kp_baseline_mae(data):
    """Calculate Kinopoisk raw rating MAE without training."""
    return _calculate_raw_score_baseline_mae(data, "kp_score", "kp_baseline")


def calculate_subset_ridge_loo_mae(data, feature_names, alpha=None, variant=None):
    """Calculate read-only Ridge LOO MAE for a selected feature subset."""
    if alpha is None:
        alpha = linear_regression_train.BENCHMARK_RIDGE_ALPHA

    selected_features = list(feature_names)
    variant_name = variant or "subset_model"
    x_data, y_data, movie_data = _build_subset_xy_with_movies(data, selected_features)
    count = len(y_data)
    if count < 2 or linear_regression_train.is_method_available(linear_regression_train.BENCHMARK_METHOD) is False:
        return {
            "kind": "model",
            "features": selected_features,
            "mae": None,
            "count": count,
            "alpha": alpha,
            "errors": [],
        }

    mean_error = 0.0
    errors = []
    for index in range(count):
        train_x = x_data.copy()
        train_y = y_data.copy()
        test_x = train_x.pop(index)
        test_y = train_y.pop(index)

        estimator = linear_regression_train.build_estimator(
            linear_regression_train.BENCHMARK_METHOD,
            alpha,
            l1_ratio=0.5,
            max_iter=5000,
        )
        estimator.fit(train_x, train_y)
        prediction = float(estimator.predict([test_x])[0])
        error_row = _build_error_row(
            movie_data[index],
            test_y,
            prediction,
            variant_name,
            build_model_contributions(selected_features, test_x, getattr(estimator, "coef_", [])),
        )
        errors.append(error_row)
        mean_error += error_row["error"] / count

    return {
        "kind": "model",
        "features": selected_features,
        "mae": mean_error,
        "count": count,
        "alpha": alpha,
        "errors": _sort_error_rows(errors),
    }


def select_best_alpha_by_loo(data, feature_names, alpha_grid=None, variant=None):
    """Select a diagnostic Ridge alpha by subset LOO MAE."""
    if alpha_grid is None:
        alpha_grid = FEATURE_ABLATION_ALPHA_GRID

    selected_features = list(feature_names)
    alpha_results = []
    best_alpha = None
    best_mae = None
    best_errors = []

    for alpha in alpha_grid:
        if variant is None:
            result = calculate_subset_ridge_loo_mae(data, selected_features, alpha=alpha)
        else:
            result = calculate_subset_ridge_loo_mae(
                data,
                selected_features,
                alpha=alpha,
                variant=variant,
            )
        mae = result.get("mae")
        alpha_results.append({
            "alpha": alpha,
            "mae": mae,
        })
        if mae is None:
            continue
        if _is_better_alpha_result(mae, alpha, best_mae, best_alpha):
            best_alpha = alpha
            best_mae = mae
            best_errors = result.get("errors", [])

    return {
        "best_alpha": best_alpha,
        "best_mae": best_mae,
        "alpha_results": alpha_results,
        "best_errors": best_errors,
    }


def _is_better_alpha_result(mae, alpha, best_mae, best_alpha) -> bool:
    if best_mae is None:
        return True
    mae_delta = float(mae) - float(best_mae)
    if mae_delta < -1e-9:
        return True
    if abs(mae_delta) < 1e-9 and best_alpha is not None:
        return float(alpha) > float(best_alpha)
    return False


def fit_subset_ridge_weights(data, feature_names, alpha):
    """Fit final diagnostic subset Ridge weights on the full dataset."""
    selected_features = list(feature_names)
    x_data, y_data = build_subset_xy(data, selected_features)
    if len(y_data) == 0 or alpha is None:
        return {}
    if linear_regression_train.is_method_available(linear_regression_train.BENCHMARK_METHOD) is False:
        return {}

    estimator = linear_regression_train.build_estimator(
        linear_regression_train.BENCHMARK_METHOD,
        alpha,
        l1_ratio=0.5,
        max_iter=5000,
    )
    estimator.fit(x_data, y_data)

    return {
        feature: float(coef)
        for feature, coef in zip(feature_names_with_bias(selected_features), estimator.coef_)
    }


def collect_feature_ablation_report(data, alpha=None):
    """Collect read-only feature ablation diagnostics."""
    results = [
        calculate_imdb_baseline_mae(data),
        calculate_kp_baseline_mae(data),
    ]

    alpha_grid = [alpha] if alpha is not None else None
    for variant, features in FEATURE_ABLATION_VARIANTS.items():
        alpha_selection = select_best_alpha_by_loo(
            data,
            features,
            alpha_grid=alpha_grid,
            variant=variant,
        )
        best_alpha = alpha_selection["best_alpha"]
        _x_data, y_data = build_subset_xy(data, features)
        result = {
            "variant": variant,
            "kind": "model",
            "features": list(features),
            "mae": alpha_selection["best_mae"],
            "count": len(y_data),
            "best_alpha": best_alpha,
            "alpha_results": alpha_selection["alpha_results"],
            "weights": fit_subset_ridge_weights(data, features, best_alpha),
            "errors": alpha_selection["best_errors"],
        }
        results.append(result)

    return results


def format_feature_ablation_report(results):
    """Format feature ablation diagnostics for future UI printing."""
    lines = [
        "Отчёт диагностики признаков",
        "",
        f"{'Вариант':<27} {'Тип':<10} {'Кол-во':>6} {'Alpha':>8} {'LOO MAE / MAE':>13}",
    ]

    result_by_variant = {}
    for result in results:
        variant = result.get("variant", "")
        result_by_variant[variant] = result
        label = VARIANT_LABELS.get(variant, variant)
        kind = KIND_LABELS.get(result.get("kind", ""), result.get("kind", ""))
        mae_text = _format_mae(result.get("mae"))
        alpha_text = _format_alpha(result.get("best_alpha"))
        lines.append(
            f"{label:<27} {kind:<10} {int(result.get('count', 0)):>6} {alpha_text:>8} {mae_text:>13}"
        )

    lines.extend(_format_weight_blocks(results))
    lines.extend(_format_error_blocks(results))

    best = _find_best_result(results)
    if best is not None:
        best_variant = best.get("variant", "")
        lines.extend(["", f"Лучший результат: {VARIANT_LABELS.get(best_variant, best_variant)}"])

    conclusion = _format_genre_conclusion(result_by_variant)
    if conclusion is not None:
        lines.append(conclusion)

    lines.extend([
        "",
        (
            "Примечание: веса диагностические. Они обучены на всём dataset "
            "с alpha, выбранным по LOO MAE, и не сохраняются как рабочая модель."
        ),
    ])

    return lines


def _format_alpha(value) -> str:
    if value is None:
        return "-"
    return str(float(value))


def _format_mae(value) -> str:
    if value is None:
        return "н/д"
    return f"{float(value):.2f}"


def _format_weight_blocks(results) -> list[str]:
    lines = []
    for result in results:
        if result.get("kind") != "model":
            continue

        variant = result.get("variant", "")
        weights = result.get("weights", {})
        features = result.get("features", [])
        lines.extend(["", f"Веса: {VARIANT_LABELS.get(variant, variant)}"])
        if len(weights) == 0:
            lines.append("нет данных")
            continue
        for feature in feature_names_with_bias(features):
            lines.append(f"{feature}: {_format_weight(weights.get(feature))}")
    return lines


def _format_error_blocks(results) -> list[str]:
    lines = []
    for result in results:
        variant = result.get("variant", "")
        label = VARIANT_LABELS.get(variant, variant)
        lines.extend(["", f"Топ-5 ошибок: {label}"])

        errors = result.get("errors", [])
        if len(errors) == 0:
            lines.append("Нет данных для расчёта ошибок.")
            continue

        for index, error_row in enumerate(errors[:5], start=1):
            title = error_row.get("title") or "Без названия"
            year = _format_year(error_row.get("year"))
            user_score = _format_score(error_row.get("user_score"))
            predicted_score = _format_score(error_row.get("predicted_score"))
            error = _format_error_value(error_row.get("error"))
            lines.append(
                f"{index}. {title} ({year}): "
                f"моя={user_score}, прогноз={predicted_score}, ошибка={error}"
            )
            lines.append(f"   Топ-4 вклада: {_format_contributions(error_row.get('contributions', []))}")

    return lines


def _format_contributions(contributions) -> str:
    if len(contributions) == 0:
        return "нет данных"
    return "; ".join(
        f"{row.get('feature', 'feature')}={_format_contribution(row.get('contribution'))}"
        for row in contributions[:TOP_CONTRIBUTIONS_LIMIT]
    )


def _format_weight(value) -> str:
    if value is None:
        return "н/д"
    return f"{float(value):.4f}"


def _format_year(value) -> str:
    if value in (None, ""):
        return "год н/д"
    return str(value)


def _format_score(value) -> str:
    if value is None:
        return "н/д"
    return f"{float(value):.1f}"


def _format_error_value(value) -> str:
    if value is None:
        return "н/д"
    return f"{float(value):.2f}"


def _format_contribution(value) -> str:
    if value is None:
        return "н/д"
    return f"{float(value):+.2f}"


def _find_best_result(results):
    scored_results = [
        result for result in results
        if result.get("mae") is not None
    ]
    if len(scored_results) == 0:
        return None
    return min(scored_results, key=lambda result: float(result["mae"]))


def _format_genre_conclusion(result_by_variant: dict) -> str | None:
    public_result = result_by_variant.get("public_only_model")
    combined_result = result_by_variant.get("public_plus_genres_model")
    if public_result is None or combined_result is None:
        return None

    public_mae = public_result.get("mae")
    combined_mae = combined_result.get("mae")
    if public_mae is None or combined_mae is None:
        return "Вывод: эффект жанров недоступен"

    improvement = float(public_mae) - float(combined_mae)
    if improvement > 0.01:
        return f"Вывод: жанры улучшили public-only модель на {improvement:.2f}"
    if improvement < -0.01:
        return f"Вывод: жанры ухудшили public-only модель на {abs(improvement):.2f}"
    return "Вывод: эффект жанров почти нулевой"

"""Обучает модель линейной регрессией с регуляризацией через scikit-learn."""

from __future__ import annotations

import time

from config import constant
from common import valid
from ui import request
from ui import ui
from model import model

try:
    from sklearn.linear_model import ElasticNet, Lasso, Ridge, SGDRegressor
except ImportError:  # pragma: no cover
    ElasticNet = None
    Lasso = None
    Ridge = None
    SGDRegressor = None

try:
    import numpy as np
    from scipy.optimize import minimize
except ImportError:  # pragma: no cover
    np = None
    minimize = None


METHODS = {
    "1": ("ridge", "Ridge"),
    "2": ("lasso", "Lasso"),
    "3": ("elasticnet", "ElasticNet"),
    "4": ("mae_sgd", "SGDRegressor (MAE)"),
    "5": ("mae_scipy", "scipy minimize (MAE)"),
}

BENCHMARK_METHOD = "ridge"
BENCHMARK_METHOD_LABEL = "Ridge"
BENCHMARK_RIDGE_ALPHA = 1.0
LOO_TRAINING_ALPHAS = [0.01, 0.03, 0.1, 0.3, 1.0, 3.0, 10.0, 30.0, 100.0]


def is_available() -> bool:
    """Проверяет доступность scikit-learn."""
    return any([
        all(item is not None for item in [Ridge, Lasso, ElasticNet, SGDRegressor]),
        all(item is not None for item in [np, minimize]),
    ])


def is_method_available(method: str) -> bool:
    """Проверяет доступность конкретного линейного метода."""
    if method == "mae_scipy":
        return all(item is not None for item in [np, minimize])
    return all(item is not None for item in [Ridge, Lasso, ElasticNet, SGDRegressor])


def build_xy(data: list) -> tuple[list[list[float]], list[float]]:
    """Преобразует датасет в матрицу признаков и целевые значения."""
    x_data = []
    y_data = []

    for movie in model.iter_movies(data):
        features = model.get_features(movie)
        x_data.append([float(features[feature]) for feature in constant.FEATURES])
        y_data.append(float(model.get_user_score(movie)))

    return x_data, y_data


def build_estimator(method: str, alpha: float, l1_ratio: float, max_iter: int):
    """Создает estimator для выбранного режима линейного обучения."""
    if method == "ridge":
        return Ridge(alpha=alpha, fit_intercept=False)
    if method == "lasso":
        return Lasso(alpha=alpha, fit_intercept=False, max_iter=max_iter, random_state=0)
    if method == "elasticnet":
        return ElasticNet(
            alpha=alpha,
            l1_ratio=l1_ratio,
            fit_intercept=False,
            max_iter=max_iter,
            random_state=0,
        )
    if method == "mae_sgd":
        return SGDRegressor(
            loss="epsilon_insensitive",
            epsilon=0.0,
            penalty="elasticnet",
            alpha=alpha,
            l1_ratio=l1_ratio,
            fit_intercept=False,
            max_iter=max_iter,
            tol=1e-4,
            random_state=0,
        )
    raise ValueError(f"Неизвестный метод линейного обучения: {method}")


def fit_mae_with_scipy(
    x_data: list[list[float]],
    y_data: list[float],
    start_weights: dict,
    alpha: float,
    l1_ratio: float,
    max_iter: int,
) -> dict:
    """Минимизирует MAE с elastic-net регуляризацией через scipy."""
    x_matrix = np.asarray(x_data, dtype=float)
    y_vector = np.asarray(y_data, dtype=float)
    start_vector = np.asarray(
        [float(start_weights.get(feature, 0.0)) for feature in constant.FEATURES],
        dtype=float,
    )

    def objective(vector) -> float:
        prediction = x_matrix @ vector
        mae = np.mean(np.abs(prediction - y_vector))
        l1_penalty = np.sum(np.abs(vector))
        l2_penalty = np.sum(vector * vector)
        regularization = alpha * (l1_ratio * l1_penalty + (1 - l1_ratio) * l2_penalty)
        return float(mae + regularization)

    result = minimize(
        objective,
        start_vector,
        method="Powell",
        options={"maxiter": max_iter, "disp": False},
    )
    best_vector = result.x if result.success or result.x is not None else start_vector

    return {
        feature: float(weight)
        for feature, weight in zip(constant.FEATURES, best_vector)
    }


def fit_linear_weights(
    data: list,
    method: str,
    start_weights: dict | None = None,
    alpha: float = 0.1,
    l1_ratio: float = 0.5,
    max_iter: int = 5000,
) -> dict:
    """Обучает линейную модель и возвращает словарь весов."""
    x_data, y_data = build_xy(data)
    if len(x_data) == 0:
        return constant.DEFAULT_WEIGHTS.copy()

    if start_weights is None:
        start_weights = constant.DEFAULT_WEIGHTS.copy()

    if method == "mae_scipy":
        return fit_mae_with_scipy(x_data, y_data, start_weights, alpha, l1_ratio, max_iter)

    estimator = build_estimator(method, alpha, l1_ratio, max_iter)
    estimator.fit(x_data, y_data)

    return {
        feature: float(coef)
        for feature, coef in zip(constant.FEATURES, estimator.coef_)
    }


def train_ridge_for_benchmark(
    data: list,
    start_weights: dict | None = None,
    alpha: float = BENCHMARK_RIDGE_ALPHA,
) -> dict:
    """Обучает временные Ridge-веса для benchmark без сохранения в weights.json."""
    return fit_linear_weights(
        data=data,
        method=BENCHMARK_METHOD,
        start_weights=start_weights,
        alpha=alpha,
    )


def calculate_linear_loo_mae(
    data: list,
    method: str,
    start_weights: dict,
    alpha: float,
    l1_ratio: float,
    max_iter: int,
    verbose: bool = False,
    progress_callback=None,
) -> float | None:
    """Считает LOO MAE для выбранного линейного режима и его параметров."""
    movies = model.iter_movies(data)
    if len(movies) < 2:
        return None

    mean_error = 0
    for idx in range(len(movies)):
        train_data = movies.copy()
        test_movie = train_data.pop(idx)
        if progress_callback is not None:
            progress_callback(idx + 1, len(movies), test_movie)
        elif verbose:
            print(f"Итерация {idx + 1}/{len(movies)}: {model.get_movie_title(test_movie)}")

        trained_weights = fit_linear_weights(
            data=train_data,
            method=method,
            start_weights=start_weights,
            alpha=alpha,
            l1_ratio=l1_ratio,
            max_iter=max_iter,
        )
        predict = model.predict_score(model.get_features(test_movie), trained_weights)
        mean_error += abs(predict - model.get_user_score(test_movie)) / len(movies)

    return mean_error


def _format_optional_metric(value: float | None) -> str:
    if value is None:
        return "не рассчитан"
    return f"{value:.4f}"


def collect_loo_metrics(data, weights: dict, loo_mae: float | None) -> dict[str, float | None]:
    return {
        "Model MAE": model.mean_absolute_error(data, weights),
        "KP_MAE": model.kp_mean_absolute_error(data),
        "IMDb_MAE": model.imdb_mean_absolute_error(data),
        "LOO MAE": loo_mae,
    }


def _format_metric_delta(before: float | None, after: float | None) -> str:
    if before is None:
        return "было не рассчитано"
    if after is None:
        return "не рассчитан"

    delta = after - before
    if abs(delta) < 0.00005:
        return "без изменений"
    if delta < 0:
        return f"лучше на {delta:.4f}"
    return f"хуже на +{delta:.4f}"


def print_metrics_report(
    title: str,
    metrics: dict[str, float | None],
    before_metrics: dict[str, float | None] | None = None,
    decision: str | None = None,
) -> None:
    border = "=" * 58
    print(border)
    print(title.center(58))
    print("")

    for name in ["Model MAE", "KP_MAE", "IMDb_MAE", "LOO MAE"]:
        value = metrics.get(name)
        line = f"{name + ':':<11} {_format_optional_metric(value):>10}"
        if before_metrics is not None:
            line += f"   {_format_metric_delta(before_metrics.get(name), value)}"
        print(line)

    if decision is not None:
        print("")
        print(f"Решение: {decision}")

    print("")
    print(border)


def print_loo_metrics_summary(before_metrics: dict[str, float | None], after_metrics: dict[str, float | None]) -> None:
    before_loo = before_metrics.get("LOO MAE")
    after_loo = after_metrics.get("LOO MAE")

    print("Итог:")
    if before_loo is None and after_loo is None:
        print("LOO MAE не рассчитан.")
    elif before_loo is None:
        print(f"LOO MAE было не рассчитано -> {_format_optional_metric(after_loo)}")
    elif after_loo is not None and after_loo < before_loo:
        print(f"LOO MAE улучшился: {before_loo:.4f} -> {after_loo:.4f}")
    elif after_loo is not None and abs(after_loo - before_loo) < 0.00005:
        print("LOO MAE не изменился.")
    else:
        print("LOO MAE не улучшился.")
    print("Веса сохранены.")


def _format_baseline_comparison(model_loo_mae: float, baseline_mae: float, baseline_name: str) -> str:
    delta = abs(model_loo_mae - baseline_mae)
    if abs(model_loo_mae - baseline_mae) < 0.00005:
        return f"модель примерно равна {baseline_name}"
    if model_loo_mae < baseline_mae:
        return f"модель лучше {baseline_name} на {delta:.4f}"
    return f"модель хуже {baseline_name} на {delta:.4f}"


def _baseline_result_phrase(model_loo_mae: float, kp_mae: float, imdb_mae: float) -> str:
    kp_better = model_loo_mae < kp_mae
    imdb_better = model_loo_mae < imdb_mae
    kp_equal = abs(model_loo_mae - kp_mae) < 0.00005
    imdb_equal = abs(model_loo_mae - imdb_mae) < 0.00005

    if kp_better and imdb_better:
        return "Модель уже лучше KP и IMDb."
    if kp_better and not imdb_better and not imdb_equal:
        return "Модель уже лучше KP, но пока хуже IMDb."
    if imdb_better and not kp_better and not kp_equal:
        return "Модель уже лучше IMDb, но пока хуже KP."
    if kp_equal and imdb_equal:
        return "Модель примерно равна KP и IMDb."
    if kp_equal and imdb_better:
        return "Модель примерно равна KP и лучше IMDb."
    if imdb_equal and kp_better:
        return "Модель лучше KP и примерно равна IMDb."
    if kp_equal:
        return "Модель примерно равна KP, но пока хуже IMDb."
    if imdb_equal:
        return "Модель примерно равна IMDb, но пока хуже KP."
    return "Модель пока хуже KP и IMDb."


def print_baseline_comparison(metrics: dict[str, float | None]) -> None:
    model_loo_mae = metrics.get("LOO MAE")
    kp_mae = metrics.get("KP_MAE")
    imdb_mae = metrics.get("IMDb_MAE")

    print("Сравнение с baseline:")
    if model_loo_mae is None:
        print("Model LOO MAE: не рассчитан")
        print("Сравнение недоступно: LOO MAE не рассчитан.")
        return
    if kp_mae is None or imdb_mae is None:
        print("Сравнение недоступно: не рассчитаны KP_MAE или IMDb_MAE.")
        return

    print(f"Model LOO MAE: {model_loo_mae:.4f}")
    print(f"KP_MAE:        {kp_mae:.4f}   {_format_baseline_comparison(model_loo_mae, kp_mae, 'KP')}")
    print(f"IMDb_MAE:      {imdb_mae:.4f}   {_format_baseline_comparison(model_loo_mae, imdb_mae, 'IMDb')}")
    print("")
    print("Вывод:")
    print(_baseline_result_phrase(model_loo_mae, kp_mae, imdb_mae))


def print_weights_summary(weights: dict, top_n: int = 10) -> None:
    bias = float(weights.get("bias", 0.0))
    weighted_features = []
    for name, value in weights.items():
        if name == "bias":
            continue
        try:
            weight = float(value)
        except (TypeError, ValueError):
            continue
        weighted_features.append((name, weight))

    positive_weights = sorted(
        ((name, weight) for name, weight in weighted_features if weight > 0),
        key=lambda item: item[1],
        reverse=True,
    )
    negative_weights = sorted(
        ((name, weight) for name, weight in weighted_features if weight < 0),
        key=lambda item: item[1],
    )

    print("Веса модели:")
    print("")
    print(f"bias: {bias:.4f}")
    print("")

    if len(positive_weights) == 0:
        print("Топ положительных весов: нет")
    else:
        print("Топ положительных весов:")
        print("")
        for index, (name, weight) in enumerate(positive_weights[:top_n], start=1):
            print(f"{index}. {name}: {weight:+.4f}")

    print("")
    if len(negative_weights) == 0:
        print("Топ отрицательных весов: нет")
    else:
        print("Топ отрицательных весов:")
        print("")
        for index, (name, weight) in enumerate(negative_weights[:top_n], start=1):
            print(f"{index}. {name}: {weight:+.4f}")


def run_loo_training(data, weights) -> None:
    """Подбирает Ridge alpha по LOO, обучает финальную модель и сохраняет результат."""
    from data_work import storage

    movies = model.iter_movies(data)
    if len(movies) < 3:
        print("Недостаточно данных для LOO обучения.")
        return

    if is_method_available(BENCHMARK_METHOD) is False:
        print(f"LOO обучение недоступно: не установлен метод {BENCHMARK_METHOD_LABEL}.")
        return

    print("LOO обучение")
    print(f"Метод: {BENCHMARK_METHOD_LABEL}")
    print(f"Записей в датасете: {len(movies)}\n")
    before_metrics = collect_loo_metrics(
        data=movies,
        weights=weights,
        loo_mae=storage.get_saved_loo_mae(),
    )
    print_metrics_report(
        title="ДО LOO ОБУЧЕНИЯ",
        metrics=before_metrics,
    )
    print("")

    results = []
    for alpha_index, alpha in enumerate(LOO_TRAINING_ALPHAS, start=1):
        print(f"Проверка alpha={alpha} [{alpha_index}/{len(LOO_TRAINING_ALPHAS)}]")
        loo_mae = calculate_linear_loo_mae(
            data=movies,
            method=BENCHMARK_METHOD,
            start_weights=weights,
            alpha=alpha,
            l1_ratio=0.5,
            max_iter=5000,
            verbose=True,
        )

        if loo_mae is None:
            print(f"LOO MAE для alpha={alpha} не рассчитан.\n")
            continue

        print(f"LOO MAE для alpha={alpha}: {loo_mae:.4f}\n")
        results.append((loo_mae, alpha))

    if len(results) == 0:
        print("LOO обучение не завершено: не удалось рассчитать LOO MAE.")
        return

    best_loo_mae, best_alpha = min(results, key=lambda item: item[0])
    print(f"Лучший alpha: {best_alpha}")
    print(f"Лучший LOO MAE: {best_loo_mae:.4f}\n")

    final_weights = train_ridge_for_benchmark(
        data=movies,
        start_weights=weights,
        alpha=best_alpha,
    )
    storage.save_weights(final_weights)
    storage.set_saved_loo_mae(best_loo_mae)

    print("LOO обучение завершено.")
    print(f"Лучший Ridge alpha: {best_alpha}")
    print(f"Лучший LOO MAE: {best_loo_mae:.4f}")
    print("Финальная модель обучена на всём датасете.")
    print("weights.json обновлён.")
    print("config/model_metrics.json обновлён.")
    print("")
    saved_weights = storage.load_weights()
    after_metrics = collect_loo_metrics(
        data=movies,
        weights=saved_weights,
        loo_mae=storage.get_saved_loo_mae(),
    )
    print_metrics_report(
        title="ПОСЛЕ LOO ОБУЧЕНИЯ",
        metrics=after_metrics,
        before_metrics=before_metrics,
        decision="веса сохранены",
    )
    print("")
    print_loo_metrics_summary(before_metrics, after_metrics)
    print("")
    print_baseline_comparison(after_metrics)
    print("")
    print_weights_summary(saved_weights)


def choose_method() -> tuple[str, str] | None:
    """Запрашивает у пользователя конкретный линейный метод."""
    print("Линейные методы обучения:\n")
    for key, (_, label) in METHODS.items():
        print(f" {key} >> {label}")
    print(" 0 >> Назад\n")

    command = request.loop_input(
        text=">> ",
        funcs_list=[lambda value: value in {"0", "1", "2", "3", "4", "5"}],
    )
    if command == "0":
        return None
    return METHODS[command]


def request_float(text: str, default_value: float) -> float:
    """Запрашивает float-параметр с дефолтным значением."""
    def is_valid_value(raw: str) -> bool:
        if raw.strip() == "":
            return True
        try:
            return valid.parse_float(raw) >= 0
        except ValueError:
            return False

    value = request.loop_input(
        text=f"{text} [{default_value}] >> ",
        funcs_list=[is_valid_value],
    )
    if value.strip() == "":
        return default_value
    return valid.parse_float(value)


def request_int(text: str, default_value: int) -> int:
    """Запрашивает integer-параметр с дефолтным значением."""
    value = request.loop_input(
        text=f"{text} [{default_value}] >> ",
        funcs_list=[lambda raw: raw.strip() == "" or (raw.isdigit() and int(raw) > 0)],
    )
    if value.strip() == "":
        return default_value
    return int(value)


def train_linear_model(data, weights) -> None:
    """Запускает отдельный режим линейного обучения через sklearn."""
    if len(data) == 0:
        print("Датасет пуст.")
        return

    if is_available() is False:
        print("Режим линейной регрессии недоступен: не установлены sklearn/scipy.")
        print("Установите зависимости из requirements.txt и запустите снова.")
        return

    chosen = choose_method()
    if chosen is None:
        return

    method, label = chosen
    if is_method_available(method) is False:
        print(f"Выбранный режим недоступен в текущем окружении: {label}")
        return

    alpha = request_float("Alpha регуляризации", 0.1)
    l1_ratio = 0.5
    if method in {"elasticnet", "mae_sgd", "mae_scipy"}:
        l1_ratio = request_float("L1 ratio", 0.5)
    max_iter = request_int("Максимум итераций", 5000)

    start_time = time.perf_counter()
    old_error = model.mean_absolute_error(data, weights)
    new_weights = fit_linear_weights(
        data=data,
        method=method,
        start_weights=weights,
        alpha=alpha,
        l1_ratio=l1_ratio,
        max_iter=max_iter,
    )
    new_error = model.mean_absolute_error(data, new_weights)

    delta_time = time.perf_counter() - start_time
    ui.show_result_train(new_weights, old_error, new_error, delta_time)
    print(f"Линейный режим: {label}")
    print(f"Сумма весов: {round(sum(new_weights.values()), 4)}")
    print(f"Train MAE: {new_error:.4f}")
    print("Train MAE показан справочно.")
    print("Решение о сохранении принято по LOO MAE.")

    print("\nРасчёт LOO MAE для новых весов...")
    new_loo_mae = calculate_linear_loo_mae(
        data=data,
        method=method,
        start_weights=weights,
        alpha=alpha,
        l1_ratio=l1_ratio,
        max_iter=max_iter,
    )
    if new_loo_mae is None:
        print("Веса отклонены: недостаточно данных для расчёта LOO MAE.")
        return

    model.save_weights_if_loo_improved(
        new_weights=new_weights,
        dataset=data,
        new_loo_mae=new_loo_mae,
        source_name=f"Линейное обучение: {label}",
    )

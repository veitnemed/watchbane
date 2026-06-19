"""UI-оркестрация режимов обучения: ввод параметров, запуск и вывод результата.

Чистые вычисления живут в model.linear_regression_train / model.noise_experiment,
а здесь только интерактив (input/print) поверх них.
"""

import time

from common import valid
from model import linear_regression_train
from model import model
from model import noise_experiment
from ui import request
from ui import ui


def choose_method() -> tuple[str, str] | None:
    """Запрашивает у пользователя конкретный линейный метод."""
    print("Линейные методы обучения:\n")
    for key, (_, label) in linear_regression_train.METHODS.items():
        print(f" {key} >> {label}")
    print(" 0 >> Назад\n")

    command = request.loop_input(
        text=">> ",
        funcs_list=[lambda value: value in {"0", "1", "2", "3", "4", "5"}],
    )
    if command == "0":
        return None
    return linear_regression_train.METHODS[command]


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

    if linear_regression_train.is_available() is False:
        print("Режим линейной регрессии недоступен: не установлены sklearn/scipy.")
        print("Установите зависимости из requirements.txt и запустите снова.")
        return

    chosen = choose_method()
    if chosen is None:
        return

    method, label = chosen
    if linear_regression_train.is_method_available(method) is False:
        print(f"Выбранный режим недоступен в текущем окружении: {label}")
        return

    alpha = request_float("Alpha регуляризации", 0.1)
    l1_ratio = 0.5
    if method in {"elasticnet", "mae_sgd", "mae_scipy"}:
        l1_ratio = request_float("L1 ratio", 0.5)
    max_iter = request_int("Максимум итераций", 5000)

    start_time = time.perf_counter()
    old_error = model.mean_absolute_error(data, weights)
    new_weights = linear_regression_train.fit_linear_weights(
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
    new_loo_mae = linear_regression_train.calculate_linear_loo_mae(
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


def _fit_with_ridge_benchmark(train_data, start_weights, **_ignored) -> dict:
    """Обучает модель на зашумленных данных через Ridge benchmark-режим."""
    return linear_regression_train.train_ridge_for_benchmark(
        data=train_data,
        start_weights=start_weights,
    )


def run_noise_sensitivity(data, weights) -> None:
    """Запускает интерактивный шумовой эксперимент устойчивости модели."""
    if len(data) == 0:
        print("Датасет пуст.")
        return

    if linear_regression_train.is_method_available(linear_regression_train.BENCHMARK_METHOD) is False:
        print(
            "Шумовой эксперимент недоступен: "
            f"не установлен {linear_regression_train.BENCHMARK_METHOD_LABEL}."
        )
        return

    delta_raw = request.loop_input(
        text="Максимальное смещение оценки [0.5] >> ",
        funcs_list=[valid.is_correct_noise_delta],
    )
    delta = 0.5 if delta_raw.strip() == "" else valid.parse_float(delta_raw)

    runs_raw = request.loop_input(
        text="Количество повторов [10] >> ",
        funcs_list=[valid.is_correct_noise_runs],
    )
    runs = 10 if runs_raw.strip() == "" else int(runs_raw)

    result = noise_experiment.run_noise_experiment(
        data=data,
        weights=weights,
        delta=delta,
        runs=runs,
        fit_func=_fit_with_ridge_benchmark,
    )

    print("\nПРОВЕРКА УСТОЙЧИВОСТИ К ШУМУ")
    print("=" * 50)
    print(f"Метод обучения для benchmark: {linear_regression_train.BENCHMARK_METHOD_LABEL}")
    print(f"Повторов: {result['runs']}")
    print(f"Шум оценки: ±{result['delta']:.2f}")
    print(f"MAE до эксперимента: {result['original_mae_before']:.4f}")
    print(f"Средний MAE на зашумленных данных: {result['avg_noisy_mae']:.4f}")
    print(
        "Средний MAE на исходных данных после обучения на шуме: "
        f"{result['avg_original_mae_after_noise_training']:.4f}"
    )
    print(
        "Диапазон MAE: "
        f"{result['min_original_mae_after_noise_training']:.4f}"
        f" .. {result['max_original_mae_after_noise_training']:.4f}"
    )

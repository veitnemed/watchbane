"""Содержит вспомогательные режимы диагностики модели."""

from common import valid
from interface import request
from model_work import linear_regression_train
from model_work import noise_experiment


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

"""Содержит режимы обучения модели."""

import time

from config import constant
from core import valid
from data_work import storage
from interface import request
from interface import ui
from model_work import model
from model_work import noise_experiment


def show_weights_sum(weights: dict) -> None:
    """Печатает сумму весов после обучения."""
    print(f'Сумма весов: {round(sum(weights.values()), 4)}')


def train_model(data, weights, fit_func, title: str, **train_kwargss):
    """Обучает модель выбранным способом."""
    start_time = time.perf_counter()

    print(title)
    old_error = model.mean_absolute_error(data, weights)
    new_weights = fit_func(data, weights, **train_kwargss)
    new_weights = model.normalize_weights(new_weights)
    new_error = model.mean_absolute_error(data, new_weights)

    if new_error <= old_error:
        storage.save_weights(new_weights)
    else:
        new_weights = weights
        new_error = old_error
        print('Новые веса не сохранены: ошибка модели увеличилась.')

    delta_time = time.perf_counter() - start_time
    ui.show_result_train(new_weights, old_error, new_error, delta_time)
    show_weights_sum(new_weights)


def auto_train_grid_steps(data, weights, title: str):
    """Подбирает веса на нескольких шагах обучения."""
    start_time = time.perf_counter()
    step_values = constant.STEPS_TRAIN
    error_now = model.mean_absolute_error(data, weights)
    best_weights = weights.copy()
    best_error = error_now

    print(title)
    for step in step_values:
        new_weights = model.fit_weights(data, best_weights, passes=5, step=step)
        new_weights = model.normalize_weights(new_weights)
        new_error = model.mean_absolute_error(data, new_weights)

        if new_error < best_error:
            best_error = new_error
            best_weights = new_weights

        print(f'step: {step} | error_now: {round(best_error, 2)}')

    storage.save_weights(best_weights)
    delta_time = time.perf_counter() - start_time
    ui.show_result_train(best_weights, error_now, best_error, delta_time)
    show_weights_sum(best_weights)


def auto_train_mix_mode(data, weights, title: str):
    """Запускает смешанный режим обучения."""
    start_time = time.perf_counter()
    step_values = constant.STEPS_TRAIN_MIX
    error_now = model.mean_absolute_error(data, weights)
    best_weights = weights.copy()
    best_error = error_now

    print(title)
    for step in step_values:
        no_mut = 0
        while True:
            new_weights_1 = model.fit_weights(data, best_weights, passes=1, step=step)
            new_weights_1 = model.normalize_weights(new_weights_1)
            new_error_1 = model.mean_absolute_error(data, new_weights_1)
            if new_error_1 < best_error:
                best_error = new_error_1
                best_weights = new_weights_1
                no_mut = 0
            else:
                no_mut += 1

            new_weights_2 = model.fit_weights_until_plateau(
                data=data,
                start_weights=best_weights,
                score=200,
                step=step
            )
            new_weights_2 = model.normalize_weights(new_weights_2)
            new_error_2 = model.mean_absolute_error(data, new_weights_2)

            if new_error_2 < best_error:
                best_error = new_error_2
                best_weights = new_weights_2
                no_mut = 0
            else:
                no_mut += 1

            if no_mut >= 5:
                break

        print(f'step: {step} | error_now: {round(best_error, 2)}')

    storage.save_weights(best_weights)
    delta_time = time.perf_counter() - start_time
    ui.show_result_train(best_weights, error_now, best_error, delta_time)
    show_weights_sum(best_weights)


def run_noise_sensitivity(data, weights, step: float) -> None:
    """Запускает проверку устойчивости модели к шуму пользовательских оценок."""
    if len(data) == 0:
        print('Датасет пуст.')
        return

    delta = request.loop_input(
        text='Шум оценки [0.5] >> ',
        funcs_list=[valid.is_correct_noise_delta]
    )
    runs = request.loop_input(
        text='Количество повторов [100] >> ',
        funcs_list=[valid.is_correct_noise_runs]
    )

    if delta.strip() == "":
        delta = 0.5
    else:
        delta = valid.parse_float(delta)

    if runs.strip() == "":
        runs = 100
    else:
        runs = int(runs)

    start_time = time.perf_counter()
    result = noise_experiment.run_noise_experiment(
        data=data,
        weights=weights,
        delta=delta,
        runs=runs,
        fit_func=model.fit_weights,
        passes=1,
        step=step
    )
    delta_time = time.perf_counter() - start_time

    print('ПРОВЕРКА УСТОЙЧИВОСТИ К ШУМУ ОЦЕНОК')
    print('=' * 50)
    print(f'Шум оценки: +/- {result["delta"]}')
    print(f'Количество повторов: {result["runs"]}')
    print(f'MAE исходной модели: {round(result["original_mae_before"], 4)}')
    print(f'Средний MAE на зашумленных оценках: {round(result["avg_noisy_mae"], 4)}')
    print(
        'Средний MAE на исходных оценках после обучения на шуме: '
        f'{round(result["avg_original_mae_after_noise_training"], 4)}'
    )
    print(
        'Разброс MAE на исходных оценках после обучения на шуме: '
        f'{round(result["min_original_mae_after_noise_training"], 4)} .. '
        f'{round(result["max_original_mae_after_noise_training"], 4)}'
    )
    print(f'Время: {round(delta_time, 4)} сек.')

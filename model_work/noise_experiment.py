"""Запускает шумовые эксперименты для проверки устойчивости модели."""

import copy
import random

from model_work import model


def clamp_score(value: float) -> float:
    """Оставляет пользовательскую оценку в допустимом диапазоне 0..10."""
    return max(0.0, min(10.0, value))


def perturb_user_scores(data: dict, delta: float, rng: random.Random) -> dict:
    """Возвращает глубокую копию датасета со случайным шумом в пользовательских оценках."""
    noisy_data = copy.deepcopy(data)
    for movie in model.iter_movies(noisy_data):
        main_info = movie["main_info"]
        old_score = float(main_info["user_score"])
        main_info["user_score"] = clamp_score(old_score + rng.uniform(-delta, delta))
    return noisy_data


def run_noise_trial(
        data: dict,
        start_weights: dict,
        delta: float,
        fit_func,
        rng: random.Random,
        **fit_kwargs
) -> dict:
    """Запускает один прогон обучения и оценки на зашумленной копии датасета."""
    noisy_data = perturb_user_scores(data, delta, rng)
    noisy_weights = fit_func(noisy_data, start_weights, **fit_kwargs)
    noisy_weights = model.normalize_weights(noisy_weights)

    return {
        "noisy_mae": model.mean_absolute_error(noisy_data, noisy_weights),
        "original_mae": model.mean_absolute_error(data, noisy_weights),
        "weights": noisy_weights,
    }


def summarize_trials(trials: list) -> dict:
    """Собирает прогоны шумового эксперимента в итоговые метрики."""
    noisy_values = [trial["noisy_mae"] for trial in trials]
    original_values = [trial["original_mae"] for trial in trials]

    if len(trials) == 0:
        return {
            "avg_noisy_mae": 0,
            "avg_original_mae": 0,
            "min_original_mae": 0,
            "max_original_mae": 0,
        }

    return {
        "avg_noisy_mae": sum(noisy_values) / len(noisy_values),
        "avg_original_mae": sum(original_values) / len(original_values),
        "min_original_mae": min(original_values),
        "max_original_mae": max(original_values),
    }


def run_noise_experiment(
        data: dict,
        weights: dict,
        delta: float,
        runs: int,
        fit_func=model.fit_weights,
        seed: int = None,
        **fit_kwargs
) -> dict:
    """Проверяет, как обучение на шумных оценках влияет на попадание в исходный вкус."""
    if runs <= 0:
        raise ValueError("Количество повторов должно быть больше нуля")
    if delta < 0:
        raise ValueError("Шум оценки не может быть отрицательным")

    rng = random.Random(seed)
    original_mae_before = model.mean_absolute_error(data, weights)
    trials = [
        run_noise_trial(data, weights, delta, fit_func, rng, **fit_kwargs)
        for _ in range(runs)
    ]
    summary = summarize_trials(trials)

    return {
        "runs": runs,
        "delta": delta,
        "original_mae_before": original_mae_before,
        "avg_noisy_mae": summary["avg_noisy_mae"],
        "avg_original_mae_after_noise_training": summary["avg_original_mae"],
        "min_original_mae_after_noise_training": summary["min_original_mae"],
        "max_original_mae_after_noise_training": summary["max_original_mae"],
        "trials": trials,
    }

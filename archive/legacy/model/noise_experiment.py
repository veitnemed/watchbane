"""Noise benchmark helpers for model stability checks."""

import copy
import random

from model import linear_regression_train
from model import model


def clamp_score(value: float) -> float:
    """Clamp a user score to the supported 0..10 range."""
    return max(0.0, min(10.0, value))


def perturb_user_scores(data: dict, delta: float, rng: random.Random) -> dict:
    """Return a deep copy of the dataset with random user-score noise."""
    noisy_data = copy.deepcopy(data)
    for movie in model.iter_movies(noisy_data):
        main_info = movie["main_info"]
        old_score = float(main_info["user_score"])
        main_info["user_score"] = clamp_score(old_score + rng.uniform(-delta, delta))
    return noisy_data


def calculate_benchmark_loo_mae(data: dict, start_weights: dict) -> float | None:
    """Compute benchmark LOO MAE through the existing shared LOO implementation."""
    return linear_regression_train.calculate_linear_loo_mae(
        data=data,
        method=linear_regression_train.BENCHMARK_METHOD,
        start_weights=start_weights,
        alpha=linear_regression_train.BENCHMARK_RIDGE_ALPHA,
        l1_ratio=0.5,
        max_iter=5000,
    )


def run_noise_trial(
        data: dict,
        start_weights: dict,
        delta: float,
        fit_func,
        rng: random.Random,
        score_func,
        **fit_kwargs
) -> dict:
    """Run one noisy training/evaluation cycle."""
    noisy_data = perturb_user_scores(data, delta, rng)
    noisy_weights = fit_func(noisy_data, start_weights, **fit_kwargs)
    noisy_weights = model.normalize_weights(noisy_weights)

    return {
        "noisy_loo_mae": score_func(noisy_data, noisy_weights),
        "original_loo_mae": score_func(data, noisy_weights),
        "weights": noisy_weights,
    }


def summarize_trials(trials: list) -> dict:
    """Aggregate trial metrics."""
    noisy_values = [trial["noisy_loo_mae"] for trial in trials]
    original_values = [trial["original_loo_mae"] for trial in trials]

    if len(trials) == 0:
        return {
            "avg_noisy_loo_mae": 0,
            "avg_original_loo_mae": 0,
            "min_original_loo_mae": 0,
            "max_original_loo_mae": 0,
        }

    return {
        "avg_noisy_loo_mae": sum(noisy_values) / len(noisy_values),
        "avg_original_loo_mae": sum(original_values) / len(original_values),
        "min_original_loo_mae": min(original_values),
        "max_original_loo_mae": max(original_values),
    }


def run_noise_experiment(
        data: dict,
        weights: dict,
        delta: float,
        runs: int,
        fit_func=None,
        score_func=None,
        seed: int = None,
        progress_callback=None,
        **fit_kwargs
) -> dict:
    """Check how training on noisy ratings affects the model's taste fit."""
    if fit_func is None:
        def fit_func(train_data, start_weights, **_ignored):
            return linear_regression_train.train_ridge_for_benchmark(
                data=train_data,
                start_weights=start_weights,
            )
    if score_func is None:
        score_func = calculate_benchmark_loo_mae
    if runs <= 0:
        raise ValueError("Количество повторов должно быть больше нуля")
    if delta < 0:
        raise ValueError("Шум оценки не может быть отрицательным")

    rng = random.Random(seed)
    original_loo_mae_before = score_func(data, weights)
    trials = []
    for run_index in range(runs):
        if progress_callback is not None:
            progress_callback(run_index + 1, runs, delta)
        trials.append(
            run_noise_trial(data, weights, delta, fit_func, rng, score_func, **fit_kwargs)
        )
    summary = summarize_trials(trials)

    return {
        "runs": runs,
        "delta": delta,
        "original_loo_mae_before": original_loo_mae_before,
        "avg_noisy_loo_mae": summary["avg_noisy_loo_mae"],
        "avg_original_loo_mae_after_noise_training": summary["avg_original_loo_mae"],
        "min_original_loo_mae_after_noise_training": summary["min_original_loo_mae"],
        "max_original_loo_mae_after_noise_training": summary["max_original_loo_mae"],
        "trials": trials,
    }


def run_noise_sensitivity_grid(
        data: dict,
        weights: dict,
        deltas: list[float] | tuple[float, ...],
        runs: int,
        seed: int = 42,
        progress_callback=None,
) -> dict:
    """Runs noise experiment for each delta and returns aggregated grid results."""
    delta_list = list(deltas)
    if len(delta_list) == 0:
        raise ValueError("Список delta для noise grid пуст")

    original_loo_mae_before = calculate_benchmark_loo_mae(data, weights)
    results_by_delta = []

    for delta_index, delta in enumerate(delta_list, start=1):
        if progress_callback is not None:
            progress_callback("delta", delta_index, len(delta_list), delta, 0, runs)

        def trial_progress(run_index: int, total_runs: int, current_delta: float = delta) -> None:
            if progress_callback is not None:
                progress_callback("trial", delta_index, len(delta_list), current_delta, run_index, total_runs)

        result = run_noise_experiment(
            data=data,
            weights=weights,
            delta=delta,
            runs=runs,
            seed=seed + delta_index,
            progress_callback=trial_progress,
        )
        results_by_delta.append(result)

    return {
        "deltas": delta_list,
        "runs": runs,
        "seed": seed,
        "original_loo_mae_before": original_loo_mae_before,
        "results_by_delta": results_by_delta,
    }

"""Tests for the noise benchmark helpers."""

import copy
from pathlib import Path
import random
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config import constant
from common import format_score
from model import model
from model import linear_regression_train
from model import noise_experiment


def assert_check(text: str, result: bool) -> None:
    print(f"{text}: {result}")
    assert result, text


def make_movie(title: str, user_score: float, raw_score: float) -> dict:
    main_info = {
        "title": title,
        "user_score": user_score,
        "year": 2024,
    }
    raw_scores = {
        "kp_score": raw_score,
        "kp_votes": 100000,
        "imdb_score": raw_score,
        "imdb_votes": 50000,
    }
    tags_vibe = {feature: 0 for feature in constant.TAGS_VIBE}
    if constant.TAGS_VIBE:
        tags_vibe[constant.TAGS_VIBE[0]] = 1
    genre_tags = {feature: 0 for feature in constant.GENRE}
    for feature in ("has_drama", "has_crime"):
        if feature in genre_tags:
            genre_tags[feature] = 1

    return {
        "main_info": main_info,
        "raw_scores": raw_scores,
        "computed_scores": format_score.raw_to_struct(raw_scores, main_info),
        constant.TAGS_VIBE_SECTION: tags_vibe,
        constant.GENRE_SECTION: genre_tags,
    }


def make_dataset() -> dict:
    movies = [
        make_movie("A", 8.0, 8.0),
        make_movie("B", 5.0, 5.5),
        make_movie("C", 9.0, 8.5),
    ]
    return {movie["main_info"]["title"]: movie for movie in movies}


def test_perturb_does_not_mutate_source() -> None:
    data = make_dataset()
    original = copy.deepcopy(data)
    rng = random.Random(1)

    noisy = noise_experiment.perturb_user_scores(data, delta=1.0, rng=rng)

    assert_check("Source dataset stays unchanged", data == original)
    assert_check("Noisy dataset is a new object", noisy is not data)
    assert_check(
        "Noisy scores stay inside 0..10",
        all(0 <= movie["main_info"]["user_score"] <= 10 for movie in model.iter_movies(noisy)),
    )


def test_zero_delta_keeps_scores() -> None:
    data = make_dataset()
    noisy = noise_experiment.perturb_user_scores(data, delta=0, rng=random.Random(1))

    original_scores = [movie["main_info"]["user_score"] for movie in model.iter_movies(data)]
    noisy_scores = [movie["main_info"]["user_score"] for movie in model.iter_movies(noisy)]

    assert_check("Zero delta keeps user scores unchanged", noisy_scores == original_scores)


def test_noise_experiment_summary() -> None:
    if linear_regression_train.is_method_available(linear_regression_train.BENCHMARK_METHOD) is False:
        print("SKIP: Ridge benchmark is unavailable in the current environment.")
        return

    data = make_dataset()
    weights = constant.DEFAULT_WEIGHTS.copy()

    def fit_with_ridge(train_data, start_weights, **_ignored) -> dict:
        return linear_regression_train.train_ridge_for_benchmark(
            data=train_data,
            start_weights=start_weights,
        )

    result = noise_experiment.run_noise_experiment(
        data=data,
        weights=weights,
        delta=0.5,
        runs=5,
        fit_func=fit_with_ridge,
        seed=123,
    )

    expected_keys = {
        "runs",
        "delta",
        "original_loo_mae_before",
        "avg_noisy_loo_mae",
        "avg_original_loo_mae_after_noise_training",
        "min_original_loo_mae_after_noise_training",
        "max_original_loo_mae_after_noise_training",
        "trials",
    }

    assert_check("Result contains the expected metrics", set(result) == expected_keys)
    assert_check("Returned the expected number of trials", len(result["trials"]) == 5)
    assert_check("Average noisy LOO MAE is non-negative", result["avg_noisy_loo_mae"] >= 0)
    assert_check(
        "Original-data LOO MAE range is ordered",
        result["min_original_loo_mae_after_noise_training"]
        <= result["avg_original_loo_mae_after_noise_training"]
        <= result["max_original_loo_mae_after_noise_training"],
    )


def run_tests() -> None:
    print("=== Noise Benchmark Tests ===")
    test_perturb_does_not_mutate_source()
    test_zero_delta_keeps_scores()
    test_noise_experiment_summary()
    print("\nNoise benchmark checks passed: True")


if __name__ == "__main__":
    run_tests()

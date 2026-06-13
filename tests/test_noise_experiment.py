"""Тесты шумового эксперимента устойчивости модели."""

import copy
from pathlib import Path
import random
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config import constant
from core import format_score
from model_work import model
from model_work import noise_experiment


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

    return {
        "main_info": main_info,
        "raw_scores": raw_scores,
        "computed_scores": format_score.raw_to_struct(raw_scores, main_info),
        constant.TAGS_VIBE_SECTION: tags_vibe,
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

    assert_check("Исходный датасет не изменился", data == original)
    assert_check("Зашумленный датасет создан как новый объект", noisy is not data)
    assert_check("Зашумленные оценки остались в диапазоне 0..10", all(
        0 <= movie["main_info"]["user_score"] <= 10
        for movie in model.iter_movies(noisy)
    ))


def test_zero_delta_keeps_scores() -> None:
    data = make_dataset()
    noisy = noise_experiment.perturb_user_scores(data, delta=0, rng=random.Random(1))

    original_scores = [
        movie["main_info"]["user_score"]
        for movie in model.iter_movies(data)
    ]
    noisy_scores = [
        movie["main_info"]["user_score"]
        for movie in model.iter_movies(noisy)
    ]

    assert_check("Шум 0 сохраняет пользовательские оценки", noisy_scores == original_scores)


def test_noise_experiment_summary() -> None:
    data = make_dataset()
    weights = constant.DEFAULT_WEIGHTS.copy()
    result = noise_experiment.run_noise_experiment(
        data=data,
        weights=weights,
        delta=0.5,
        runs=5,
        fit_func=model.fit_weights,
        seed=123,
        passes=1,
        step=0.5,
    )

    expected_keys = {
        "runs",
        "delta",
        "original_mae_before",
        "avg_noisy_mae",
        "avg_original_mae_after_noise_training",
        "min_original_mae_after_noise_training",
        "max_original_mae_after_noise_training",
        "trials",
    }

    assert_check("Результат содержит ожидаемые метрики", set(result) == expected_keys)
    assert_check("Вернулось нужное количество прогонов", len(result["trials"]) == 5)
    assert_check("Средний MAE на шуме неотрицательный", result["avg_noisy_mae"] >= 0)
    assert_check(
        "Диапазон MAE на исходных оценках упорядочен",
        result["min_original_mae_after_noise_training"]
        <= result["avg_original_mae_after_noise_training"]
        <= result["max_original_mae_after_noise_training"]
    )


def run_tests() -> None:
    print("=== Тесты шумового эксперимента ===")
    test_perturb_does_not_mutate_source()
    test_zero_delta_keeps_scores()
    test_noise_experiment_summary()
    print("\nПроверки шумового эксперимента пройдены: True")


if __name__ == "__main__":
    run_tests()

import copy
import json
import tempfile
from pathlib import Path

import pytest

from common import format_score
from config import constant
from config import scheme


def _make_movie(title: str, user_score: float, year: int, raw_score: float = 8.0) -> dict:
    raw_scores = {
        "kp_score": raw_score,
        "kp_votes": 120000,
        "imdb_score": raw_score,
        "imdb_votes": 1200,
    }
    main_info = {
        "title": title,
        "user_score": user_score,
        "year": year,
    }
    return {
        "main_info": main_info,
        "raw_scores": raw_scores,
        "computed_scores": format_score.raw_to_struct(raw_scores, main_info),
        scheme.TAGS_VIBE: {feature: 0 for feature in constant.TAGS_VIBE},
        constant.GENRE_SECTION: {feature: 0 for feature in constant.GENRE},
    }


def _patch_storage_paths(monkeypatch, root: Path) -> None:
    monkeypatch.setattr(constant, "MODEL_METRICS_JSON", str(root / "model_metrics.json"))
    monkeypatch.setattr(constant, "WEIGHTS_JSON", str(root / "weights.json"))
    monkeypatch.setattr(constant, "FILE_NAME", str(root / "dataset.json"))


def test_save_weights_after_explicit_loo_training_saves_worse_loo_and_clears_stale(
    monkeypatch,
) -> None:
    from model import model
    from storage import data as storage_data

    new_weights = copy.deepcopy(constant.DEFAULT_WEIGHTS)
    new_weights["bias"] = 0.42

    with tempfile.TemporaryDirectory() as temp_root:
        root = Path(temp_root)
        _patch_storage_paths(monkeypatch, root)
        storage_data.init_model_metrics()
        storage_data.save_weights(constant.DEFAULT_WEIGHTS)
        storage_data.save_model_metrics(
            {
                "loo_mae": 0.5,
                "is_stale": True,
                "stale_reason": "user_score_changed",
            }
        )

        result = model.save_weights_after_explicit_loo_training(
            new_weights=new_weights,
            new_loo_mae=0.82,
            source_name="LOO обучение",
        )

        metrics = storage_data.get_model_metrics_status()
        saved_weights = storage_data.load_weights()

    assert result["saved"] is True
    assert result["previous_loo_mae"] == 0.5
    assert result["previous_is_stale"] is True
    assert result["previous_stale_reason"] == "user_score_changed"
    assert result["new_loo_mae"] == 0.82
    assert result["delta"] == pytest.approx(0.32)
    assert metrics["loo_mae"] == 0.82
    assert metrics["is_stale"] is False
    assert metrics["stale_reason"] is None
    assert metrics["updated_at"] is not None
    assert saved_weights["bias"] == 0.42


def test_save_weights_if_loo_improved_still_rejects_worse_loo(monkeypatch) -> None:
    from model import model
    from storage import data as storage_data

    new_weights = copy.deepcopy(constant.DEFAULT_WEIGHTS)
    new_weights["bias"] = 0.99
    dataset = {"Alpha": _make_movie("Alpha", 8.0, 2020)}

    with tempfile.TemporaryDirectory() as temp_root:
        root = Path(temp_root)
        _patch_storage_paths(monkeypatch, root)
        storage_data.init_model_metrics()
        storage_data.save_weights(constant.DEFAULT_WEIGHTS)
        storage_data.save_model_metrics({"loo_mae": 0.5, "is_stale": False})

        saved = model.save_weights_if_loo_improved(
            new_weights=new_weights,
            dataset=dataset,
            new_loo_mae=0.8,
            source_name="Линейное обучение",
        )
        metrics = storage_data.get_model_metrics_status()
        current_weights = storage_data.load_weights()

    assert saved is False
    assert metrics["loo_mae"] == 0.5
    assert current_weights["bias"] == constant.DEFAULT_WEIGHTS["bias"]


def test_run_loo_training_does_not_save_on_small_dataset(monkeypatch) -> None:
    from model import linear_regression_train
    from storage import data as storage_data

    save_calls: list[tuple] = []

    def fake_save(*args, **kwargs):
        save_calls.append((args, kwargs))
        return {"saved": True, "new_loo_mae": kwargs.get("new_loo_mae")}

    monkeypatch.setattr(
        linear_regression_train.model,
        "save_weights_after_explicit_loo_training",
        fake_save,
    )

    with tempfile.TemporaryDirectory() as temp_root:
        root = Path(temp_root)
        _patch_storage_paths(monkeypatch, root)
        storage_data.init_model_metrics()
        storage_data.save_model_metrics({"loo_mae": 0.5, "is_stale": True})

        dataset = {
            "Alpha": _make_movie("Alpha", 8.0, 2020),
            "Bravo": _make_movie("Bravo", 7.0, 2019),
        }
        linear_regression_train.run_loo_training(dataset, constant.DEFAULT_WEIGHTS)
        metrics = storage_data.get_model_metrics_status()

    assert save_calls == []
    assert metrics["loo_mae"] == 0.5
    assert metrics["is_stale"] is True


def test_run_loo_training_saves_via_explicit_policy(monkeypatch) -> None:
    from model import linear_regression_train
    from storage import data as storage_data

    save_calls: list[tuple] = []

    def fake_calculate_linear_loo_mae(**_kwargs) -> float:
        return 0.9

    def fake_train_ridge_for_benchmark(**_kwargs) -> dict:
        weights = copy.deepcopy(constant.DEFAULT_WEIGHTS)
        weights["bias"] = 0.77
        return weights

    def fake_save(new_weights, new_loo_mae, **kwargs):
        save_calls.append((new_weights, new_loo_mae, kwargs))
        storage_data.save_weights(new_weights)
        storage_data.set_saved_loo_mae(new_loo_mae)
        return {
            "saved": True,
            "previous_loo_mae": 0.5,
            "previous_is_stale": True,
            "previous_stale_reason": "user_score_changed",
            "new_loo_mae": new_loo_mae,
            "delta": new_loo_mae - 0.5,
        }

    monkeypatch.setattr(linear_regression_train, "calculate_linear_loo_mae", fake_calculate_linear_loo_mae)
    monkeypatch.setattr(linear_regression_train, "train_ridge_for_benchmark", fake_train_ridge_for_benchmark)
    monkeypatch.setattr(
        linear_regression_train.model,
        "save_weights_after_explicit_loo_training",
        fake_save,
    )
    monkeypatch.setattr(linear_regression_train, "print_baseline_comparison", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(linear_regression_train, "print_weights_summary", lambda *_args, **_kwargs: None)

    dataset = {
        "Alpha": _make_movie("Alpha", 8.0, 2020),
        "Bravo": _make_movie("Bravo", 7.0, 2019),
        "Charlie": _make_movie("Charlie", 6.0, 2018),
    }

    with tempfile.TemporaryDirectory() as temp_root:
        root = Path(temp_root)
        _patch_storage_paths(monkeypatch, root)
        storage_data.init_model_metrics()
        storage_data.save_model_metrics(
            {
                "loo_mae": 0.5,
                "is_stale": True,
                "stale_reason": "user_score_changed",
            }
        )

        linear_regression_train.run_loo_training(dataset, constant.DEFAULT_WEIGHTS)
        metrics = storage_data.get_model_metrics_status()
        saved_weights = storage_data.load_weights()

    assert len(save_calls) == 1
    assert save_calls[0][1] == 0.9
    assert metrics["loo_mae"] == 0.9
    assert metrics["is_stale"] is False
    assert saved_weights["bias"] == 0.77

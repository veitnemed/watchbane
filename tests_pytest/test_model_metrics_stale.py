import copy
import json

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


def test_old_model_metrics_json_reads_as_fresh(tmp_path, monkeypatch) -> None:
    from storage import data as storage_data

    metrics_path = tmp_path / "model_metrics.json"
    metrics_path.write_text(json.dumps({"loo_mae": 0.7366}), encoding="utf-8")
    monkeypatch.setattr(constant, "MODEL_METRICS_JSON", str(metrics_path))

    metrics = storage_data.load_model_metrics()

    assert metrics["loo_mae"] == 0.7366
    assert metrics["is_stale"] is False
    assert metrics["stale_reason"] is None
    assert metrics["updated_at"] is None
    assert metrics["dataset_changed_at"] is None


def test_mark_model_metrics_stale_sets_status(tmp_path, monkeypatch) -> None:
    from storage import data as storage_data

    metrics_path = tmp_path / "model_metrics.json"
    monkeypatch.setattr(constant, "MODEL_METRICS_JSON", str(metrics_path))
    storage_data.save_model_metrics({"loo_mae": 0.5})

    storage_data.mark_model_metrics_stale("user_score_changed")
    metrics = storage_data.get_model_metrics_status()

    assert metrics["loo_mae"] == 0.5
    assert metrics["is_stale"] is True
    assert metrics["stale_reason"] == "user_score_changed"
    assert metrics["dataset_changed_at"] is not None


def test_set_saved_loo_mae_resets_stale_status(tmp_path, monkeypatch) -> None:
    from storage import data as storage_data

    metrics_path = tmp_path / "model_metrics.json"
    monkeypatch.setattr(constant, "MODEL_METRICS_JSON", str(metrics_path))
    storage_data.save_model_metrics({"loo_mae": 0.8, "is_stale": True, "stale_reason": "dataset_changed"})

    storage_data.set_saved_loo_mae(0.7)
    metrics = storage_data.get_model_metrics_status()

    assert metrics["loo_mae"] == 0.7
    assert metrics["is_stale"] is False
    assert metrics["stale_reason"] is None
    assert metrics["updated_at"] is not None
    assert metrics["dataset_changed_at"] is None


def test_update_dataset_record_marks_metrics_stale_for_user_score(monkeypatch) -> None:
    from dataset import dataset_records

    dataset = {"Alpha": _make_movie("Alpha", 8.0, 2020)}
    saved = {}
    stale_reasons = []

    monkeypatch.setattr(dataset_records, "load_dataset", lambda: copy.deepcopy(dataset))
    monkeypatch.setattr(dataset_records, "save_dataset", lambda payload: saved.update(payload))
    monkeypatch.setattr(dataset_records.storage_data, "mark_model_metrics_stale", lambda reason: stale_reasons.append(reason))

    result = dataset_records.update_dataset_record("Alpha", {"main_info": {"user_score": 8.5}})

    assert result.ok is True
    assert result.changed_fields == ["main_info.user_score"]
    assert saved["Alpha"]["main_info"]["user_score"] == 8.5
    assert stale_reasons == ["user_score_changed"]


def test_update_dataset_record_does_not_mark_stale_for_non_score_change(monkeypatch) -> None:
    from dataset import dataset_records

    dataset = {"Alpha": _make_movie("Alpha", 8.0, 2020)}
    stale_reasons = []

    monkeypatch.setattr(dataset_records, "load_dataset", lambda: copy.deepcopy(dataset))
    monkeypatch.setattr(dataset_records, "save_dataset", lambda _payload: None)
    monkeypatch.setattr(dataset_records.storage_data, "mark_model_metrics_stale", lambda reason: stale_reasons.append(reason))

    result = dataset_records.update_dataset_record("Alpha", {"main_info": {"year": 2021}})

    assert result.ok is True
    assert result.changed_fields == ["main_info.year"]
    assert stale_reasons == []


def test_console_loo_display_marks_stale() -> None:
    from ui.console.ui import format_loo_mae_display

    assert format_loo_mae_display(0.7366, {"is_stale": False}) == "LOO MAE: 0.7366"
    assert format_loo_mae_display(0.7366, {"is_stale": True}) == "LOO MAE: 0.7366 (устарело после изменения dataset)"
    assert format_loo_mae_display(None, {"is_stale": True}) == "LOO MAE: не рассчитан"

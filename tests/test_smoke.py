import json
import tempfile
from pathlib import Path


def test_tmp_path_can_write_utf8_json() -> None:
    payload = {"title": "Во все тяжкие"}

    with tempfile.TemporaryDirectory() as temp_root:
        path = Path(temp_root) / "test.json"
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        raw_text = path.read_text(encoding="utf-8")

    assert "Во все тяжкие" in raw_text
    assert "\\u0412" not in raw_text


def test_storage_data_has_no_model_artifact_api() -> None:
    from config import constant
    from storage import data as storage_data

    for name in (
        "init_weights",
        "load_weights",
        "save_weights",
        "uppdate_weights",
        "init_model_metrics",
        "load_model_metrics",
        "save_model_metrics",
        "get_model_metrics_status",
        "get_saved_loo_mae",
        "set_saved_loo_mae",
        "mark_model_metrics_stale",
    ):
        assert hasattr(storage_data, name) is False

    assert hasattr(constant, "WEIGHTS_JSON") is False
    assert hasattr(constant, "MODEL_METRICS_JSON") is False
    assert hasattr(constant, "DEFAULT_WEIGHTS") is False

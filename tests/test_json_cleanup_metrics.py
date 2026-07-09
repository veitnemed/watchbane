from __future__ import annotations

from scripts.reports.json_cleanup_metrics import collect_metrics


def test_json_cleanup_metrics_reports_cleanup_baseline() -> None:
    metrics = collect_metrics()

    assert set(metrics) == {
        "python_loc_storage_candidates_dataset_app_core",
        "json_runtime_reference_count",
        "backend_switch_reference_count",
    }
    assert metrics["python_loc_storage_candidates_dataset_app_core"] > 0
    assert metrics["json_runtime_reference_count"] > 0
    assert metrics["backend_switch_reference_count"] == 0

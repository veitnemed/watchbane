from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.research.trace_tmdb_adult_propagation import fixture_traces, run_audit
from tools.qa.isolation import IsolationError


def _by_scenario(traces: list[dict], name: str) -> dict:
    return next(trace for trace in traces if trace["scenario"] == name)


def test_fixture_traces_keep_tri_state_adult_through_both_details_paths(tmp_path: Path) -> None:
    traces = fixture_traces(tmp_path / "isolated")
    true_trace = _by_scenario(traces, "adult_true")
    false_trace = _by_scenario(traces, "adult_false")
    null_trace = _by_scenario(traces, "adult_null")

    assert true_trace["paths"]["full_details"]["adult_value_matches_raw"] is True
    assert true_trace["paths"]["full_details"]["stored_value_matches_normalized"] is True
    assert false_trace["paths"]["full_details"]["stored_value_matches_normalized"] is True
    assert null_trace["paths"]["full_details"]["stored_value_matches_normalized"] is True
    assert true_trace["paths"]["full_details"]["loss_layer"] is None
    assert true_trace["paths"]["full_details"]["eligibility"]["adult_based_blocked"] is True
    assert false_trace["paths"]["full_details"]["eligibility"]["adult_based_blocked"] is False
    assert null_trace["paths"]["full_details"]["eligibility"]["adult_based_blocked"] is False
    for trace in (true_trace, false_trace, null_trace):
        merged = trace["paths"]["filter_details_merge"]
        assert merged["stored_value_matches_normalized"] is True
        assert merged["loss_layer"] is None
    assert true_trace["paths"]["filter_details_merge"]["eligibility"]["adult_based_blocked"] is True
    assert false_trace["paths"]["filter_details_merge"]["eligibility"]["adult_based_blocked"] is False
    assert null_trace["paths"]["filter_details_merge"]["eligibility"]["adult_based_blocked"] is False


def test_run_audit_isolated_and_evidence_has_no_title_or_tmdb_id(tmp_path: Path) -> None:
    output = tmp_path / "evidence"
    payload = run_audit(
        tmp_path / "isolated",
        output=output,
        movie_id=123,
        fetch_details=lambda _: {"id": 123, "adult": False, "title": "Live title", "release_date": "2020-01-01"},
    )
    text = (output / "adult_trace.json").read_text(encoding="utf-8")
    assert payload["live_status"] == "ok"
    assert "Live title" not in text
    assert "123" not in text
    assert (tmp_path / "isolated" / ".watchbane_qa_isolated").is_file()
    assert json.loads((output / "summary.json").read_text(encoding="utf-8"))["loss_count"] == 0


def test_run_audit_rejects_production_runtime(tmp_path: Path) -> None:
    with pytest.raises(IsolationError):
        run_audit(
            Path.home(), output=tmp_path / "evidence", movie_id=1, fetch_details=lambda _: {},
        )

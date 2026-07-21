"""Offline contract tests for the static TMDb tracing snapshot fixtures."""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "research" / "tmdb"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _assert_valid(instance: dict, schema: dict) -> None:
    errors = sorted(Draft202012Validator(schema).iter_errors(instance), key=str)
    assert not errors, "\n".join(error.message for error in errors)


def test_manifest_and_all_snapshot_fixtures_validate() -> None:
    snapshot_schema = _load(RESEARCH / "schema.json")
    manifest_schema = _load(RESEARCH / "sample_manifest.schema.json")
    manifest = _load(RESEARCH / "sample_manifest.json")

    _assert_valid(manifest, manifest_schema)
    assert {entry["media_type"] for entry in manifest["fixtures"]} == {"movie", "tv"}
    assert len(manifest["fixtures"]) == 3

    for entry in manifest["fixtures"]:
        snapshot = _load(RESEARCH / entry["file"])
        _assert_valid(snapshot, snapshot_schema)
        assert snapshot["snapshot_id"] == entry["snapshot_id"]
        assert snapshot["sample_group"] == entry["sample_group"]
        assert set(snapshot["layers"]) == {"raw_api", "normalized", "stored", "ui_projection"}
        assert set(snapshot["layers"]["stored"]) >= {"sql_columns", "payload_fields", "meta_fields"}


def test_special_provenance_and_known_losses_are_explicit() -> None:
    movie = _load(RESEARCH / "fixtures" / "movie_watched_refresh_losses.json")
    tv = _load(RESEARCH / "fixtures" / "tv_content_ratings_aggregate_credits.json")
    localized = _load(RESEARCH / "fixtures" / "localization_en_fallback.json")

    assert movie["diagnostics"]["adult"]["adult_lost_in_normalization"] is False
    assert movie["field_traces"]["certification"]["normalized"]["state"] == "lost_in_normalization"
    assert movie["field_traces"]["credits"]["stored"]["state"] == "lost_in_normalization"

    assert tv["diagnostics"]["tv_runtime"] == {
        "episode_run_time_raw": [24, 48],
        "episode_run_time_selected": 24,
        "selection_strategy": "first_value",
    }
    assert tv["provenance"]["certification"]["source_region"] == "RU"
    assert tv["diagnostics"]["credits"]["raw_credits_type"] == "aggregate_credits"

    assert localized["field_traces"]["title"]["raw_api"]["state"] == "empty"
    assert localized["field_traces"]["overview"]["raw_api"]["state"] == "empty"
    assert localized["provenance"]["title"]["fallback_level"] == "english"
    assert localized["provenance"]["overview"]["selected_value"] == "English fallback overview"

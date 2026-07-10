import json
from pathlib import Path

from candidates.replenish.report import (
    build_filter_replenish_report_payload,
    sanitize_filter_replenish_report,
    write_filter_replenish_report,
)


def _result() -> dict:
    return {
        "ok": True,
        "requested_count": 30,
        "created_count": 2,
        "saved_count": 2,
        "duplicate_count": 1,
        "watched_skipped": 1,
        "hidden_skipped": 0,
        "rejected_count": 0,
        "api_requests": 2,
        "details_requests": 2,
        "before_pool_count": 3,
        "after_pool_count": 5,
        "compatibility": {"can_run": True, "warnings": [], "blocking_conflicts": []},
        "plan": {
            "intent": {"countries": ["RU"], "media_type": "tv"},
            "target_add_count": 30,
            "bucket_count": 1,
            "country_plan": {"RU": 30},
            "media_plan": {"tv": 30},
            "broad_origin_allowed": False,
        },
        "bucket_results": [{"bucket_id": "RU:tv:1", "accepted_count": 2}],
        "discover_params_sample": [
            {
                "include_adult": False,
                "sort_by": "popularity.desc",
                "with_origin_country": "RU",
                "without_genres": "16,10764",
            }
        ],
        "candidates": [
            {"title": "Alpha", "year": 2024, "media_type": "tv", "tmdb_id": 10},
            {"title": "Beta", "year": 2023, "media_type": "tv", "tmdb_id": 11},
        ],
    }


def test_report_payload_contains_required_fields_and_guardrail_flag() -> None:
    payload = build_filter_replenish_report_payload(
        _result(),
        timestamp="2026-07-10T00:00:00+00:00",
        elapsed_ms=12.5,
    )

    assert payload["timestamp"] == "2026-07-10T00:00:00+00:00"
    assert payload["normalized_intent"] == {"countries": ["RU"], "media_type": "tv"}
    assert payload["plan_summary"]["country_plan"] == {"RU": 30}
    assert payload["before_pool_count"] == 3
    assert payload["after_pool_count"] == 5
    assert payload["requested"] == 30
    assert payload["created"] == 2
    assert payload["saved"] == 2
    assert payload["duplicates"] == 1
    assert payload["watched_skipped"] == 1
    assert payload["api_requests"] == 2
    assert payload["details_requests"] == 2
    assert payload["elapsed_ms"] == 12.5
    assert payload["added_sample"][0]["title"] == "Alpha"
    assert payload["no_vote_rating_discover_filters"] is True


def test_report_payload_detects_vote_rating_guardrail_violation() -> None:
    result = _result()
    result["discover_params_sample"] = [{"vote_count.gte": 100}]

    payload = build_filter_replenish_report_payload(result)

    assert payload["no_vote_rating_discover_filters"] is False


def test_write_filter_replenish_report_writes_latest_and_jsonl(tmp_path) -> None:
    paths = write_filter_replenish_report(
        _result(),
        output_dir=tmp_path,
        timestamp="2026-07-10T00:00:00+00:00",
    )
    write_filter_replenish_report(
        _result(),
        output_dir=tmp_path,
        timestamp="2026-07-10T00:00:01+00:00",
    )

    json_path = Path(paths["json_path"])
    markdown_path = Path(paths["markdown_path"])
    jsonl_path = Path(paths["jsonl_path"])

    assert json_path.name == "filter_replenish_latest.json"
    assert markdown_path.name == "filter_replenish_latest.md"
    assert jsonl_path.name == "filter_replenish_runs.jsonl"
    assert json_path.exists()
    assert markdown_path.exists()
    assert jsonl_path.exists()

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")
    jsonl_lines = jsonl_path.read_text(encoding="utf-8").splitlines()

    assert payload["timestamp"] == "2026-07-10T00:00:01+00:00"
    assert "# Filter Replenish Latest Run" in markdown
    assert "no_vote_rating_discover_filters: True" in markdown
    assert len(jsonl_lines) == 2


def test_report_sanitization_removes_tokens_paths_and_full_watched_lists() -> None:
    payload = sanitize_filter_replenish_report(
        {
            "api_token": "secret-token",
            "runtime_db_path": r"D:\Users\me\data\watchbane.sqlite3",
            "full_watched_records": [{"title": "Private"}],
            "nested": {
                "authorization": "Bearer secret",
                "path": r"D:\Users\me\data\other.sqlite3",
            },
        }
    )

    assert payload["api_token"] == "<redacted_secret>"
    assert payload["runtime_db_path"] == "<redacted_path>"
    assert payload["full_watched_records"] == "<redacted_watched_list>"
    assert payload["nested"]["authorization"] == "<redacted_secret>"
    assert payload["nested"]["path"] == "<redacted_path>"

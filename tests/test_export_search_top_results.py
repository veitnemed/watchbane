"""Tests for the offline search top-results export script."""

from __future__ import annotations

import json

import scripts.reports.export_search_top_results as export


def _pool() -> list[dict]:
    return [
        {"tmdb_id": 1, "title": "Криминальный сериал", "final_score": 0.9, "quality_score": 0.8, "year": 2020},
        {"tmdb_id": 2, "title": "Комедия", "final_score": 0.6, "quality_score": 0.5, "year": 2019},
        {"tmdb_id": 3, "title": "Криминальная драма", "final_score": 0.8, "quality_score": 0.7, "year": 2021},
    ]


def _patch_pipeline(monkeypatch, pool: list[dict]) -> None:
    monkeypatch.setattr(
        export.candidate_service,
        "get_search_overview_view",
        lambda: {"is_empty": False, "candidates": list(pool)},
    )
    monkeypatch.setattr(
        export.candidate_service,
        "search_candidate_pool",
        lambda candidates, filters: {"candidates": list(candidates), "filtered_count": len(candidates)},
    )
    monkeypatch.setattr(
        export.candidate_service,
        "sort_search_candidates",
        lambda candidates, sort_mode: {
            "candidates": sorted(candidates, key=lambda item: item.get("final_score") or 0, reverse=True),
            "hidden_duplicates": 0,
        },
    )


def test_export_writes_json_with_ranked_items(tmp_path, monkeypatch) -> None:
    _patch_pipeline(monkeypatch, _pool())
    output = tmp_path / "review.json"

    code = export.main(["--top", "50", "--output", str(output)])

    assert code == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["count"] == 3
    items = payload["items"]
    assert [item["rank"] for item in items] == [1, 2, 3]
    assert items[0]["tmdb_id"] == 1
    assert items[0]["title"] == "Криминальный сериал"
    assert items[0]["final_score"] == 0.9
    assert items[0]["review"] is None
    assert [item["final_score"] for item in items] == [0.9, 0.8, 0.6]


def test_export_applies_query_substring_filter(tmp_path, monkeypatch) -> None:
    _patch_pipeline(monkeypatch, _pool())
    monkeypatch.setattr(export.candidate_service, "is_fts_search_enabled", lambda: False)
    output = tmp_path / "review.json"

    export.main(["--query", "криминаль", "--output", str(output)])

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["query"] == "криминаль"
    titles = [item["title"] for item in payload["items"]]
    assert "Комедия" not in titles
    assert set(titles) == {"Криминальный сериал", "Криминальная драма"}


def test_export_respects_top_limit(tmp_path, monkeypatch) -> None:
    _patch_pipeline(monkeypatch, _pool())
    output = tmp_path / "review.json"

    export.main(["--top", "1", "--output", str(output)])

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["count"] == 1
    assert payload["items"][0]["tmdb_id"] == 1


def test_export_output_has_no_absolute_paths(tmp_path, monkeypatch) -> None:
    _patch_pipeline(monkeypatch, _pool())
    output = tmp_path / "review.json"

    export.main(["--output", str(output)])

    raw = output.read_text(encoding="utf-8")
    payload = json.loads(raw)
    assert "secret" not in raw
    for item in payload["items"]:
        assert set(["rank", "tmdb_id", "title", "final_score"]).issubset(item.keys())

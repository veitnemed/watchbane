import json

from tools.reports.run_filter_replenish_quality_report import (
    build_quality_report,
    main,
    run_mock_scenario,
)


def test_quality_report_all_mock_scenarios_have_expected_counts() -> None:
    report = build_quality_report([
        "ru_dark_tv",
        "anime_jp",
        "k_drama_kr",
        "us_gb_new_movies",
        "sparse_tr",
        "duplicate_heavy",
    ])
    rows = {row["scenario"]: row for row in report["rows"]}

    assert report["scenario_count"] == 6
    assert rows["ru_dark_tv"]["saved_count"] == 30
    assert rows["anime_jp"]["saved_count"] == 30
    assert rows["k_drama_kr"]["saved_count"] == 30
    assert rows["us_gb_new_movies"]["saved_count"] == 30
    assert rows["sparse_tr"]["saved_count"] == 5
    assert rows["sparse_tr"]["fill_rate"] < 1.0
    assert rows["duplicate_heavy"]["saved_count"] == 14
    assert rows["duplicate_heavy"]["duplicate_count"] == 8
    assert report["summary"]["guardrail_violations"] == 0


def test_quality_metrics_match_country_media_animation_and_no_leaks() -> None:
    anime = run_mock_scenario("anime_jp")
    us_gb = run_mock_scenario("us_gb_new_movies")
    duplicate = run_mock_scenario("duplicate_heavy")

    assert anime["country_match_rate"] == 1.0
    assert anime["media_match_rate"] == 1.0
    assert anime["animation_match_rate"] == 1.0
    assert us_gb["country_match_rate"] == 1.0
    assert us_gb["media_match_rate"] == 1.0
    assert duplicate["existing_pool_duplicate_leak_count"] == 0
    assert duplicate["watched_leak_count"] == 0


def test_quality_report_cli_writes_markdown_and_json(tmp_path, capsys) -> None:
    output = tmp_path / "quality.md"
    json_output = tmp_path / "quality.json"

    exit_code = main([
        "--mock",
        "--scenario",
        "sparse_tr",
        "--output",
        str(output),
        "--json-output",
        str(json_output),
    ])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert output.exists()
    assert json_output.exists()
    assert "Mock Filter Replenish Quality Report" in output.read_text(encoding="utf-8")
    assert "Sparse TR" in captured.out

    payload = json.loads(json_output.read_text(encoding="utf-8"))
    assert payload["scenario_count"] == 1
    assert payload["rows"][0]["scenario"] == "sparse_tr"
    assert payload["rows"][0]["broad_origin_fallback_count"] == 0

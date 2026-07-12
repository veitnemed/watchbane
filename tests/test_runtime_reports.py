import sys
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

from diagnostics import runtime_reports
from tools.reports import onboarding_compare_report
from tools.reports import run_onboarding_discover_quality_report as onboarding_report

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass
class FakeBundle:
    title: str = "Alpha"
    country: str = "Россия"
    found: bool = True
    statuses: dict | None = None
    preview_card: dict | None = None
    defaults: dict | None = None
    meta_payload: dict | None = None
    poster_hints: dict | None = None


def _fake_bundle() -> FakeBundle:
    return FakeBundle(
        statuses={"sql": "найдено", "kp_api": "лимит", "tmdb_api": "найдено"},
        preview_card={"title": "Alpha", "year": 2024, "kp_votes": 1000, "imdb_votes": 200},
        defaults={"main_info": {"title": "Alpha"}},
        meta_payload={"tmdb_id": 10},
        poster_hints={"poster_url": "https://example.test/poster.jpg"},
    )


def test_write_report_creates_json_and_text(tmp_path) -> None:
    report = {
        "scenario": "unit",
        "status": "ok",
        "started_at": "2026-01-01T00:00:00+00:00",
        "finished_at": "2026-01-01T00:00:01+00:00",
        "duration_seconds": 1.0,
        "inputs": {"title": "Alpha"},
        "progress": [{"current": 1, "total": 2, "message": "step"}],
        "result": {"found": True},
    }

    files = runtime_reports.write_report(report, tmp_path)

    assert files["json_path"].endswith(".json")
    assert files["text_path"].endswith(".txt")
    assert "Alpha" in Path(files["json_path"]).read_text(encoding="utf-8")
    assert "Progress:" in Path(files["text_path"]).read_text(encoding="utf-8")


def test_run_add_title_report_records_progress_without_network(tmp_path) -> None:
    def fake_resolver(title, country, on_progress=None):
        on_progress(1, 7, "IMDb dataset: Поиск")
        on_progress(7, 7, "Подготовка: Готово")
        return _fake_bundle()

    report = runtime_reports.run_add_title_report(
        "Alpha",
        "Россия",
        reports_dir=tmp_path,
        resolver=fake_resolver,
    )

    assert report["status"] == "ok"
    assert report["result"]["statuses"]["kp_api"] == "лимит"
    assert report["progress"][-1]["message"] == "Подготовка: Готово"


def test_run_command_report_captures_stdout(tmp_path) -> None:
    report = runtime_reports.run_command_report(
        "hello",
        [sys.executable, "-c", "print('hello report')"],
        reports_dir=tmp_path,
    )

    assert report["status"] == "ok"
    assert "hello report" in report["stdout"]


def test_onboarding_candidate_sample_schema_includes_vote_confidence_and_quality() -> None:
    row = onboarding_report._candidate_row(
        {
            "title": "Alpha",
            "year": 2024,
            "media_type": "movie",
            "target_country": "US",
            "tmdb_score": 7.5,
            "tmdb_votes": 12,
            "overview_source": "en-US",
            "quality_class": "weak",
            "quality_reasons": ["low_votes"],
            "final_score": 9.1,
            "score_debug": {"vote_confidence": 0.45},
        }
    )

    assert row["rating"] == 7.5
    assert row["votes"] == 12
    assert row["vote_confidence"] == 0.45
    assert row["overview_source"] == "en-US"
    assert row["quality_class"] == "weak"


def test_onboarding_report_summary_schema_includes_details_and_localization_metrics() -> None:
    candidates = [
        {
            "media_type": "movie",
            "tmdb_votes": 5,
            "quality_class": "weak",
            "quality_reasons": ["low_votes"],
            "score_debug": {"vote_confidence": 0.25},
        },
        {
            "media_type": "movie",
            "tmdb_votes": 500,
            "quality_class": "good",
            "quality_reasons": [],
            "score_debug": {"vote_confidence": 1.0},
        },
    ]
    candidate_metrics = onboarding_report._candidate_metrics(candidates)
    result = SimpleNamespace(
        planned_counts={"country": {"US": 2}, "media_type": {"movie": 2}},
        actual_counts={"media_type": {"movie": 2}},
        details_requests=4,
        localization_fallback_count=2,
        overview_fallback_original_language_count=1,
        overview_fallback_en_count=1,
        missing_overview_after_fallback=0,
        adaptive_pages_used=1,
        pagination_stop_reasons={"quota_full": 1},
        quality_gate_rejected_counts={"garbage": 2},
        quality_gate_rejected_reasons={"missing_overview_low_confidence": 2},
        preference_diagnostics={
            "preference_conflict_count": 1,
            "preference_warning_count": 1,
            "preference_conflict_codes": ["anime_requires_animation_only"],
            "auto_fix_applied": True,
            "selected_preset_before": "anime",
            "selected_preset_after": "anime",
            "countries_before": ["RU"],
            "countries_after": ["JP", "RU"],
            "animation_mode_before": "live_action_only",
            "animation_mode_after": "animation_only",
        },
    )
    summary = onboarding_report._report_schema_summary(
        profile={
            "country_selection": {"selected_countries": ["US"]},
            "details_enrichment": {"enabled": True, "fetch_external_ids": True},
        },
        result=result,
        country_metrics={
            "country_actual": {"US": 2},
            "country_hit_rate": 1.0,
            "country_leakage_count": 0,
        },
        candidate_metrics=candidate_metrics,
        api_budget_metrics={
            "discover_templates_count": 2,
            "discover_http_requests": 3,
            "broad_origin_requests": 0,
            "fallback_used": False,
        },
        request_rows=[],
        request_diagnostics={
            "request_timeout_count": 1,
            "request_retry_count": 1,
            "request_outlier_count": 1,
            "max_request_ms": 125.0,
            "p95_request_ms": 125.0,
        },
    )

    assert summary["details_requests"] == 4
    assert summary["external_ids_requests"] == 4
    assert summary["details_enrichment_enabled"] is True
    assert summary["localization_fallback_count"] == 2
    assert summary["overview_fallback_original_language_count"] == 1
    assert summary["overview_fallback_en_count"] == 1
    assert summary["vote_confidence_avg"] == 0.625
    assert summary["weak_candidates_count"] == 1
    assert summary["quality_gate_garbage_rejected_count"] == 2
    assert summary["quality_gate_rejected_reasons"] == {"missing_overview_low_confidence": 2}
    assert summary["quality_class_distribution"] == {"weak": 1, "good": 1, "rejected_garbage": 2}
    assert summary["adaptive_pages_used"] == 1
    assert summary["request_timeout_count"] == 1
    assert summary["request_retry_count"] == 1
    assert summary["request_outlier_count"] == 1
    assert summary["max_request_ms"] == 125.0
    assert summary["preference_conflict_count"] == 1
    assert summary["preference_warning_count"] == 1
    assert summary["preference_conflict_codes"] == ["anime_requires_animation_only"]
    assert summary["auto_fix_applied"] is True
    assert summary["selected_preset_before"] == "anime"
    assert summary["selected_preset_after"] == "anime"
    assert summary["countries_before"] == ["RU"]
    assert summary["countries_after"] == ["JP", "RU"]
    assert summary["animation_mode_before"] == "live_action_only"
    assert summary["animation_mode_after"] == "animation_only"


def test_onboarding_compare_report_includes_before_after_metric_keys() -> None:
    current = [
        {"scenario": "ru-manual-jp-kr", "garbage_rate": 0.1, "details_requests": 10, "missing_overview_after_fallback": 1, "country_hit_rate": 1.0, "ok": True},
        {"scenario": "ru-foreign-new-movies-us-gb", "garbage_rate": 0.05, "details_requests": 20, "missing_overview_after_fallback": 0, "country_hit_rate": 1.0, "ok": True},
        {"scenario": "ru-tv-manual-serious-2010", "created_count": 120, "details_requests": 30, "missing_overview_after_fallback": 0, "country_hit_rate": 1.0, "ok": True},
    ]
    report = onboarding_compare_report.build_compare_report(
        current,
        baseline={
            "jp_kr_garbage_rate": 0.3917,
            "us_gb_new_movies_garbage_rate": 0.2417,
            "ru_tv_manual_serious_2010_created_count": 82,
            "details_requests": 0,
            "missing_overview_after_fallback": 10,
            "country_hit_rate": 1.0,
        },
    )
    rows = {row["metric"]: row for row in report["rows"]}

    assert set(rows) == set(onboarding_compare_report.COMPARE_METRICS)
    assert rows["jp_kr_garbage_rate"]["current"] == 0.1
    assert rows["ru_tv_manual_serious_2010_created_count"]["delta"] == 38.0
    assert rows["details_requests"]["current"] == 60.0


def test_onboarding_compare_report_marks_missing_baseline_as_not_captured() -> None:
    report = onboarding_compare_report.build_compare_report(
        [{"scenario": "ru-manual-jp-kr", "garbage_rate": 0.1, "ok": True}],
        baseline={},
    )

    assert all(row["baseline"] == onboarding_compare_report.NOT_CAPTURED for row in report["rows"])
    assert "has no captured baseline yet" in report["analysis_markdown"]


def test_onboarding_compare_report_mentions_failed_scenarios() -> None:
    report = onboarding_compare_report.build_compare_report(
        [
            {"scenario": "ru-manual-jp-kr", "garbage_rate": 0.1, "ok": True},
            {"scenario": "dark-new-tv-us-gb", "status": "failed", "ok": False},
        ],
        baseline={},
    )

    assert "Failed scenarios are present: dark-new-tv-us-gb." in report["analysis_markdown"]


def test_onboarding_report_output_hygiene_contract() -> None:
    assert onboarding_compare_report.RAW_DIR == Path("data/reports/onboarding/raw")
    assert onboarding_compare_report.ANALYSIS_DIR == Path("data/reports/onboarding/analysis")
    assert onboarding_compare_report.BASELINES_DIR == Path("data/reports/onboarding/baselines")
    assert onboarding_report.DEFAULT_REPORT_OUTPUT.relative_to(PROJECT_ROOT) == Path(
        "data/reports/onboarding/analysis/discover_quality_report.md"
    )

    generated_reports_in_docs = sorted((PROJECT_ROOT / "docs").glob("onboarding_*report*.md"))
    assert generated_reports_in_docs == []


def test_onboarding_final_report_template_contains_required_review_fields() -> None:
    template = (PROJECT_ROOT / "docs/reports/curated/onboarding/analysis/final_report_template.md").read_text(encoding="utf-8")
    required_fragments = [
        "## Changed files",
        "## Discover filter confirmation",
        "`vote_count.gte`",
        "`vote_average.gte`",
        "## Vote confidence scoring formula",
        "rating_bonus_adjusted = vote_average * 100 * vote_confidence",
        "## Details enrichment behavior",
        "## Localization fallback behavior",
        "## Quality gate rules",
        "## Adaptive pagination rules",
        "## Tests run",
        "## Before/after metrics",
        "`jp_kr_garbage_rate`",
        "`us_gb_new_movies_garbage_rate`",
        "`ru_tv_manual_serious_2010_created_count`",
        "`details_requests`",
        "`missing_overview_after_fallback`",
        "`country_hit_rate`",
        "## Before/after onboarding scenario output",
        "`not_captured`",
    ]

    for fragment in required_fragments:
        assert fragment in template

import sys
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

from diagnostics import runtime_reports
from scripts.reports import run_onboarding_discover_quality_report as onboarding_report


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
    )

    assert summary["details_requests"] == 4
    assert summary["external_ids_requests"] == 4
    assert summary["details_enrichment_enabled"] is True
    assert summary["localization_fallback_count"] == 2
    assert summary["overview_fallback_original_language_count"] == 1
    assert summary["overview_fallback_en_count"] == 1
    assert summary["vote_confidence_avg"] == 0.625
    assert summary["weak_candidates_count"] == 1
    assert summary["adaptive_pages_used"] == 1

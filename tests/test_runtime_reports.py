import sys
from dataclasses import dataclass
from pathlib import Path

from diagnostics import runtime_reports


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

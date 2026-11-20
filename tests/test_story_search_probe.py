import json
import re
import sys
from pathlib import Path
from runpy import run_path
from types import SimpleNamespace

import pytest

from candidates.story_search import OUT_OF_SCOPE_NOTICE
from candidates import story_search_probe
from storage import profiles


def _run_cli(monkeypatch, *args) -> int:
    monkeypatch.setattr(sys, "argv", ["Watchbane.exe", *map(str, args)])
    with pytest.raises(SystemExit) as exit:
        run_path("start_app.py", run_name="__main__")
    return exit.value.code


@pytest.fixture
def windows_cases(tmp_path):
    script = Path("tools/smoke_windows_e5_install.ps1").read_text(encoding="utf-8")
    payload = re.search(r"@'\n(\{.*?\})\n'@ \| Set-Content", script, re.DOTALL).group(1)
    path = tmp_path / "windows-cases.json"
    path.write_text(payload, encoding="utf-8")
    return path


@pytest.mark.parametrize("bad_order,bad_rejection", [(False, False), (True, False), (False, True)])
def test_story_search_probe_checks_all_ranks_and_negative_in_isolated_profile(
    monkeypatch, tmp_path, windows_cases, bad_order, bad_rejection,
):
    films, queries, rejected = story_search_probe._read_cases(windows_cases)
    results = {q["text"]: q["top1"] for q in queries}
    calls = []
    old_root = profiles.get_base_data_dir()

    class SearchFixture:
        def search(self, text, limit):
            calls.append(text)
            assert limit == len(films)
            if text == rejected:
                return SimpleNamespace(hits=(), notice="" if bad_rejection else OUT_OF_SCOPE_NOTICE)
            other = next(row["key"] for row in films if row["key"] != results[text])
            order = [other, results[text]] if bad_order and len(calls) == 1 else [results[text], other]
            return SimpleNamespace(hits=[SimpleNamespace(document=SimpleNamespace(key=key)) for key in order])

    def build(films_arg, model_dir):
        assert films_arg == films and model_dir == tmp_path / "model"
        disposable = profiles.get_base_data_dir()
        assert disposable.parent == tmp_path and disposable != old_root
        (disposable / "derived-data").touch()
        return SearchFixture()

    monkeypatch.setattr(story_search_probe, "_build_semantic_engine", build)
    monkeypatch.setitem(sys.modules, "desktop.app", None)
    report = tmp_path / "result.json"
    exit = _run_cli(monkeypatch, "--check-story-search", tmp_path / "model", windows_cases, report)

    failed = bad_order or bad_rejection
    assert exit == int(failed)
    assert calls == [*(row["text"] for row in queries), rejected]
    assert profiles.get_base_data_dir() == old_root
    assert sorted(p.name for p in tmp_path.iterdir()) == ["result.json", "windows-cases.json"]
    assert json.loads(report.read_text()) == {
        "status": "expectation_failed" if failed else "ok",
        "search_tested": True, "backend": "semantic_f32",
        "corpus_size": 4, "positive_total": 4,
        "top1_correct": 3 if bad_order else 4,
        "expected_ranks": [2 if bad_order else 1, 1, 1, 1],
        "instruction_rejected": not bad_rejection,
        "gui_tested": False, "collection_tested": False,
    }


def test_story_search_probe_rejects_malformed_cases_without_model_access(monkeypatch, tmp_path):
    cases = tmp_path / "cases.json"
    cases.write_text('{"outside": "private text"}', encoding="utf-8")
    report = tmp_path / "result.json"
    monkeypatch.setattr(story_search_probe, "_build_semantic_engine", lambda *_: pytest.fail("Loaded model"))
    assert _run_cli(monkeypatch, "--check-story-search", tmp_path / "model", cases) == 2
    assert not report.exists()
    assert _run_cli(monkeypatch, "--check-story-search", tmp_path / "model", cases, report) == 1
    before = report.read_bytes()
    assert json.loads(before)["status"] == "invalid_cases"
    assert b"private" not in before
    assert _run_cli(monkeypatch, "--check-story-search", tmp_path / "model", cases, report) == 1
    assert report.read_bytes() == before


def test_story_search_probe_refuses_lexical_fallback(monkeypatch, tmp_path, windows_cases):
    from candidates import story_service

    engine = story_service.StorySearch(())
    monkeypatch.setattr(story_service, "create_story_search", lambda *_: engine)
    report = tmp_path / "result.json"
    assert _run_cli(monkeypatch, "--check-story-search", tmp_path / "model", windows_cases, report) == 1
    assert json.loads(report.read_text()) == {
        "status": "engine_or_query_failed", "search_tested": False,
        "gui_tested": False, "collection_tested": False,
    }

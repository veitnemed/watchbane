import hashlib
import json
import sys

import pytest

from candidates.story_search import StoryDocument, StoryResponse
from tools.qa import evaluate_story_relevance as cli


def _args(tmp_path, monkeypatch, cases, *flags, annotations=None):
    fixture = tmp_path / "sealed-fixture.json"
    frozen = json.dumps({"cases": cases}).encode()
    fixture.write_bytes(frozen)
    options = [
        "evaluate_story_relevance", "--cases", str(fixture), "--sha256", hashlib.sha256(frozen).hexdigest(),
        "--catalog", str(tmp_path / "offline.json"), "--model-dir", str(tmp_path / "model"),
        "--profile", str(tmp_path / "qa-profile"), *flags,
    ]
    if annotations is not None:
        reviews = tmp_path / "reviews.json"
        reviews.write_text(json.dumps(annotations), encoding="utf-8")
        options.extend(["--annotations", str(reviews)])
    monkeypatch.setattr(sys, "argv", options)


@pytest.fixture
def isolated_cli(monkeypatch):
    from candidates import story_service

    monkeypatch.setattr("tools.qa.isolation.apply_isolated_data_dir", lambda _path: None)
    documents = (StoryDocument("tmdb:movie:1", "Fixture", "Герой лечит врачей.", "movie", "offline"),)
    monkeypatch.setattr(story_service, "story_catalog_snapshot", lambda *, seed_path: (documents, {}))
    return story_service


def test_cli_coverage_gate_skips_model_work_and_reports_missing_case(tmp_path, monkeypatch, capsys, isolated_cli):
    _args(tmp_path, monkeypatch, [
        {"id": "off-catalog", "expect": "match", "query": "test", "full": ["tmdb:movie:2"]},
    ], "--require-complete-coverage")

    def no_model(*_a, **_kw):
        raise AssertionError("No model needed for a missing-coverage gate")

    monkeypatch.setattr(isolated_cli, "create_story_search", no_model)
    assert cli.main() == 1
    output = json.loads(capsys.readouterr().out)
    assert output["coverage"]["uncovered_positive_case_ids"] == ["off-catalog"]
    assert output["gates"] == {"complete_coverage": False}
    assert output["ranking_skipped"] and "hybrid" not in output


@pytest.mark.parametrize("review_both", [True, False])
def test_cli_keeps_manual_verdict_separate_per_engine(tmp_path, monkeypatch, capsys, isolated_cli, review_both):
    rows = [{"id": "ood", "group": "ood", "query": "not a story"}]
    review = {"ood": {"action": "UNSUPPORTED", "scope_notice": True}}
    labels = {"hybrid": review, **({"words": review} if review_both else {})}
    _args(tmp_path, monkeypatch, rows, annotations=labels)

    class BenchmarkEngine:
        def search(self, _):
            return StoryResponse((), backend="fixture backend")

    monkeypatch.setattr(isolated_cli, "create_story_search", lambda *_: BenchmarkEngine())
    monkeypatch.setattr("candidates.story_search.StorySearch", lambda _documents: BenchmarkEngine())
    assert cli.main() == 0
    output = json.loads(capsys.readouterr().out)
    assert output["gates"] == {}
    assert output["hybrid"]["cases"][0]["behavior_pass"] is True
    assert output["words"]["cases"][0]["behavior_pass"] is (True if review_both else None)
    assert output["hybrid"]["reported_backends"] == ["fixture backend"]


@pytest.mark.parametrize("cases", [
    [],
    [{"id": "a", "expect": "no_match", "query": " "}],
    [{"id": "a", "expect": "no_match", "query": "a", "group": "ood"}],
])
def test_cli_rejects_empty_or_bad_sealed_inputs_before_profile_setup(tmp_path, monkeypatch, capsys, cases):
    _args(tmp_path, monkeypatch, cases)

    def no_profile(_):
        raise AssertionError("Malformed sealed input must not touch any profile")

    monkeypatch.setattr("tools.qa.isolation.apply_isolated_data_dir", no_profile)
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == 2
    assert "error:" in capsys.readouterr().err

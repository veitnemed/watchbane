import json
import os
from pathlib import Path

import pytest

from tools.qa import smoke_story_desktop as smoke


def arguments(tmp_path):
    catalog = tmp_path / "private-catalog.jsonl"
    catalog.write_text(json.dumps({
        "tmdb_id": 3477123, "media_type": "movie", "title": "Частный QA заголовок",
        "overview": "Врач лечит пациентов в больнице и спасает ребёнка.",
        "language": "ru-RU", "year": 2020,
    }, ensure_ascii=False) + "\n", encoding="utf-8")
    model = tmp_path / "model"
    model.mkdir()
    return ["--catalog", str(catalog), "--model-dir", str(model), "--query", "врач в больнице",
            "--expected-title", "Частный QA заголовок"]


def test_operator_cli_refuses_existing_profile_and_same_screenshot_target(tmp_path, capsys):
    args = arguments(tmp_path)
    profile = tmp_path / "profile"
    profile.mkdir()
    marker = profile / "existing"
    marker.write_text("untouched", encoding="utf-8")
    assert smoke.main([*args, "--profile", str(profile)]) == 1
    assert marker.read_text(encoding="utf-8") == "untouched"
    assert "fresh or empty" in capsys.readouterr().err
    unused = tmp_path / "unused"
    assert smoke.main([*args, "--profile", str(unused), "--output-dir", str(unused)]) == 1
    assert not unused.exists()
    assert "separate directories" in capsys.readouterr().err


def test_operator_report_uses_two_phases_without_catalogue_content(tmp_path, capsys, monkeypatch):
    args = arguments(tmp_path)
    calls = []

    def child(phase, payload, **kwargs):
        assert (Path(payload["profile"]) / smoke.PROFILE_MARKER).is_file()
        calls.append((phase, payload["profile"], kwargs["platform"]))
        return {"ok": True, "pid": len(calls), "unexpected_network_calls": 0}

    monkeypatch.setattr(smoke, "_child_run", child)
    assert smoke.main([*args, "--qt-platform", "offscreen"]) == 0
    assert calls == [("first", calls[0][1], "offscreen"), ("reopen", calls[0][1], "offscreen")]
    assert not Path(calls[0][1]).exists()  # default temp profile cleaned
    output = capsys.readouterr()
    report = json.loads(output.out)
    assert report["isolated_processes"] == 2 and report["reopened_collection_matches"]
    assert "Частный QA заголовок" not in output.out and "private-catalog" not in output.out


def test_ci_can_run_actual_smoke_with_operator_supplied_model(tmp_path, capsys):
    model = os.environ.get("WATCHBANE_TEST_MODEL_DIR")
    if not model:
        pytest.skip("Set WATCHBANE_TEST_MODEL_DIR to verified local E5 artifacts")
    args = arguments(tmp_path)
    args[3] = model
    assert smoke.main([*args, "--step-timeout", "20", "--qt-platform", "offscreen"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["first"]["pid"] != output["reopen"]["pid"]
    assert output["first"]["unexpected_network_calls"] == output["reopen"]["unexpected_network_calls"] == 0


def test_environment_does_not_forward_existing_credentials_or_profile_settings(monkeypatch):
    for key in ("WATCHBANE_DATA_DIR", "WATCHBANE_STORY_SEED_CATALOG", "TMDB_TOKEN", "PYTHONPATH"):
        monkeypatch.setenv(key, "should-not-reach-child")
    isolated = smoke._clean_environment("offscreen")
    assert "should-not-reach-child" not in isolated.values()
    assert isolated["QT_QPA_PLATFORM"] == "offscreen"
    assert smoke.match_title("  Белый\u00A0дом ", "БЕЛЫЙ дом")

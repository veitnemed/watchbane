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


@pytest.mark.parametrize("cached_install", [False, True])
def test_ci_can_run_actual_smoke_with_operator_supplied_model(tmp_path, capsys, cached_install):
    model = os.environ.get("WATCHBANE_TEST_MODEL_DIR")
    if not model:
        pytest.skip("Set WATCHBANE_TEST_MODEL_DIR to verified local E5 artifacts")
    args = arguments(tmp_path)
    args[3] = model
    if cached_install:
        args.append("--verify-cached-install")
    assert smoke.main([*args, "--step-timeout", "30", "--qt-platform", "offscreen"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["cached_model_verified_in_ui"] is cached_install
    assert output["first"]["pid"] != output["reopen"]["pid"]
    assert output["first"]["unexpected_network_calls"] == output["reopen"]["unexpected_network_calls"] == 0


def test_environment_does_not_forward_existing_credentials_or_profile_settings(monkeypatch):
    for key in ("WATCHBANE_DATA_DIR", "WATCHBANE_STORY_SEED_CATALOG", "TMDB_TOKEN", "PYTHONPATH"):
        monkeypatch.setenv(key, "should-not-reach-child")
    isolated = smoke._clean_environment("offscreen")
    assert "should-not-reach-child" not in isolated.values()
    assert isolated["QT_QPA_PLATFORM"] == "offscreen"
    assert smoke.match_title("  Белый\u00A0дом ", "БЕЛЫЙ дом")


def test_frozen_child_file_ipc_keeps_private_inputs_out_of_args(tmp_path, monkeypatch):
    from tools.qa import frozen_story_desktop as entry

    exe = tmp_path / "WatchbaneStoryQA.exe"
    payload = {"query": "частный запрос", "verify_cached_install": True}

    def phase_run(phase, options):
        assert phase == "first" and options["require_fp32"] is True
        assert options["query"] == payload["query"]
        return {"ok": True, "pid": 42}

    def process_run(argv, **kwargs):
        assert argv[0] == str(exe)
        assert payload["query"] not in str(argv)
        assert kwargs["stdin"] == smoke.subprocess.DEVNULL
        status = entry.main(argv[1:])
        return smoke.subprocess.CompletedProcess(argv, status)

    monkeypatch.setattr(entry.sys, "frozen", True, raising=False)
    monkeypatch.setattr(entry, "_child_report", phase_run)
    monkeypatch.setattr(smoke.subprocess, "run", process_run)
    assert smoke._child_run("first", payload, timeout=5, platform=None, exe=exe) == {"ok": True, "pid": 42, "frozen": True}


def test_frozen_entry_rejects_existing_report_and_non_cached_request(tmp_path, monkeypatch):
    from tools.qa import frozen_story_desktop as entry

    request = tmp_path / "request.json"
    request.write_text("{}", encoding="ascii")
    report = tmp_path / "report.json"
    monkeypatch.setattr(entry, "_child_report", lambda *_: pytest.fail("Must not start Qt."))
    assert entry.main(["first", str(request), str(report)]) == 1
    assert json.loads(report.read_text()) == {"ok": False, "failure": "Cached model verification is required.", "frozen": False}
    report.write_text("unchanged")
    assert entry.main(["first", str(request), str(report)]) == 1
    assert report.read_text() == "unchanged"


@pytest.mark.skipif(not (os.environ.get("WATCHBANE_TEST_QA_EXE") and os.environ.get("WATCHBANE_TEST_MODEL_DIR")),
                    reason="Requires private frozen QA executable and verified FP32 model")
def test_frozen_bundle_can_run_actual_smoke(tmp_path, capsys):
    args = arguments(tmp_path)
    args[3] = os.environ["WATCHBANE_TEST_MODEL_DIR"]
    assert smoke.main([*args, "--qa-exe", os.environ["WATCHBANE_TEST_QA_EXE"],
                       "--verify-cached-install", "--step-timeout", "60"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["frozen_qa"] and output["fp32_required"]


def test_private_overlay_uses_production_data_without_altering_public_spec(tmp_path, monkeypatch):
    from tools.qa import build_frozen_story_desktop as build

    root = Path(build.__file__).resolve().parents[2]
    original = (root / "watchbane.spec").read_bytes()

    def build_call(argv, **kwargs):
        assert kwargs["cwd"] == root
        assert kwargs["env"]["WATCHBANE_BUNDLE_PROFILE"] == "semantic"
        assert Path(argv[-1]).parent != root
        overlay = Path(argv[-1]).read_text(encoding="utf-8")
        assert overlay.count('name="WatchbaneStoryQA"') == 2
        assert "frozen_story_desktop.py" in overlay
        assert "start_app.py" not in overlay
        captured = {}
        prefix = overlay.split("# -*- mode: python", 1)[0]
        namespace = {"Analysis": lambda *_args, **kw: captured.update(kw)}
        exec(compile(prefix, "fake-private.spec", "exec"), namespace)
        namespace["_qa_analysis"](datas=[("desktop/images/logos", "desktop/images/logos")])
        assert Path(captured["datas"][0][0]).is_dir()
        assert captured["datas"][0][1] == "desktop/images/logos"
        return 0

    monkeypatch.setattr(build.subprocess, "call", build_call)
    assert build.main([str(tmp_path / "private")]) == 0
    assert (root / "watchbane.spec").read_bytes() == original



def test_frozen_windows_child_leaves_python_off_path(monkeypatch):
    monkeypatch.setattr(smoke.sys, "platform", "win32")
    monkeypatch.setenv("SystemRoot", r"C:\Windows")
    monkeypatch.setenv("Path", r"C:\InstalledPython")
    with_frozen = smoke._clean_environment("offscreen", frozen=True)
    assert {key: value for key, value in with_frozen.items() if key.upper() == "PATH"} == {"PATH": r"C:\Windows\System32"}

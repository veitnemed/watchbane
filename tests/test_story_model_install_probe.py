import json
import sys
from pathlib import Path
from runpy import run_path
from types import ModuleType

import pytest


def _run_cli(monkeypatch, *args) -> int:
    monkeypatch.setattr(sys, "argv", ["Watchbane.exe", *map(str, args)])
    with pytest.raises(SystemExit) as exit:
        run_path("start_app.py", run_name="__main__")
    return exit.value.code


@pytest.fixture
def fake_installer(monkeypatch):
    module = ModuleType("candidates.story_model_install")
    module.StoryModelInstallError = type("StoryModelInstallError", (RuntimeError,), {})
    monkeypatch.setitem(sys.modules, module.__name__, module)
    return module


def test_model_install_requires_explicit_consent_and_new_separate_report(monkeypatch, tmp_path, fake_installer):
    def unexpected(*_args):
        pytest.fail("installation must not start without a valid opt-in and unused report")

    fake_installer.install_story_model = unexpected
    destination = tmp_path / "model"
    report = tmp_path / "report.json"
    assert _run_cli(monkeypatch, "--install-semantic-model", destination, report) == 2
    assert _run_cli(monkeypatch, "--install-semantic-model", destination, report, "--different-flag") == 2
    assert not report.exists() and not destination.exists()

    report.write_text("existing report", encoding="utf-8")
    assert _run_cli(monkeypatch, "--install-semantic-model", destination, report, "--accept-download") == 1
    assert report.read_text(encoding="utf-8") == "existing report"
    assert _run_cli(monkeypatch, "--install-semantic-model", destination, destination, "--accept-download") == 1
    assert not destination.exists()


@pytest.mark.parametrize("should_fail", [False, True])
def test_explicit_model_install_delegates_and_reports_no_secrets(monkeypatch, tmp_path, fake_installer, should_fail):
    # A local stub deliberately substitutes for the production download.
    # Importing Qt/normal boot can never be needed on this entry point.
    monkeypatch.setitem(sys.modules, "desktop.app", None)
    monkeypatch.setitem(sys.modules, "PyQt6", None)
    runtime = tmp_path / "profile must stay untouched"
    monkeypatch.setenv("WATCHBANE_DATA_DIR", str(runtime))
    destination = tmp_path / "private model directory"
    report = tmp_path / "new report.json"
    calls = []

    def pretend_install(path: Path) -> Path:
        assert report.is_file()
        calls.append(path)
        if should_fail:
            raise RuntimeError(f"signed URL and paths are secret: {path}")
        return path

    fake_installer.install_story_model = pretend_install
    assert _run_cli(monkeypatch, "--install-semantic-model", destination, report, "--accept-download") == int(should_fail)
    assert calls == [destination]
    assert not runtime.exists()
    result = json.loads(report.read_text(encoding="utf-8"))
    expected = {
        "status": "install_failed" if should_fail else "ok",
        "installation_verified": not should_fail,
        "model_tested": False,
        "search_tested": False,
    }
    if should_fail:
        expected.update(failure_stage="install", failure_code="runtime_error")
    assert result == expected


@pytest.mark.parametrize("code,expected", [
    ("redirect_host", "redirect_host"),
    ("network_or_disk", "network_or_disk"),
    ("tls", "tls"),
    ("https://private.example/model?signature=secret", "runtime_error"),
    (["redirect_host", "secret"], "runtime_error"),
])
def test_model_install_reports_only_allowlisted_installer_codes(monkeypatch, tmp_path, fake_installer, code, expected):
    destination = tmp_path / "private destination"
    report = tmp_path / "report.json"

    def pretend_install(path):
        error = fake_installer.StoryModelInstallError(f"Internal details {path}")
        error.code = code
        raise error

    fake_installer.install_story_model = pretend_install
    assert _run_cli(monkeypatch, "--install-semantic-model", destination, report, "--accept-download") == 1
    result = json.loads(report.read_text(encoding="utf-8"))
    assert result["failure_stage"] == "install"
    assert result["failure_code"] == expected
    assert set(result) == {"status", "installation_verified", "model_tested", "search_tested",
                           "failure_stage", "failure_code"}


def test_model_install_distinguishes_an_import_failure(monkeypatch, tmp_path, fake_installer):
    # Missing callable mimics an import problem without using the network.
    report = tmp_path / "report.json"
    assert _run_cli(monkeypatch, "--install-semantic-model", tmp_path / "model", report, "--accept-download") == 1
    result = json.loads(report.read_text(encoding="utf-8"))
    assert result["failure_stage"] == "import_installer"
    assert result["failure_code"] == "import_error"

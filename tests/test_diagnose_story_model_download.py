import re

from candidates.story_model_install import StoryModelInstallError
from tools.qa import diagnose_story_model_download as diag

from test_story_model_install import _ARTIFACTS, _PREFIX, Response, fake_download


def _phases(stdout):
    return re.findall(r"phase=(\w+)", stdout)


def test_ci_trace_matches_real_verified_installer_with_fake_transport(tmp_path, fake_download, capsys):
    destination = tmp_path / "private-workspace"
    assert diag.run_install(destination) == 0
    stdout = capsys.readouterr().out
    assert _phases(stdout) == ["installer_started", "first_progress", "verified"]
    assert f"observed_bytes={sum(map(len, _ARTIFACTS.values()))}" in stdout.splitlines()[-1]
    assert "elapsed_s=" in stdout and str(destination) not in stdout and _PREFIX not in stdout
    assert len(fake_download.requests) == 2 and destination.is_dir()


def test_ci_trace_reports_only_safe_integrity_code(tmp_path, fake_download, capsys):
    fake_download.responses[_PREFIX + "onnx/tokenizer.json"] = Response(b"fixture bad tokenizer")
    destination = tmp_path / "private"
    assert diag.run_install(destination) == 1
    output = capsys.readouterr().out
    assert _phases(output)[-1] == "failed"
    assert "error=integrity" in output and "tokenizer" not in output and str(destination) not in output
    assert not destination.exists()


def test_heartbeat_is_bounded_even_without_first_progress(tmp_path, monkeypatch, capsys):
    from threading import Event

    count = 0
    ready = Event()

    def trace(text, **kwargs):
        nonlocal count
        print(text, **kwargs)
        if "install_in_progress" in text:
            count += 1
            if count == 2:
                ready.set()

    def stuck(*args, **kwargs):
        assert ready.wait(2)
        raise StoryModelInstallError("https://secret.invalid/?signed", "inject\nunsafe")

    monkeypatch.setattr(diag, "print", trace, raising=False)
    monkeypatch.setattr(diag, "install_story_model", stuck)
    monkeypatch.setattr(diag, "_MAX_HEARTBEATS", 2)
    assert diag.run_install(tmp_path / "unused", heartbeat_seconds=.001) == 1
    output = capsys.readouterr().out
    assert _phases(output) == ["installer_started", "install_in_progress", "install_in_progress", "failed"]
    assert output.count("observed_bytes=0") == 4
    assert "error=installer_error" in output and "unsafe" not in output and "secret" not in output

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from desktop.shell.single_instance import SingleInstanceGuard, show_already_running_warning


def test_guard_rejects_second_owner_for_same_runtime(qtbot, tmp_path) -> None:
    del qtbot
    first = SingleInstanceGuard(tmp_path)
    second = SingleInstanceGuard(tmp_path)
    try:
        assert first.acquire() is True
        assert first.acquire() is True
        assert second.acquire() is False
    finally:
        second.release()
        first.release()


def test_guard_is_scoped_per_runtime_profile(qtbot, tmp_path) -> None:
    del qtbot
    first = SingleInstanceGuard(tmp_path / "profile-a")
    second = SingleInstanceGuard(tmp_path / "profile-b")
    try:
        assert first.acquire() is True
        assert second.acquire() is True
    finally:
        second.release()
        first.release()


def test_guard_rejects_live_external_process_and_recovers_after_exit(qtbot, tmp_path) -> None:
    del qtbot
    code = (
        "import sys,time; "
        "from desktop.shell.single_instance import SingleInstanceGuard; "
        "guard=SingleInstanceGuard(sys.argv[1]); "
        "assert guard.acquire(); print('READY', flush=True); time.sleep(30)"
    )
    process = subprocess.Popen(
        [sys.executable, "-c", code, str(tmp_path)],
        cwd=str(Path(__file__).resolve().parents[2]),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    contender = SingleInstanceGuard(tmp_path)
    try:
        assert process.stdout is not None
        assert process.stdout.readline().strip() == "READY"
        assert contender.acquire() is False
    finally:
        process.terminate()
        process.wait(timeout=10)
        contender.release()

    recovered = SingleInstanceGuard(tmp_path)
    try:
        assert recovered.acquire() is True
    finally:
        recovered.release()


def test_already_running_warning_is_clear(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(
        "desktop.shell.single_instance.QMessageBox.warning",
        lambda parent, title, text: calls.append((parent, title, text)),
    )

    show_already_running_warning()

    assert calls[0][1] == "Watchbane"
    assert "уже запущен" in calls[0][2]
    assert "already running" in calls[0][2]

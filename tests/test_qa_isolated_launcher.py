from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from config.app_paths import DATA_DIR_ENV, resolve_runtime_root
from tools.qa.isolation import IsolationError, assert_runtime_is_isolated, real_watchbane_profile_root
from tools.qa import run_recommendation_audit as launcher


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_assert_runtime_rejects_real_appdata_path() -> None:
    real = real_watchbane_profile_root()
    with pytest.raises(IsolationError, match="equals real Watchbane profile"):
        assert_runtime_is_isolated(real, real_root=real)


def test_assert_runtime_rejects_path_inside_real_profile(tmp_path: Path) -> None:
    real = real_watchbane_profile_root()
    nested = real / "qa_nested_should_fail"
    with pytest.raises(IsolationError, match="inside real Watchbane profile"):
        assert_runtime_is_isolated(nested, real_root=real)


def test_assert_runtime_rejects_empty_runtime() -> None:
    with pytest.raises(IsolationError, match="Runtime root is required"):
        assert_runtime_is_isolated("")
    with pytest.raises(IsolationError, match="Runtime root is required"):
        assert_runtime_is_isolated(Path("."))


def test_launcher_cli_rejects_real_appdata(tmp_path: Path) -> None:
    real = real_watchbane_profile_root()
    code = launcher.main(["--runtime-root", str(real), "--evidence-dir", str(tmp_path / "ev")])
    assert code == 2


def test_launcher_cli_requires_runtime_root() -> None:
    with pytest.raises(SystemExit) as raised:
        launcher.build_parser().parse_args([])
    assert raised.value.code == 2


def test_launcher_accepts_temp_runtime_and_child_proves_isolation(tmp_path: Path) -> None:
    runtime = tmp_path / "isolated_runtime"
    evidence = tmp_path / "evidence"
    code = launcher.main(
        [
            "--runtime-root",
            str(runtime),
            "--evidence-dir",
            str(evidence),
        ]
    )
    assert code == 0
    meta_path = evidence / "isolation_meta.json"
    proof_path = evidence / "child_isolation_proof.json"
    assert meta_path.is_file()
    assert proof_path.is_file()
    assert (runtime / ".watchbane_qa_isolated").is_file()
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    proof = json.loads(proof_path.read_text(encoding="utf-8"))
    assert meta["isolation_check"] == "pass"
    assert proof["isolated"] is True
    app_data = Path(proof["APP_DATA_DIR"]).resolve()
    assert app_data == (runtime.resolve() / "data")
    # Parent must have left DATA_DIR pointing at isolated root for this process too.
    assert Path(os.environ[DATA_DIR_ENV]).resolve() == runtime.resolve()


def test_subprocess_module_entry_rejects_missing_and_accepts_tmp(tmp_path: Path) -> None:
    missing = subprocess.run(
        [sys.executable, "-m", "tools.qa.run_recommendation_audit"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert missing.returncode != 0

    runtime = tmp_path / "mod_runtime"
    ok = subprocess.run(
        [
            sys.executable,
            "-m",
            "tools.qa.run_recommendation_audit",
            "--runtime-root",
            str(runtime),
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert ok.returncode == 0, ok.stderr
    assert "ISOLATION_OK" in (ok.stdout or "")

"""Developer-only console launchers for GUI smoke scenarios."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from config.app_paths import DATA_DIR_ENV
from storage import profiles
from storage import runtime


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def build_empty_candidate_pool_gui_command() -> list[str]:
    """Return the current Python command for starting the desktop GUI."""
    return [sys.executable, "start_app.py"]


def _dev_gui_runtime_root() -> Path:
    return _repo_root() / "tmp" / "dev_gui" / "empty_candidate_pool"


def _assert_inside(parent: Path, child: Path) -> None:
    resolved_parent = parent.resolve()
    resolved_child = child.resolve()
    if resolved_child == resolved_parent:
        return
    if resolved_child.is_relative_to(resolved_parent) is False:
        raise RuntimeError(f"Unsafe dev GUI path: {resolved_child}")


def prepare_empty_candidate_pool_runtime() -> Path:
    """Copy the active data root into an isolated runtime root for GUI dev checks."""
    repo_tmp = _repo_root() / "tmp"
    runtime_root = _dev_gui_runtime_root()
    target_data_dir = runtime_root / "data"
    source_data_dir = Path(profiles.describe_active_profile()["data_dir"])

    _assert_inside(repo_tmp, runtime_root)
    if source_data_dir.resolve().is_relative_to(runtime_root.resolve()):
        raise RuntimeError("Dev GUI source data dir cannot be inside the target runtime root.")

    if runtime_root.exists():
        shutil.rmtree(runtime_root)
    runtime_root.mkdir(parents=True, exist_ok=True)

    if source_data_dir.is_dir():
        shutil.copytree(
            source_data_dir,
            target_data_dir,
            ignore=shutil.ignore_patterns("backups", "cache", "exports", "logs"),
        )
    else:
        target_data_dir.mkdir(parents=True, exist_ok=True)
    return runtime_root


def launch_gui_with_empty_candidate_pool() -> int:
    """Start GUI so its bootstrap clears candidate/onboarding tables first."""
    runtime_root = prepare_empty_candidate_pool_runtime()
    env = os.environ.copy()
    env[DATA_DIR_ENV] = str(runtime_root)
    env[runtime.DEV_CLEAR_CANDIDATES_ENV] = "1"
    env.pop(runtime.DEV_EMPTY_PROFILE_ENV, None)

    command = build_empty_candidate_pool_gui_command()
    print("\nDev GUI mode: empty candidate pool on startup")
    print(f"Flag: {runtime.DEV_CLEAR_CANDIDATES_ENV}=1")
    print(f"Data root: {runtime_root}")
    print("Watched records are copied. Candidate/onboarding tables are backed up then cleared in this sandbox.")
    print("Close the GUI window to return to the console.\n")

    completed = subprocess.run(command, cwd=_repo_root(), env=env, check=False)
    return int(completed.returncode or 0)

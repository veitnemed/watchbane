"""Developer-only console launchers for GUI smoke scenarios."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from storage import runtime


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def build_empty_candidate_pool_gui_command() -> list[str]:
    """Return the current Python command for starting the desktop GUI."""
    return [sys.executable, "start_app.py"]


def launch_gui_with_empty_candidate_pool() -> int:
    """Start GUI so its bootstrap clears candidate/onboarding tables first."""
    env = os.environ.copy()
    env[runtime.DEV_CLEAR_CANDIDATES_ENV] = "1"
    env.pop(runtime.DEV_EMPTY_PROFILE_ENV, None)

    command = build_empty_candidate_pool_gui_command()
    print("\nDev GUI mode: empty candidate pool on startup")
    print(f"Flag: {runtime.DEV_CLEAR_CANDIDATES_ENV}=1")
    print("Watched records are kept. Candidate/onboarding tables are backed up then cleared by GUI bootstrap.")
    print("Close the GUI window to return to the console.\n")

    completed = subprocess.run(command, cwd=_repo_root(), env=env, check=False)
    return int(completed.returncode or 0)

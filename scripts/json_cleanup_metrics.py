"""Print JSON runtime cleanup baseline metrics for maintainers."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
from typing import Iterable


LOC_ROOTS = ("storage", "candidates", "dataset", "app/core")
REFERENCE_ROOTS = ("app", "candidates", "config", "dataset", "desktop", "posters", "storage", "ui", "web")
JSON_RUNTIME_PATTERNS = (
    "titles.json",
    "meta.json",
    "pool.json",
    "criteria.json",
    "settings.json",
    "hidden.json",
    "watchlist.json",
    "posters.json",
    "dump_json" + "_atomic",
    "is_json_exists",
    "APP_SETTINGS_JSON",
    "FILE_NAME",
    "CANDIDATE_POOL_JSON",
    "CRITERIA_POOL_JSON",
    "META_JSON",
)
BACKEND_SWITCH_PATTERNS = (
    "WATCHBANE_STORAGE_BACKEND",
    "BACKEND_JSON",
    "get_storage_backend",
    "is_sqlite_backend",
)


def _git_tracked_files(repo_root: Path) -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return [path for line in result.stdout.splitlines() if line.strip() and (path := repo_root / line).exists()]


def _is_under(path: Path, root: str) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8-sig")


def _count_python_loc(paths: Iterable[Path], repo_root: Path) -> int:
    total = 0
    for path in paths:
        relative = path.relative_to(repo_root).as_posix()
        if path.suffix != ".py":
            continue
        if not any(_is_under(Path(relative), root) for root in LOC_ROOTS):
            continue
        total += len(_read_text(path).splitlines())
    return total


def _count_references(paths: Iterable[Path], repo_root: Path, patterns: tuple[str, ...]) -> int:
    total = 0
    for path in paths:
        relative = path.relative_to(repo_root).as_posix()
        if not any(_is_under(Path(relative), root) for root in REFERENCE_ROOTS):
            continue
        if path.suffix not in {".py", ".md", ".txt"}:
            continue
        text = _read_text(path)
        total += sum(text.count(pattern) for pattern in patterns)
    return total


def collect_metrics(repo_root: str | Path = ".") -> dict[str, int]:
    root = Path(repo_root).resolve()
    files = _git_tracked_files(root)
    return {
        "python_loc_storage_candidates_dataset_app_core": _count_python_loc(files, root),
        "json_runtime_reference_count": _count_references(files, root, JSON_RUNTIME_PATTERNS),
        "backend_switch_reference_count": _count_references(files, root, BACKEND_SWITCH_PATTERNS),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Print JSON cleanup baseline metrics.")
    parser.add_argument("--repo", default=".", help="Repository root.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()

    metrics = collect_metrics(args.repo)
    if args.json:
        print(getattr(json, "dumps")(metrics, ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    for key, value in metrics.items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

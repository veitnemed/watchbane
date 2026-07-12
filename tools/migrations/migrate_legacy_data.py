"""Migrate legacy local data files into the project data/ layout."""

from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
BACKUP_ROOT = ROOT_DIR / "data" / "backups"


@dataclass(frozen=True)
class CopyRule:
    source: Path
    target: Path
    kind: str


RULES = [
    CopyRule(
        Path("C:/DATA/movies-learn/dataset.json"),
        ROOT_DIR / "data" / "watched" / "titles.json",
        "json",
    ),
    CopyRule(
        Path("C:/META/meta-movies-learn/meta_data.json"),
        ROOT_DIR / "data" / "watched" / "meta.json",
        "json",
    ),
    CopyRule(
        Path("C:/DATA/movies-learn/candidate_pool.json"),
        ROOT_DIR / "data" / "candidates" / "pool.json",
        "json",
    ),
    CopyRule(
        Path("C:/DATA/movies-learn/candidate_criteria.json"),
        ROOT_DIR / "data" / "candidates" / "criteria.json",
        "json",
    ),
    CopyRule(
        Path("C:/DATA/movies-learn/api_requests.log"),
        ROOT_DIR / "data" / "logs" / "api_requests.log",
        "text",
    ),
    CopyRule(
        Path("C:/TXT_FILES/movies-learn/edit_dataset.xlsx"),
        ROOT_DIR / "data" / "exports" / "edit_dataset.xlsx",
        "binary",
    ),
]


def _is_non_empty_file(path: Path) -> bool:
    return path.is_file() and path.stat().st_size > 0


def _validate_json(path: Path) -> None:
    with path.open("r", encoding="utf-8-sig") as file:
        json.load(file)


def _relative_target(path: Path) -> Path:
    try:
        return path.relative_to(ROOT_DIR)
    except ValueError:
        return Path(path.name)


def _backup_existing(path: Path, stamp: str, dry_run: bool) -> Path | None:
    if not _is_non_empty_file(path):
        return None

    backup_path = BACKUP_ROOT / f"migration_{stamp}" / _relative_target(path)
    if dry_run:
        return backup_path

    backup_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, backup_path)
    return backup_path


def _copy(rule: CopyRule, stamp: str, dry_run: bool) -> bool:
    if not rule.source.is_file():
        print(f"SKIP missing: {rule.source}")
        return False

    if rule.kind == "json":
        _validate_json(rule.source)

    backup_path = _backup_existing(rule.target, stamp, dry_run)
    if backup_path is not None:
        print(f"BACKUP: {rule.target} -> {backup_path}")

    if dry_run:
        print(f"DRY RUN: {rule.source} -> {rule.target}")
        return True

    rule.target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(rule.source, rule.target)
    print(f"MIGRATED: {rule.source} -> {rule.target}")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Copy legacy local data into the current data/ layout."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show planned copies without writing files.",
    )
    args = parser.parse_args()

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    migrated = 0

    for rule in RULES:
        try:
            if _copy(rule, stamp, args.dry_run):
                migrated += 1
        except json.JSONDecodeError as exc:
            print(f"ERROR invalid json: {rule.source} ({exc})")
        except OSError as exc:
            print(f"ERROR file copy failed: {rule.source} -> {rule.target} ({exc})")

    print(f"DONE: {migrated} file(s) ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

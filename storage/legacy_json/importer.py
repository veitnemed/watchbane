"""Explicit import of legacy JSON data into SQLite."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil

from storage.sqlite import action_repository
from storage.sqlite import candidate_repository
from storage.sqlite import poster_repository
from storage.sqlite import settings_repository
from storage.sqlite import watched_repository
from storage.sqlite.connection import get_db_path


@dataclass(frozen=True)
class LegacyJsonPaths:
    base_dir: Path
    titles: Path
    meta: Path
    candidate_pool: Path
    candidate_criteria: Path
    watchlist: Path
    hidden: Path
    settings: Path
    poster_cache: Path
    backup_dir: Path


def legacy_paths(base_dir: str | Path = "data") -> LegacyJsonPaths:
    base = Path(base_dir)
    return LegacyJsonPaths(
        base_dir=base,
        titles=base / "watched" / "titles.json",
        meta=base / "watched" / "meta.json",
        candidate_pool=base / "candidates" / "pool.json",
        candidate_criteria=base / "candidates" / "criteria.json",
        watchlist=base / "candidates" / "watchlist.json",
        hidden=base / "candidates" / "hidden.json",
        settings=base / "settings.json",
        poster_cache=base / "cache" / "posters" / "posters.json",
        backup_dir=base / "backups",
    )


def load_legacy_json_mapping(path: Path) -> dict:
    if path.is_file() is False:
        return {}
    with path.open("r", encoding="utf-8-sig") as file:
        data = json.load(file)
    return data if isinstance(data, dict) else {}


def _json_sources(paths: LegacyJsonPaths) -> tuple[Path, ...]:
    return (
        paths.titles,
        paths.meta,
        paths.candidate_pool,
        paths.candidate_criteria,
        paths.watchlist,
        paths.hidden,
        paths.settings,
        paths.poster_cache,
    )


def backup_legacy_json(paths: LegacyJsonPaths) -> Path:
    """Copy existing legacy JSON files before importing."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    backup_root = paths.backup_dir / f"sqlite-import-{stamp}"
    for source in _json_sources(paths):
        if source.is_file() is False:
            continue
        relative = source.relative_to(paths.base_dir)
        target = backup_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    backup_root.mkdir(parents=True, exist_ok=True)
    return backup_root


def import_legacy_json_to_sqlite(
    *,
    base_dir: str | Path = "data",
    db_path: str | Path | None = None,
    dry_run: bool = False,
    create_backup: bool = True,
) -> dict:
    """Import legacy JSON files into SQLite and return a count report."""
    paths = legacy_paths(base_dir)
    target_db = Path(db_path) if db_path is not None else get_db_path()

    payloads = {
        "watched": load_legacy_json_mapping(paths.titles),
        "meta": load_legacy_json_mapping(paths.meta),
        "candidate_pool": load_legacy_json_mapping(paths.candidate_pool),
        "candidate_criteria": load_legacy_json_mapping(paths.candidate_criteria),
        "watchlist": load_legacy_json_mapping(paths.watchlist),
        "hidden": load_legacy_json_mapping(paths.hidden),
        "settings": load_legacy_json_mapping(paths.settings),
        "poster_cache": load_legacy_json_mapping(paths.poster_cache),
    }
    report = {
        "ok": True,
        "dry_run": dry_run,
        "db_path": str(target_db),
        "backup_dir": None,
        "counts": {name: len(value) for name, value in payloads.items()},
    }
    if dry_run:
        return report

    if create_backup:
        report["backup_dir"] = str(backup_legacy_json(paths))

    watched_repository.save_dataset_dict(payloads["watched"], path=target_db)
    watched_repository.save_meta_dict(payloads["meta"], path=target_db)
    candidate_repository.save_candidate_pool_dict(
        payloads["candidate_pool"],
        path=target_db,
        purge_watched=False,
    )
    candidate_repository.save_candidate_criteria_dict(
        payloads["candidate_criteria"],
        path=target_db,
    )
    action_repository.save_candidate_actions_dict(
        action_repository.ACTION_WATCHLIST,
        payloads["watchlist"],
        path=target_db,
    )
    action_repository.save_candidate_actions_dict(
        action_repository.ACTION_HIDDEN,
        payloads["hidden"],
        path=target_db,
    )
    settings_repository.save_settings_dict(payloads["settings"], path=target_db)
    poster_repository.save_poster_cache_dict(payloads["poster_cache"], path=target_db)
    return report

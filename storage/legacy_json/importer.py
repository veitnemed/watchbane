"""Explicit import of legacy JSON data into SQLite."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil

from dataset.models.user_rating import is_valid_user_rating, legacy_score_to_user_rating

from storage.sqlite import action_repository
from storage.sqlite import candidate_repository
from storage.sqlite import poster_repository
from storage.sqlite import settings_repository
from storage.sqlite import watched_repository
from storage.sqlite.connection import get_db_path
from storage.sqlite.backup import backup_sqlite_database
from storage.sqlite.connection import connect
from storage.sqlite.migrations import apply_migrations
from storage.legacy_json.exporter import (
    CANONICAL_RATING_SCALE,
    LEGACY_EXPORT_MANIFEST,
    LEGACY_EXPORT_SCHEMA_VERSION,
)


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
    manifest: Path


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
        manifest=base / LEGACY_EXPORT_MANIFEST,
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
        paths.manifest,
    )


def _export_rating_metadata(paths: LegacyJsonPaths) -> tuple[int | None, str | None]:
    if not paths.manifest.is_file():
        return None, None
    manifest = load_legacy_json_mapping(paths.manifest)
    version = manifest.get("schema_version")
    if manifest.get("format") != "watchbane-legacy-json" or type(version) is not int:
        raise ValueError(f"Unsupported Watchbane export schema version: {version!r}")
    if version == 1 and set(manifest) == {"format", "schema_version"}:
        # Version 1 was introduced after the SQLite migration to reactions.
        return 1, None
    if version != LEGACY_EXPORT_SCHEMA_VERSION:
        raise ValueError(f"Unsupported Watchbane export schema version: {version!r}")
    digest = manifest.get("watched_titles_sha256")
    if (manifest.get("watched_rating_scale") != CANONICAL_RATING_SCALE
            or not isinstance(digest, str) or len(digest) != 64
            or any(char not in "0123456789abcdef" for char in digest)):
        raise ValueError("Invalid Watchbane export rating metadata")
    return version, digest


def _load_watched_for_import(paths: LegacyJsonPaths, version: int | None, digest: str | None) -> dict:
    if version is None:
        watched = load_legacy_json_mapping(paths.titles)
        for record in watched.values():
            if not isinstance(record, dict):
                continue
            main_info = record.get("main_info")
            if isinstance(main_info, dict):
                main_info["user_score"] = legacy_score_to_user_rating(main_info.get("user_score"))
        return watched

    if not paths.titles.is_file():
        raise ValueError("Export is missing watched/titles.json")
    raw = paths.titles.read_bytes()
    if digest is not None and hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError("Watched ratings file does not match Watchbane export metadata")
    watched = json.loads(raw.decode("utf-8-sig"))
    if not isinstance(watched, dict):
        raise ValueError("Invalid Watchbane watched titles mapping")
    for record in watched.values():
        if not isinstance(record, dict):
            raise ValueError("Invalid Watchbane watched title record")
        main_info = record.get("main_info")
        if main_info is not None and not isinstance(main_info, dict):
            raise ValueError("Invalid Watchbane watched title metadata")
        for value in (record.get("user_score"), (main_info or {}).get("user_score")):
            if value is not None and not is_valid_user_rating(value):
                raise ValueError("Invalid canonical Watchbane rating; expected 1, 2, 3 or null")
    return watched


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
    export_version, rating_digest = _export_rating_metadata(paths)

    payloads = {
        "watched": _load_watched_for_import(paths, export_version, rating_digest),
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
        "runtime_backup": None,
        "schema_version": LEGACY_EXPORT_SCHEMA_VERSION,
        "counts": {name: len(value) for name, value in payloads.items()},
    }
    if dry_run:
        return report

    if create_backup:
        report["backup_dir"] = str(backup_legacy_json(paths))
    if target_db.is_file():
        report["runtime_backup"] = str(
            backup_sqlite_database(db_path=target_db, backup_dir=paths.backup_dir)
        )

    active = connect(target_db)
    try:
        apply_migrations(active)
        with active:
            watched_repository.save_dataset_dict(payloads["watched"], conn=active)
            watched_repository.save_meta_dict(payloads["meta"], conn=active)
            candidate_repository.save_candidate_pool_dict(
                payloads["candidate_pool"],
                conn=active,
                purge_watched=False,
            )
            candidate_repository.save_candidate_criteria_dict(
                payloads["candidate_criteria"],
                conn=active,
            )
            action_repository.save_candidate_actions_dict(
                action_repository.ACTION_WATCHLIST,
                payloads["watchlist"],
                conn=active,
            )
            action_repository.save_candidate_actions_dict(
                action_repository.ACTION_HIDDEN,
                payloads["hidden"],
                conn=active,
            )
            settings_repository.save_settings_dict(payloads["settings"], conn=active)
            poster_repository.save_poster_cache_dict(payloads["poster_cache"], conn=active)
    finally:
        active.close()
    return report

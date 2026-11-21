"""Explicit export of SQLite runtime data to legacy JSON files."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory

from storage.sqlite import action_repository
from storage.sqlite import candidate_repository
from storage.sqlite import poster_repository
from storage.sqlite import settings_repository
from storage.sqlite import watched_repository
from storage.sqlite.connection import get_db_path
from storage.sqlite.migrations import MIGRATIONS


LEGACY_EXPORT_SCHEMA_VERSION = 3
CANONICAL_RATING_SCALE = "watchbane-reaction-1-to-3"
LEGACY_EXPORT_MANIFEST = "_watchbane_export.json"
LEGACY_EXPORT_V3_MARKER = "_watchbane_export_v3"


def _dump_mapping(path: Path, payload: dict, *, digest: bool = False) -> str | None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = None
    try:
        with NamedTemporaryFile(
            mode="w+", encoding="utf-8", dir=path.parent,
            prefix=f".{path.name}.", suffix=".tmp", delete=False,
        ) as file:
            temp_path = Path(file.name)
            json.dump(payload, file, ensure_ascii=False, indent=4)
            file.write("\n")
            checksum = None
            if digest:
                file.flush()
                file.buffer.seek(0)
                checksum = hashlib.file_digest(file.buffer, "sha256").hexdigest()
        os.replace(temp_path, path)
        return checksum
    finally:
        if temp_path is not None:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass


def _read_payloads(source_db: Path) -> dict:
    conn = sqlite3.connect(source_db.resolve().as_uri() + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("BEGIN")
        # Repository readers check migrations. Require the current schema on
        # this read-only snapshot before invoking them; never migrate the source.
        versions = {row[0]: row[1] for row in conn.execute(
            "SELECT version, name FROM schema_migrations"
        )}
        if versions != {item.version: item.name for item in MIGRATIONS}:
            raise ValueError("Open and migrate the Watchbane database before exporting")
        return {
            "watched/titles.json": watched_repository.load_dataset_dict(conn=conn),
            "watched/meta.json": watched_repository.load_meta_dict(conn=conn),
            "candidates/pool.json": candidate_repository.load_candidate_pool_dict(conn=conn),
            "candidates/criteria.json": candidate_repository.load_candidate_criteria_dict(conn=conn),
            "candidates/watchlist.json": action_repository.load_candidate_actions_dict(
                action_repository.ACTION_WATCHLIST, conn=conn,
            ),
            "candidates/hidden.json": action_repository.load_candidate_actions_dict(
                action_repository.ACTION_HIDDEN, conn=conn,
            ),
            "settings.json": settings_repository.load_settings_dict(conn=conn),
            "cache/posters/posters.json": poster_repository.load_poster_cache_dict(conn=conn),
        }
    finally:
        conn.close()


def _require_empty_destination(path: Path) -> None:
    if path.is_symlink() or (path.exists() and (not path.is_dir() or any(path.iterdir()))):
        raise FileExistsError("Choose a new or empty directory for the Watchbane export")


def export_sqlite_to_legacy_json(
    *,
    output_dir: str | Path,
    db_path: str | Path | None = None,
) -> dict:
    """Publish a consistent export to a new or empty output directory."""
    target_dir = Path(output_dir).absolute()
    source_db = Path(db_path) if db_path is not None else get_db_path()
    _require_empty_destination(target_dir)
    payloads = _read_payloads(source_db)

    target_dir.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".watchbane-export-", dir=target_dir.parent) as staging:
        bundle = Path(staging) / "bundle"
        checksums = {
            relative: _dump_mapping(bundle / relative, payload, digest=True)
            for relative, payload in payloads.items()
        }
        # Prevent accidental manifest deletion from turning this bundle
        # into an apparent unmanifested 0–10 legacy dataset.
        (bundle / LEGACY_EXPORT_V3_MARKER).touch()
        _dump_mapping(bundle / LEGACY_EXPORT_MANIFEST, {
            "format": "watchbane-legacy-json",
            "schema_version": LEGACY_EXPORT_SCHEMA_VERSION,
            "watched_rating_scale": CANONICAL_RATING_SCALE,
            "files_sha256": checksums,
        })
        # rmdir cannot remove a competitor's published nonempty bundle.
        # POSIX rename can replace only an empty directory; Windows refuses
        # existing destinations, hence rmdir for an intentional empty output.
        _require_empty_destination(target_dir)
        try:
            target_dir.rmdir()
        except FileNotFoundError:
            pass
        os.rename(bundle, target_dir)

    return {
        "ok": True,
        "db_path": str(source_db),
        "output_dir": str(output_dir),
        "counts": {relative_path: len(payload) for relative_path, payload in payloads.items()},
        "schema_version": LEGACY_EXPORT_SCHEMA_VERSION,
    }

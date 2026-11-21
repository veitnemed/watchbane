"""Explicit export of SQLite runtime data to legacy JSON files."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from storage.sqlite import action_repository
from storage.sqlite import candidate_repository
from storage.sqlite import poster_repository
from storage.sqlite import settings_repository
from storage.sqlite import watched_repository
from storage.sqlite.connection import get_db_path


LEGACY_EXPORT_SCHEMA_VERSION = 2
CANONICAL_RATING_SCALE = "watchbane-reaction-1-to-3"
LEGACY_EXPORT_MANIFEST = "_watchbane_export.json"


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


def export_sqlite_to_legacy_json(
    *,
    output_dir: str | Path,
    db_path: str | Path | None = None,
) -> dict:
    """Export current SQLite state to legacy-compatible JSON files."""
    target_dir = Path(output_dir)
    source_db = Path(db_path) if db_path is not None else get_db_path()

    payloads = {
        "watched/titles.json": watched_repository.load_dataset_dict(path=source_db),
        "watched/meta.json": watched_repository.load_meta_dict(path=source_db),
        "candidates/pool.json": candidate_repository.load_candidate_pool_dict(path=source_db),
        "candidates/criteria.json": candidate_repository.load_candidate_criteria_dict(path=source_db),
        "candidates/watchlist.json": action_repository.load_candidate_actions_dict(
            action_repository.ACTION_WATCHLIST,
            path=source_db,
        ),
        "candidates/hidden.json": action_repository.load_candidate_actions_dict(
            action_repository.ACTION_HIDDEN,
            path=source_db,
        ),
        "settings.json": settings_repository.load_settings_dict(path=source_db),
        "cache/posters/posters.json": poster_repository.load_poster_cache_dict(path=source_db),
    }

    watched_digest = _dump_mapping(
        target_dir / "watched/titles.json", payloads["watched/titles.json"], digest=True,
    )
    for relative_path, payload in payloads.items():
        if relative_path != "watched/titles.json":
            _dump_mapping(target_dir / relative_path, payload)
    _dump_mapping(
        target_dir / LEGACY_EXPORT_MANIFEST,
        {
            "format": "watchbane-legacy-json",
            "schema_version": LEGACY_EXPORT_SCHEMA_VERSION,
            "watched_rating_scale": CANONICAL_RATING_SCALE,
            "watched_titles_sha256": watched_digest,
        },
    )

    return {
        "ok": True,
        "db_path": str(source_db),
        "output_dir": str(target_dir),
        "counts": {relative_path: len(payload) for relative_path, payload in payloads.items()},
        "schema_version": LEGACY_EXPORT_SCHEMA_VERSION,
    }

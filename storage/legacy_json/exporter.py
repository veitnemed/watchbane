"""Explicit export of SQLite runtime data to legacy JSON files."""

from __future__ import annotations

import json
import os
from pathlib import Path

from storage.sqlite import action_repository
from storage.sqlite import candidate_repository
from storage.sqlite import poster_repository
from storage.sqlite import settings_repository
from storage.sqlite import watched_repository
from storage.sqlite.connection import get_db_path


def _dump_mapping(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.tmp")
    try:
        with temp_path.open("w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=4)
            file.write("\n")
        os.replace(temp_path, path)
    except Exception:
        try:
            temp_path.unlink()
        except OSError:
            pass
        raise


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

    for relative_path, payload in payloads.items():
        _dump_mapping(target_dir / relative_path, payload)

    return {
        "ok": True,
        "db_path": str(source_db),
        "output_dir": str(target_dir),
        "counts": {relative_path: len(payload) for relative_path, payload in payloads.items()},
    }

"""TMDb snapshot build, preview, import, and save use cases."""

from __future__ import annotations

import json
from pathlib import Path

from candidates.sources.tmdb import builder as tmdb_build
from candidates.sources.tmdb import importer as tmdb_import


def get_tmdb_import_files_view() -> dict:
    """Return available TMDb result JSON files for import UI."""
    files = tmdb_import.list_tmdb_result_files()
    return {"files": files, "file_names": [path.name for path in files], "is_empty": len(files) == 0}


def load_tmdb_result_import_preview(result_path: str | Path) -> dict:
    """Load a TMDb result JSON preview without mutating the pool."""
    result_path = Path(result_path)
    try:
        with open(result_path, "r", encoding="utf-8-sig") as file:
            result = json.load(file)
    except (OSError, json.JSONDecodeError) as error:
        return {"ok": False, "error": str(error), "result_path": result_path, "candidates": [], "candidate_count": 0, "default_criteria_name": ""}
    candidates = result.get("candidates") if isinstance(result, dict) else None
    if isinstance(candidates, list) is False:
        return {"ok": False, "error": "Р’ С„Р°Р№Р»Рµ РЅРµС‚ СЃРїРёСЃРєР° candidates.", "result_path": result_path, "candidates": [], "candidate_count": 0, "default_criteria_name": ""}
    return {
        "ok": True, "error": None, "result_path": result_path, "result": result,
        "candidates": candidates, "candidate_count": len(candidates),
        "default_criteria_name": tmdb_import.tmdb_import_default_criteria_name(result) or "",
    }


def import_tmdb_result_to_pool(result_path: str | Path, criteria_name: str | None = None) -> dict:
    """Import a TMDb result JSON into the common candidate pool."""
    result_path = Path(result_path)
    stats = tmdb_import.import_tmdb_result_to_common_pool(result_path, criteria_name=criteria_name)
    return {
        "ok": stats.get("ok", False), "stats": stats, "result_file": str(result_path),
        "criteria_name": stats.get("criteria_name") or criteria_name, "error": stats.get("error"),
    }


def build_tmdb_criteria_name(country: str, mode: str, year_min: int | None = None, min_tmdb_score: float | None = None) -> str:
    """Return a default criteria name for the TMDb build flow."""
    return tmdb_build.build_tmdb_criteria_name(country, mode, year_min=year_min, min_tmdb_score=min_tmdb_score)


def build_tmdb_candidate_pool(country: str, pages: int = 3, details_limit: int = 50, mode: str = "quality", criteria_name: str | None = None, year_min: int | None = None, year_max: int | None = None, min_tmdb_score: float | None = None, min_tmdb_votes: int | None = None, with_genres: str | None = None, without_genres: str | None = None, force_refresh: bool = False, skip_existing_pool: bool = True, language: str | None = None, media_type: str | None = None) -> dict:
    """Build a TMDb-only candidate snapshot via the discover/details path."""
    return tmdb_build.build_candidate_pool(
        country=country, pages=pages, details_limit=details_limit, mode=mode, criteria_name=criteria_name,
        year_min=year_min, year_max=year_max, min_tmdb_score=min_tmdb_score, min_tmdb_votes=min_tmdb_votes,
        with_genres=with_genres, without_genres=without_genres, force_refresh=force_refresh,
        skip_existing_pool=skip_existing_pool, language=language, media_type=media_type,
    )


def save_tmdb_build_result(result: dict, *, is_test_run: bool = False) -> dict:
    """Save a TMDb build snapshot JSON/CSV through the established write path."""
    json_path, csv_path = (
        tmdb_build.save_candidate_pool_test_result(result)
        if is_test_run else tmdb_build.save_candidate_pool_result(result)
    )
    return {"ok": True, "json_path": json_path, "csv_path": csv_path, "is_test_run": is_test_run, "criteria_name": result.get("criteria_name")}


def build_and_save_tmdb_candidate_pool(*, is_test_run: bool = False, **build_kwargs) -> dict:
    """Build and save a TMDb snapshot without automatically importing it."""
    try:
        result = build_tmdb_candidate_pool(**build_kwargs)
    except Exception as error:
        return {"ok": False, "error": str(error), "result": None, "json_path": None, "csv_path": None, "criteria_name": build_kwargs.get("criteria_name"), "is_test_run": is_test_run, "stats": {}, "candidates": []}
    save_result = save_tmdb_build_result(result, is_test_run=is_test_run)
    return {
        "ok": True, "error": None, "result": result, "json_path": save_result["json_path"],
        "csv_path": save_result["csv_path"], "criteria_name": result.get("criteria_name") or build_kwargs.get("criteria_name"),
        "is_test_run": is_test_run, "stats": result.get("stats") or {}, "candidates": result.get("candidates") or [],
    }

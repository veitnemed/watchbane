"""Refresh current SQLite candidate pool entries from TMDb Details."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from apis import tmdb_api
from candidates.models.schema import normalize_candidate_for_storage, resolve_canonical_year, strip_external_rating_fields
from candidates.repositories import pool_repository
from candidates.sources.tmdb.normalizer import prepare_tmdb_candidate
from candidates.sources.tmdb.scoring import (
    compute_metadata_completeness_score,
    compute_tmdb_final_score,
    compute_tmdb_hidden_gem_score,
    compute_tmdb_quality_score,
)
from posters.fetch_watched_tmdb import match_tmdb_search_result

REPORT_PATH = ROOT_DIR / "data" / "diagnostics" / "candidate_pool_tmdb_refresh_report.json"
LOCAL_FIELD_NAMES = {
    "hidden",
    "hidden_at",
    "hidden_reason",
    "notes",
    "user_notes",
    "criteria_name",
    "added_at",
    "saved_at",
    "source_trace",
    "source_query",
    "custom_flags",
    "tags",
}


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def candidate_pool_path() -> Path:
    from storage.sqlite.connection import get_db_path

    return get_db_path()


def backup_path_for(pool_path: Path, timestamp: str) -> Path:
    return pool_path.with_name(f"{pool_path.stem}.candidate_pool.before_tmdb_refresh.{timestamp}.json")


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=4)


def _has_tmdb_id(candidate: dict[str, Any]) -> bool:
    value = candidate.get("tmdb_id")
    return value is not None and str(value).strip() != ""


def _local_fields(candidate: dict[str, Any]) -> dict[str, Any]:
    preserved = {}
    for key, value in candidate.items():
        if key in LOCAL_FIELD_NAMES or key.startswith("custom_") or key.startswith("user_"):
            preserved[key] = value
    return strip_external_rating_fields(preserved)


def _score_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    candidate["metadata_completeness_score"] = compute_metadata_completeness_score(candidate)
    candidate["quality_score"] = compute_tmdb_quality_score(candidate)
    candidate["hidden_gem_score"] = compute_tmdb_hidden_gem_score(candidate)
    candidate["final_score"] = compute_tmdb_final_score(candidate)
    candidate["completeness_score"] = candidate["metadata_completeness_score"]
    return normalize_candidate_for_storage(candidate)


def _prepare_refreshed_candidate(
    original: dict[str, Any],
    raw_details: dict[str, Any],
) -> dict[str, Any]:
    refreshed = prepare_tmdb_candidate(
        raw_details,
        country=(original.get("country_codes") or [None])[0] if isinstance(original.get("country_codes"), list) else None,
        source_query=original.get("source_query") if isinstance(original.get("source_query"), dict) else {},
        source_trace=original.get("source_trace"),
    )
    refreshed.update(_local_fields(original))
    refreshed["source"] = "tmdb"
    refreshed["source_provider"] = "tmdb"
    refreshed["source_version"] = 2
    return _score_candidate(strip_external_rating_fields(refreshed))


def _search_match(candidate: dict[str, Any], *, force_refresh: bool, token: str | None) -> tuple[dict[str, Any] | None, str]:
    title = candidate.get("title") or candidate.get("original_title") or ""
    year = resolve_canonical_year(candidate)
    if not title or year is None:
        return None, "failed"
    results = tmdb_api.search_tv_by_name(title, token=token)
    matched, status = match_tmdb_search_result(title, year, results)
    if status != "matched" or matched is None:
        return None, "needs_manual_match" if status == "uncertain_match" else "failed"
    try:
        details = tmdb_api.get_tv_details(
            int(matched["id"]),
            append_to_response=tmdb_api.DEFAULT_TV_DETAIL_APPENDS,
            force_refresh=force_refresh,
            token=token,
        )
    except Exception:
        return None, "failed"
    return details, "matched_by_search"


def refresh_candidate(
    candidate: dict[str, Any],
    *,
    force_refresh: bool = False,
    token: str | None = None,
) -> tuple[dict[str, Any], str]:
    if _has_tmdb_id(candidate):
        try:
            details = tmdb_api.get_tv_details(
                int(candidate["tmdb_id"]),
                append_to_response=tmdb_api.DEFAULT_TV_DETAIL_APPENDS,
                force_refresh=force_refresh,
                token=token,
            )
        except Exception:
            return strip_external_rating_fields(candidate), "failed"
        return _prepare_refreshed_candidate(candidate, details), "refreshed_by_tmdb_id"

    details, status = _search_match(candidate, force_refresh=force_refresh, token=token)
    if details is None:
        return strip_external_rating_fields(candidate), status
    return _prepare_refreshed_candidate(candidate, details), status


def refresh_pool(
    pool: dict[str, Any],
    *,
    limit: int | None = None,
    only_missing: bool = False,
    force_refresh: bool = False,
    token: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    refreshed_pool: dict[str, Any] = {}
    stats = {
        "total": len(pool) if isinstance(pool, dict) else 0,
        "processed": 0,
        "refreshed_by_tmdb_id": 0,
        "matched_by_search": 0,
        "needs_manual_match": 0,
        "failed": 0,
        "complete_after_refresh": 0,
        "incomplete_after_refresh": 0,
    }
    if isinstance(pool, dict) is False:
        return {}, stats

    remaining = None if limit is None else max(0, int(limit))
    for key, candidate in pool.items():
        if isinstance(candidate, dict) is False:
            refreshed_pool[key] = candidate
            continue
        if only_missing and _has_tmdb_id(candidate):
            updated = normalize_candidate_for_storage(strip_external_rating_fields(candidate))
            refreshed_pool[key] = updated
        elif remaining == 0:
            updated = normalize_candidate_for_storage(strip_external_rating_fields(candidate))
            refreshed_pool[key] = updated
        else:
            updated, status = refresh_candidate(candidate, force_refresh=force_refresh, token=token)
            updated = normalize_candidate_for_storage(strip_external_rating_fields(updated))
            refreshed_pool[key] = updated
            stats["processed"] += 1
            if remaining is not None:
                remaining -= 1
            if status in {"refreshed_by_tmdb_id", "matched_by_search", "needs_manual_match", "failed"}:
                stats[status] += 1

        if refreshed_pool[key].get("is_complete") is True:
            stats["complete_after_refresh"] += 1
        else:
            stats["incomplete_after_refresh"] += 1
    return refreshed_pool, stats


def build_report(*, mode: str, pool_path: Path, backup_path: Path | None, stats: dict[str, Any]) -> dict[str, Any]:
    return {
        "mode": mode,
        "pool_path": str(pool_path),
        "backup_path": str(backup_path) if backup_path is not None else None,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        **stats,
    }


def run_refresh(
    *,
    apply: bool,
    limit: int | None = None,
    only_missing: bool = False,
    force_refresh: bool = False,
    report_path: Path = REPORT_PATH,
) -> dict[str, Any]:
    pool_path = candidate_pool_path()
    original_pool = pool_repository.load_candidate_pool()
    token = tmdb_api.load_tmdb_token()
    refreshed_pool, stats = refresh_pool(
        original_pool,
        limit=limit,
        only_missing=only_missing,
        force_refresh=force_refresh,
        token=token,
    )

    backup_path = None
    if apply:
        backup_path = backup_path_for(pool_path, _timestamp())
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        write_json(backup_path, original_pool)
        pool_repository.save_candidate_pool(refreshed_pool)

    report = build_report(
        mode="apply" if apply else "dry-run",
        pool_path=pool_path,
        backup_path=backup_path,
        stats=stats,
    )
    write_json(report_path, report)
    return report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh the SQLite candidate pool from TMDb.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Refresh in memory and write report only.")
    mode.add_argument("--apply", action="store_true", help="Backup and rewrite the SQLite candidate pool.")
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of candidates to refresh.")
    parser.add_argument("--only-missing", action="store_true", help="Refresh only candidates without tmdb_id.")
    parser.add_argument("--force-refresh", action="store_true", help="Force TMDb details cache refresh.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = run_refresh(
        apply=args.apply,
        limit=args.limit,
        only_missing=args.only_missing,
        force_refresh=args.force_refresh,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

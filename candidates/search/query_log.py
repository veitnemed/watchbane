"""Local JSONL log for desktop search queries and result breadcrumbs.

Privacy-safe, opt-in (``WATCHBANE_LOG_SEARCH_QUERIES=1``), append-only. One row
per finalized search result and optional best-effort action breadcrumbs
(open/hide/watched). Nothing is sent anywhere; ``reports/`` is git-ignored.

This module does not change ranking, filters or TMDb Discover behavior.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from candidates.onboarding.request_log import current_git_commit, utc_timestamp
from diagnostics.log_sanitize import _sanitize_text, sanitize_log_entry

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LOG_PATH = PROJECT_ROOT / "reports" / "search" / "user_queries" / "search_query_log.jsonl"
SEARCH_QUERY_LOG_ENV = "WATCHBANE_LOG_SEARCH_QUERIES"
TOP_RESULTS_LIMIT = 20


def is_search_query_log_enabled() -> bool:
    return os.environ.get(SEARCH_QUERY_LOG_ENV) == "1"


def normalize_query(query: str | None) -> str:
    return str(query or "").strip().casefold()


def _candidate_tmdb_id(candidate: dict) -> Any:
    tmdb_id = candidate.get("tmdb_id")
    if tmdb_id in (None, ""):
        source_query = candidate.get("source_query")
        if isinstance(source_query, dict):
            tmdb_id = source_query.get("tmdb_id")
    return tmdb_id if tmdb_id not in (None, "") else None


def _candidate_title(candidate: dict) -> str:
    for key in ("title", "name", "original_title", "original_name"):
        value = candidate.get(key)
        if value not in (None, ""):
            return str(value)
    return ""


def _coerce_float(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def build_top_results(candidates: list[dict], limit: int = TOP_RESULTS_LIMIT) -> list[dict]:
    """Reduce visible candidates to compact top-N ranking rows."""
    rows: list[dict] = []
    for rank, candidate in enumerate(candidates[:limit], start=1):
        if not isinstance(candidate, dict):
            continue
        rows.append(
            {
                "rank": rank,
                "tmdb_id": _candidate_tmdb_id(candidate),
                "title": _candidate_title(candidate),
                "final_score": _coerce_float(candidate.get("final_score")),
            }
        )
    return rows


def build_search_query_entry(
    *,
    search_id: str | None,
    query: str | None,
    filters: dict | None,
    sort_mode: str | None,
    result_count: int,
    top_candidates: list[dict],
    latency_ms: float | int | None = None,
    top_limit: int = TOP_RESULTS_LIMIT,
) -> dict[str, Any]:
    """Build one finalized-search log record (``event="search"``)."""
    return {
        "timestamp": utc_timestamp(),
        "git_commit": current_git_commit(),
        "search_id": search_id,
        "event": "search",
        "query": query or "",
        "normalized_query": normalize_query(query),
        "filters": dict(filters or {}),
        "sort_mode": sort_mode,
        "result_count": int(result_count),
        "zero_result": int(result_count) == 0,
        "latency_ms": latency_ms,
        "top_results": build_top_results(top_candidates, limit=top_limit),
    }


def build_search_action_entry(
    *,
    search_id: str | None,
    action: str,
    tmdb_id: Any = None,
    rank: int | None = None,
    query: str | None = None,
) -> dict[str, Any]:
    """Build one action breadcrumb record (``event="action"``)."""
    return {
        "timestamp": utc_timestamp(),
        "git_commit": current_git_commit(),
        "search_id": search_id,
        "event": "action",
        "action": action,
        "tmdb_id": tmdb_id if tmdb_id not in (None, "") else None,
        "rank": rank,
        "query": query or "",
        "normalized_query": normalize_query(query),
    }


def build_search_signature(entry: dict[str, Any]) -> tuple:
    """Dedup key for a finalized search: query + filters + result_count."""
    filters = entry.get("filters") or {}
    return (
        entry.get("normalized_query"),
        entry.get("sort_mode"),
        int(entry.get("result_count") or 0),
        json.dumps(filters, ensure_ascii=False, sort_keys=True, default=str),
    )


def append_search_query_log(
    entry: dict[str, Any],
    path: str | Path | None = None,
) -> str | None:
    """Append one sanitized JSONL row. Returns a warning on failure, never raises."""
    if not is_search_query_log_enabled():
        return None
    try:
        target = Path(path) if path is not None else DEFAULT_LOG_PATH
        target.parent.mkdir(parents=True, exist_ok=True)
        sanitized = sanitize_log_entry(entry)
        with target.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(sanitized, ensure_ascii=False, sort_keys=True))
            handle.write("\n")
    except Exception as error:
        message = _sanitize_text(str(error))
        return f"Search query log write failed: {error.__class__.__name__}: {message}"
    return None

"""Local report writer for filter-driven candidate replenish runs."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from candidates.replenish.filter_discover import (
    discover_params_have_broad_origin_fallback,
    discover_params_have_vote_rating_filters,
)

DEFAULT_REPORT_DIR = Path("data/reports/candidates/replenish")
LATEST_JSON = "filter_replenish_latest.json"
LATEST_MD = "filter_replenish_latest.md"
RUNS_JSONL = "filter_replenish_runs.jsonl"
_SENSITIVE_KEY_PARTS = (
    "token",
    "api_key",
    "authorization",
    "secret",
    "password",
)
_PATH_KEY_PARTS = (
    "db_path",
    "database_path",
    "runtime_path",
    "sqlite_path",
    "absolute_path",
)
_WATCHED_KEY_PARTS = (
    "watched_list",
    "full_watched",
    "watched_records",
)


def _is_absolute_path_text(value: str) -> bool:
    text = value.strip()
    return text.startswith("/") or text.startswith("\\") or (len(text) >= 3 and text[1:3] == ":\\")


def _sanitize_value(value: Any, *, key: str = "") -> Any:
    lowered_key = key.casefold()
    if any(part in lowered_key for part in _SENSITIVE_KEY_PARTS):
        return "<redacted_secret>"
    if any(part in lowered_key for part in _PATH_KEY_PARTS):
        return "<redacted_path>"
    if any(part in lowered_key for part in _WATCHED_KEY_PARTS):
        return "<redacted_watched_list>"
    if isinstance(value, dict):
        return {str(item_key): _sanitize_value(item_value, key=str(item_key)) for item_key, item_value in value.items()}
    if isinstance(value, list):
        return [_sanitize_value(item, key=key) for item in value]
    if isinstance(value, tuple):
        return [_sanitize_value(item, key=key) for item in value]
    if isinstance(value, str) and _is_absolute_path_text(value):
        return "<redacted_path>"
    return value


def sanitize_filter_replenish_report(payload: dict[str, Any]) -> dict[str, Any]:
    """Return report payload without tokens, absolute runtime paths, or watched lists."""
    return _sanitize_value(deepcopy(payload))


def _plan_summary(plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "target_add_count": plan.get("target_add_count"),
        "bucket_count": plan.get("bucket_count"),
        "country_plan": plan.get("country_plan") or {},
        "media_plan": plan.get("media_plan") or {},
        "broad_origin_allowed": plan.get("broad_origin_allowed"),
    }


def _no_vote_rating_discover_filters(samples: list[dict[str, Any]]) -> bool:
    return all(
        discover_params_have_vote_rating_filters(sample) is False
        and discover_params_have_broad_origin_fallback(sample) is False
        for sample in samples
    )


def build_filter_replenish_report_payload(
    result: dict[str, Any],
    *,
    timestamp: str | None = None,
    elapsed_ms: float | None = None,
) -> dict[str, Any]:
    """Build a stable JSON report payload from a replenish result."""
    samples = list(result.get("discover_params_sample") or [])
    payload = {
        "timestamp": timestamp or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "normalized_intent": (result.get("plan") or {}).get("intent")
        or (result.get("compatibility") or {}).get("intent")
        or {},
        "compatibility": result.get("compatibility") or {},
        "plan_summary": _plan_summary(result.get("plan") or {}),
        "before_pool_count": int(result.get("before_pool_count") or 0),
        "after_pool_count": int(result.get("after_pool_count") or 0),
        "requested": int(result.get("requested_count") or 0),
        "created": int(result.get("created_count") or 0),
        "saved": int(result.get("saved_count") or 0),
        "duplicates": int(result.get("duplicate_count") or 0),
        "watched_skipped": int(result.get("watched_skipped") or 0),
        "hidden_skipped": int(result.get("hidden_skipped") or 0),
        "rejected": int(result.get("rejected_count") or 0),
        "api_requests": int(result.get("api_requests") or 0),
        "details_requests": int(result.get("details_requests") or 0),
        "bucket_results": result.get("bucket_results") or [],
        "elapsed_ms": elapsed_ms,
        "added_sample": [
            {
                "title": candidate.get("title"),
                "year": candidate.get("year"),
                "media_type": candidate.get("media_type"),
                "tmdb_id": candidate.get("tmdb_id"),
            }
            for candidate in list(result.get("candidates") or [])[:5]
            if isinstance(candidate, dict)
        ],
        "discover_params_sample": samples[:5],
        "no_vote_rating_discover_filters": _no_vote_rating_discover_filters(samples),
        "ok": bool(result.get("ok")),
        "blocked": bool(result.get("blocked")),
        "cancelled": bool(result.get("cancelled")),
        "error": result.get("error"),
    }
    return sanitize_filter_replenish_report(payload)


def _markdown_report(payload: dict[str, Any]) -> str:
    plan = payload.get("plan_summary") or {}
    lines = [
        "# Filter Replenish Latest Run",
        "",
        f"- timestamp: {payload.get('timestamp')}",
        f"- ok: {payload.get('ok')}",
        f"- requested: {payload.get('requested')}",
        f"- created: {payload.get('created')}",
        f"- saved: {payload.get('saved')}",
        f"- duplicates: {payload.get('duplicates')}",
        f"- watched_skipped: {payload.get('watched_skipped')}",
        f"- hidden_skipped: {payload.get('hidden_skipped')}",
        f"- rejected: {payload.get('rejected')}",
        f"- api_requests: {payload.get('api_requests')}",
        f"- details_requests: {payload.get('details_requests')}",
        f"- before_pool_count: {payload.get('before_pool_count')}",
        f"- after_pool_count: {payload.get('after_pool_count')}",
        f"- no_vote_rating_discover_filters: {payload.get('no_vote_rating_discover_filters')}",
        "",
        "## Plan",
        "",
        f"- target_add_count: {plan.get('target_add_count')}",
        f"- bucket_count: {plan.get('bucket_count')}",
        f"- country_plan: {plan.get('country_plan')}",
        f"- media_plan: {plan.get('media_plan')}",
        f"- broad_origin_allowed: {plan.get('broad_origin_allowed')}",
        "",
        "## Added Sample",
        "",
    ]
    for candidate in payload.get("added_sample") or []:
        lines.append(
            f"- {candidate.get('title')} ({candidate.get('year')}, {candidate.get('media_type')}, tmdb={candidate.get('tmdb_id')})"
        )
    if not payload.get("added_sample"):
        lines.append("- none")
    return "\n".join(lines) + "\n"


def write_filter_replenish_report(
    result: dict[str, Any],
    *,
    output_dir: str | Path = DEFAULT_REPORT_DIR,
    timestamp: str | None = None,
    elapsed_ms: float | None = None,
) -> dict[str, str]:
    """Write latest JSON/Markdown and append JSONL for a replenish run."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    payload = build_filter_replenish_report_payload(
        result,
        timestamp=timestamp,
        elapsed_ms=elapsed_ms,
    )
    json_path = output_path / LATEST_JSON
    md_path = output_path / LATEST_MD
    jsonl_path = output_path / RUNS_JSONL
    json_text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    json_path.write_text(json_text + "\n", encoding="utf-8")
    md_path.write_text(_markdown_report(payload), encoding="utf-8")
    with jsonl_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        handle.write("\n")
    return {
        "json_path": str(json_path),
        "markdown_path": str(md_path),
        "jsonl_path": str(jsonl_path),
    }

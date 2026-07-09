"""Local JSONL log for onboarding candidate-pool request settings."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
from typing import Any

from diagnostics.log_sanitize import (
    MAX_TEXT_LENGTH,
    _POSIX_ABSOLUTE_PATH_RE,
    _SENSITIVE_KEY_RE,
    _SENSITIVE_TEXT_RE,
    _WINDOWS_ABSOLUTE_PATH_RE,
    _sanitize_text,
    _sanitize_value,
    sanitize_log_entry,
)

__all__ = [
    "MAX_TEXT_LENGTH",
    "_POSIX_ABSOLUTE_PATH_RE",
    "_SENSITIVE_KEY_RE",
    "_SENSITIVE_TEXT_RE",
    "_WINDOWS_ABSOLUTE_PATH_RE",
    "_sanitize_text",
    "_sanitize_value",
    "sanitize_log_entry",
    "OnboardingRequestLogEntry",
    "utc_timestamp",
    "current_git_commit",
    "is_onboarding_request_log_enabled",
    "append_onboarding_request_log",
    "PROJECT_ROOT",
    "DEFAULT_LOG_PATH",
    "ENV_FLAG",
]


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LOG_PATH = PROJECT_ROOT / "reports" / "onboarding" / "user_requests" / "onboarding_request_log.jsonl"
ENV_FLAG = "WATCHBANE_LOG_ONBOARDING_REQUESTS"


@dataclass(frozen=True)
class OnboardingRequestLogEntry:
    timestamp: str
    app_version: str | None
    git_commit: str | None
    ui_language: str | None
    selected_preset: str | None
    media_type: str | None
    animation_mode: str | None
    selected_countries: list[str]
    origin_preference: str | None
    release_preference: str | None
    vibe: str | None
    include_genres: list[int]
    exclude_genres: list[int]
    min_year: int | None
    max_year: int | None
    target_pool_size: int
    generated_candidates_count: int
    country_plan: dict[str, int]
    country_actual: dict[str, int]
    media_actual: dict[str, int]
    country_hit_rate: float
    fallback_used: bool
    broad_origin_requests: int
    discover_http_requests: int
    details_requests: int
    missing_overview_count: int
    weak_candidates_count: int
    garbage_candidates_count: int
    warnings: list[str]
    duration_ms: int
    status: str
    error_class: str | None = None
    error_message: str | None = None


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def current_git_commit() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=PROJECT_ROOT,
            text=True,
            encoding="utf-8",
            stderr=subprocess.DEVNULL,
            timeout=2,
        ).strip() or None
    except Exception:
        return None


def is_onboarding_request_log_enabled() -> bool:
    return os.environ.get(ENV_FLAG) == "1"


def append_onboarding_request_log(
    entry: OnboardingRequestLogEntry | dict[str, Any],
    path: str | Path | None = None,
) -> str | None:
    """Append one sanitized JSONL row. Returns a warning on failure, never raises."""
    if not is_onboarding_request_log_enabled():
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
        return f"Onboarding request log write failed: {error.__class__.__name__}: {message}"
    return None

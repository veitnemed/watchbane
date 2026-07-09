"""Local JSONL log for onboarding candidate-pool request settings."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LOG_PATH = PROJECT_ROOT / "reports" / "onboarding" / "user_requests" / "onboarding_request_log.jsonl"
ENV_FLAG = "WATCHBANE_LOG_ONBOARDING_REQUESTS"
MAX_TEXT_LENGTH = 500

_SENSITIVE_KEY_RE = re.compile(
    r"(api[_-]?key|authorization|bearer|credential|password|secret|token)",
    re.IGNORECASE,
)
_SENSITIVE_TEXT_RE = re.compile(
    r"\b(api[_-]?key|authorization|bearer|credential|password|secret|token)\s*[:=]\s*[^\s,;]+",
    re.IGNORECASE,
)
_WINDOWS_ABSOLUTE_PATH_RE = re.compile(r"(?<![\w:])[A-Za-z]:\\[^\r\n\t\"'<>|]+")
_POSIX_ABSOLUTE_PATH_RE = re.compile(r"(?<![\w:])/(?:[^\s\"'<>/]+/)+[^\s\"'<>]+")


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


def _sanitize_text(value: str) -> str:
    text = "".join(char for char in str(value) if (ord(char) >= 32 and ord(char) != 127))
    text = _SENSITIVE_TEXT_RE.sub(lambda match: f"{match.group(1)}=<redacted>", text)
    text = _WINDOWS_ABSOLUTE_PATH_RE.sub("<redacted_path>", text)
    text = _POSIX_ABSOLUTE_PATH_RE.sub("<redacted_path>", text)
    if len(text) > MAX_TEXT_LENGTH:
        return text[:MAX_TEXT_LENGTH].rstrip() + "..."
    return text


def _sanitize_value(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            key_text = _sanitize_text(str(key))
            if _SENSITIVE_KEY_RE.search(key_text):
                continue
            sanitized[key_text] = _sanitize_value(item)
        return sanitized
    if isinstance(value, (list, tuple, set)):
        return [_sanitize_value(item) for item in value]
    if isinstance(value, str):
        return _sanitize_text(value)
    if isinstance(value, Path):
        return "<redacted_path>" if value.is_absolute() else _sanitize_text(value.as_posix())
    return value


def sanitize_log_entry(entry: OnboardingRequestLogEntry | dict[str, Any]) -> dict[str, Any]:
    data = asdict(entry) if isinstance(entry, OnboardingRequestLogEntry) else dict(entry)
    return _sanitize_value(data)


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

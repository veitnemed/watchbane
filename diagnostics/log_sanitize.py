"""Shared privacy sanitizer for local JSONL diagnostics logs.

Strips API tokens (``key=value``), absolute runtime paths, sensitive keys and
control characters before anything is written to disk. Used by both the
onboarding request log and the search query log.
"""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from pathlib import Path
import re
from typing import Any

MAX_TEXT_LENGTH = 500

_SENSITIVE_KEY_RE = re.compile(
    r"(api[_-]?key|authorization|bearer|credential|password|secret|token)",
    re.IGNORECASE,
)
_PRIVATE_COLLECTION_KEY_RE = re.compile(
    r"(full[_-]?(collection|dataset|library)|watched[_-]?(records|list))",
    re.IGNORECASE,
)
_SENSITIVE_TEXT_RE = re.compile(
    r"\b(api[_-]?key|authorization|bearer|credential|password|secret|token)\s*[:=]\s*[^\s,;]+",
    re.IGNORECASE,
)
_WINDOWS_ABSOLUTE_PATH_RE = re.compile(r"(?<![\w:])[A-Za-z]:\\[^\r\n\t\"'<>|]+")
_POSIX_ABSOLUTE_PATH_RE = re.compile(r"(?<![\w:])/(?:[^\s\"'<>/]+/)+[^\s\"'<>]+")


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
            if _PRIVATE_COLLECTION_KEY_RE.search(key_text):
                sanitized[key_text] = "<redacted_collection>"
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


def sanitize_log_entry(entry: Any) -> dict[str, Any]:
    """Return a sanitized dict for a dataclass instance or plain mapping."""
    if is_dataclass(entry) and not isinstance(entry, type):
        data = asdict(entry)
    else:
        data = dict(entry)
    return _sanitize_value(data)

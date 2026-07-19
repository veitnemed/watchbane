"""Serializable result contract for filter replenish runs."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class FilterReplenishResult:
    ok: bool
    dry_run: bool
    blocked: bool = False
    cancelled: bool = False
    error: str | None = None
    requested_count: int = 0
    created_count: int = 0
    saved_count: int = 0
    duplicate_count: int = 0
    existing_skipped: int = 0
    watched_skipped: int = 0
    hidden_skipped: int = 0
    rejected_count: int = 0
    explicit_content_skipped: int = 0
    raw_seen_count: int = 0
    api_requests: int = 0
    details_requests: int = 0
    candidates: list[dict[str, Any]] = field(default_factory=list)
    compatibility: dict[str, Any] = field(default_factory=dict)
    plan: dict[str, Any] = field(default_factory=dict)
    bucket_results: list[dict[str, Any]] = field(default_factory=list)
    discover_params_sample: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

"""Pagination configuration for onboarding Discover sweeps."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


DEFAULT_DISCOVER_PAGES = 3
MAX_DISCOVER_PAGES = 5
ADAPTIVE_MAX_DISCOVER_PAGES = 10


def _coerce_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


@dataclass(frozen=True)
class PaginationConfig:
    default_pages: int = DEFAULT_DISCOVER_PAGES
    normal_max_pages: int = MAX_DISCOVER_PAGES
    adaptive_max_pages: int = ADAPTIVE_MAX_DISCOVER_PAGES
    continue_if_accepted_per_page_gte: int = 8
    stop_if_accepted_per_page_lt: int = 3
    stop_if_quota_full: bool = True

    def normalized(self, *, discover_pages: int = DEFAULT_DISCOVER_PAGES) -> "PaginationConfig":
        try:
            default_pages = int(self.default_pages or discover_pages or DEFAULT_DISCOVER_PAGES)
        except (TypeError, ValueError):
            default_pages = int(discover_pages or DEFAULT_DISCOVER_PAGES)
        try:
            normal_max_pages = int(self.normal_max_pages or MAX_DISCOVER_PAGES)
        except (TypeError, ValueError):
            normal_max_pages = MAX_DISCOVER_PAGES
        try:
            adaptive_max_pages = int(self.adaptive_max_pages or ADAPTIVE_MAX_DISCOVER_PAGES)
        except (TypeError, ValueError):
            adaptive_max_pages = ADAPTIVE_MAX_DISCOVER_PAGES
        normal_max_pages = max(default_pages, normal_max_pages)
        adaptive_max_pages = max(normal_max_pages, adaptive_max_pages)
        return PaginationConfig(
            default_pages=max(1, default_pages),
            normal_max_pages=max(1, normal_max_pages),
            adaptive_max_pages=max(1, adaptive_max_pages),
            continue_if_accepted_per_page_gte=max(0, _coerce_int(self.continue_if_accepted_per_page_gte, 8)),
            stop_if_accepted_per_page_lt=max(0, _coerce_int(self.stop_if_accepted_per_page_lt, 3)),
            stop_if_quota_full=bool(self.stop_if_quota_full),
        )

    def as_repository_dict(self) -> dict[str, Any]:
        return asdict(self.normalized())

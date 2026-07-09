"""Details enrichment configuration for onboarding candidate collection."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


DEFAULT_DETAILS_LIMIT_PER_TEMPLATE = 50


@dataclass(frozen=True)
class DetailsEnrichmentConfig:
    enabled: bool = True
    default_limit_per_bucket: int = DEFAULT_DETAILS_LIMIT_PER_TEMPLATE
    only_for_final_candidates: bool = True
    fetch_external_ids: bool = True
    fetch_tv_seasons_basic: bool = False
    lazy_tv_details_on_card_open: bool = True

    def normalized(self, *, details_limit: int = DEFAULT_DETAILS_LIMIT_PER_TEMPLATE) -> "DetailsEnrichmentConfig":
        try:
            limit = int(self.default_limit_per_bucket or details_limit or DEFAULT_DETAILS_LIMIT_PER_TEMPLATE)
        except (TypeError, ValueError):
            limit = int(details_limit or DEFAULT_DETAILS_LIMIT_PER_TEMPLATE)
        return DetailsEnrichmentConfig(
            enabled=bool(self.enabled),
            default_limit_per_bucket=max(0, limit),
            only_for_final_candidates=bool(self.only_for_final_candidates),
            fetch_external_ids=bool(self.fetch_external_ids),
            fetch_tv_seasons_basic=bool(self.fetch_tv_seasons_basic),
            lazy_tv_details_on_card_open=bool(self.lazy_tv_details_on_card_open),
        )

    def as_repository_dict(self) -> dict[str, Any]:
        return asdict(self.normalized())

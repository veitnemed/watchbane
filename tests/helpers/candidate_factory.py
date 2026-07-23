"""Technical candidate fixtures for tests (no taste-profile biographies)."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


def _base(
    *,
    media_type: str,
    tmdb_id: int,
    title: str,
    **overrides: Any,
) -> dict[str, Any]:
    candidate: dict[str, Any] = {
        "title": title,
        "original_title": title,
        "year": 2020,
        "media_type": media_type,
        "tmdb_id": tmdb_id,
        "final_score": 80.0,
        "tmdb_score": 7.5,
        "tmdb_votes": 500,
        "tmdb_popularity": 30.0,
        "country": "US",
        "country_codes": ["US"],
        "countries": ["US"],
        "genres": ["Drama"],
        "genres_tmdb": ["Drama"],
        "poster_path": f"/fixture-{tmdb_id}.jpg",
        "description": "Technical fixture overview.",
        "overview": "Technical fixture overview.",
        "adult": False,
        "source": "test_fixture",
    }
    candidate.update(overrides)
    return candidate


def safe_movie(**overrides: Any) -> dict[str, Any]:
    return _base(media_type="movie", tmdb_id=10_001, title="Safe Movie", adult=False, **overrides)


def adult_movie(**overrides: Any) -> dict[str, Any]:
    return _base(media_type="movie", tmdb_id=10_002, title="Adult Movie", adult=True, **overrides)


def partial_movie(**overrides: Any) -> dict[str, Any]:
    """Discover-like movie without Details-only fields."""
    return _base(
        media_type="movie",
        tmdb_id=10_003,
        title="Partial Movie",
        **overrides,
    )


def enriched_movie(**overrides: Any) -> dict[str, Any]:
    return _base(
        media_type="movie",
        tmdb_id=10_004,
        title="Enriched Movie",
        runtime=120,
        runtime_minutes=120,
        content_rating="16+",
        keywords=["drama"],
        adult=False,
        details_enrichment_contract_version=1,
        details_enrichment_status="success",
        details_enriched_at="2026-07-21T00:00:00+00:00",
        **overrides,
    )


def partial_tv(**overrides: Any) -> dict[str, Any]:
    return _base(media_type="tv", tmdb_id=20_001, title="Partial TV", **overrides)


def enriched_tv(**overrides: Any) -> dict[str, Any]:
    return _base(
        media_type="tv",
        tmdb_id=20_002,
        title="Enriched TV",
        episode_run_time=[45],
        number_of_seasons=2,
        number_of_episodes=20,
        content_rating="16",
        keywords=["mystery"],
        adult=False,
        details_enrichment_contract_version=1,
        details_enrichment_status="success",
        details_enriched_at="2026-07-21T00:00:00+00:00",
        **overrides,
    )


def localized_fallback(**overrides: Any) -> dict[str, Any]:
    return _base(
        media_type="tv",
        tmdb_id=20_003,
        title="",
        original_title="Original Only Title",
        overview="",
        description="",
        **overrides,
    )


def watched_hidden_candidate(**overrides: Any) -> dict[str, Any]:
    return _base(
        media_type="movie",
        tmdb_id=10_005,
        title="Hidden Candidate",
        final_score=-1000,
        **overrides,
    )


def as_pool(*candidates: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Build a pool dict with stable keys; does not mutate inputs."""
    pool: dict[str, dict[str, Any]] = {}
    for index, candidate in enumerate(candidates):
        item = deepcopy(candidate)
        key = f"fixture-{item.get('media_type')}-{item.get('tmdb_id')}-{index}"
        pool[key] = item
    return pool

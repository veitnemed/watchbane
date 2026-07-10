"""Mock TMDb fixtures for filter replenish tests."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any


RESULTS_PER_PAGE = 20


@dataclass(frozen=True)
class MockTmdbScenario:
    name: str
    description: str
    pages: dict[tuple[str, str], list[list[dict[str, Any]]]]
    watched_tmdb_ids: frozenset[int] = frozenset()
    hidden_tmdb_ids: frozenset[int] = frozenset()
    existing_tmdb_ids: frozenset[int] = frozenset()


@dataclass
class MockFilterReplenishTmdbClient:
    scenario: MockTmdbScenario
    discover_requests: list[dict[str, Any]] = field(default_factory=list)
    details_requests: list[dict[str, Any]] = field(default_factory=list)

    @property
    def api_request_count(self) -> int:
        return len(self.discover_requests) + len(self.details_requests)

    def discover(self, media_type: str, params: dict[str, Any]) -> dict[str, Any]:
        request = {
            "media_type": media_type,
            "params": deepcopy(params),
        }
        self.discover_requests.append(request)
        country = str(params.get("with_origin_country") or "any").upper()
        page_number = max(1, int(params.get("page") or 1))
        pages = self.scenario.pages.get((country, media_type), [])
        page_results = pages[page_number - 1] if page_number <= len(pages) else []
        return {
            "page": page_number,
            "total_pages": len(pages),
            "results": deepcopy(page_results),
        }

    def details(self, media_type: str, tmdb_id: int, *, language: str = "ru-RU") -> dict[str, Any]:
        self.details_requests.append({
            "media_type": media_type,
            "tmdb_id": int(tmdb_id),
            "language": language,
        })
        return mock_details(int(tmdb_id), media_type=media_type, language=language)


def _candidate(
    tmdb_id: int,
    *,
    title: str,
    media_type: str,
    country: str,
    year: int,
    genre_ids: list[int] | None = None,
    original_language: str | None = None,
) -> dict[str, Any]:
    base = {
        "id": tmdb_id,
        "overview": f"Mock overview for {title}.",
        "origin_country": [country],
        "genre_ids": list(genre_ids or []),
        "vote_average": 7.0 + (tmdb_id % 20) / 10,
        "vote_count": 100 + tmdb_id,
        "popularity": 1000.0 - tmdb_id,
        "original_language": original_language or country.casefold(),
    }
    if media_type == "tv":
        return {
            **base,
            "name": title,
            "original_name": title,
            "first_air_date": f"{year}-01-01",
        }
    return {
        **base,
        "title": title,
        "original_title": title,
        "release_date": f"{year}-01-01",
    }


def _page(
    *,
    start_id: int,
    count: int,
    prefix: str,
    media_type: str,
    country: str,
    year: int,
    genre_ids: list[int] | None = None,
    original_language: str | None = None,
) -> list[dict[str, Any]]:
    return [
        _candidate(
            start_id + index,
            title=f"{prefix} {index + 1}",
            media_type=media_type,
            country=country,
            year=year,
            genre_ids=genre_ids,
            original_language=original_language,
        )
        for index in range(count)
    ]


def _pages(*pages: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    return [list(page) for page in pages]


def mock_details(tmdb_id: int, *, media_type: str, language: str = "ru-RU") -> dict[str, Any]:
    title_key = "name" if media_type == "tv" else "title"
    date_key = "first_air_date" if media_type == "tv" else "release_date"
    return {
        "id": int(tmdb_id),
        title_key: f"Details {tmdb_id}",
        "overview": f"Localized {language} details for {tmdb_id}.",
        date_key: "2024-01-01",
        "runtime": 100 if media_type == "movie" else None,
        "episode_run_time": [45] if media_type == "tv" else [],
        "genres": [{"id": 18, "name": "Drama"}],
        "origin_country": ["US"],
        "vote_average": 7.4,
        "vote_count": 300,
        "popularity": 80.0,
    }


def _duplicate_heavy_pages() -> list[list[dict[str, Any]]]:
    first = _page(
        start_id=6000,
        count=10,
        prefix="Duplicate",
        media_type="movie",
        country="US",
        year=2024,
        genre_ids=[18],
        original_language="en",
    )
    second = deepcopy(first[:8]) + _page(
        start_id=7000,
        count=4,
        prefix="Unique Tail",
        media_type="movie",
        country="US",
        year=2024,
        genre_ids=[18],
        original_language="en",
    )
    return _pages(first, second)


SCENARIOS: dict[str, MockTmdbScenario] = {
    "ru_dark_tv_enough": MockTmdbScenario(
        name="ru_dark_tv_enough",
        description="RU dark TV has enough unique live-action candidates for +30.",
        pages={
            ("RU", "tv"): _pages(
                _page(start_id=1000, count=20, prefix="RU Dark TV", media_type="tv", country="RU", year=2021, genre_ids=[18, 80], original_language="ru"),
                _page(start_id=1020, count=20, prefix="RU Dark TV", media_type="tv", country="RU", year=2022, genre_ids=[18, 80], original_language="ru"),
            ),
        },
    ),
    "anime_jp_enough": MockTmdbScenario(
        name="anime_jp_enough",
        description="Anime JP returns enough Animation genre candidates.",
        pages={
            ("JP", "movie"): _pages(
                _page(start_id=2000, count=20, prefix="Anime JP Movie", media_type="movie", country="JP", year=2023, genre_ids=[16], original_language="ja"),
            ),
            ("JP", "tv"): _pages(
                _page(start_id=2020, count=20, prefix="Anime JP TV", media_type="tv", country="JP", year=2023, genre_ids=[16], original_language="ja"),
            ),
        },
    ),
    "k_drama_kr_live_tv": MockTmdbScenario(
        name="k_drama_kr_live_tv",
        description="K-drama KR TV returns live-action candidates without Animation genre.",
        pages={
            ("KR", "tv"): _pages(
                _page(start_id=3000, count=20, prefix="K Drama", media_type="tv", country="KR", year=2024, genre_ids=[18, 10749], original_language="ko"),
                _page(start_id=3020, count=12, prefix="K Drama", media_type="tv", country="KR", year=2024, genre_ids=[18], original_language="ko"),
            ),
        },
    ),
    "us_gb_new_movies_balanced": MockTmdbScenario(
        name="us_gb_new_movies_balanced",
        description="US/GB new movies can fill balanced country buckets.",
        pages={
            ("US", "movie"): _pages(
                _page(start_id=4000, count=20, prefix="US New Movie", media_type="movie", country="US", year=2024, genre_ids=[18], original_language="en"),
            ),
            ("GB", "movie"): _pages(
                _page(start_id=5000, count=20, prefix="GB New Movie", media_type="movie", country="GB", year=2024, genre_ids=[18], original_language="en"),
            ),
        },
    ),
    "sparse_tr_underfilled": MockTmdbScenario(
        name="sparse_tr_underfilled",
        description="Sparse TR scenario underfills and must not use broad-origin fallback.",
        pages={
            ("TR", "tv"): _pages(
                _page(start_id=8000, count=5, prefix="Sparse TR", media_type="tv", country="TR", year=2020, genre_ids=[18], original_language="tr"),
            ),
        },
    ),
    "duplicate_heavy": MockTmdbScenario(
        name="duplicate_heavy",
        description="Duplicate-heavy results prove TMDb/title dedupe before saving.",
        pages={
            ("US", "movie"): _duplicate_heavy_pages(),
        },
    ),
    "watched_hidden_overlap": MockTmdbScenario(
        name="watched_hidden_overlap",
        description="Results overlap watched, hidden, and existing-pool identities.",
        pages={
            ("US", "movie"): _pages(
                _page(start_id=9000, count=20, prefix="Overlap Movie", media_type="movie", country="US", year=2024, genre_ids=[18], original_language="en"),
            ),
        },
        watched_tmdb_ids=frozenset({9001, 9002}),
        hidden_tmdb_ids=frozenset({9003}),
        existing_tmdb_ids=frozenset({9004, 9005}),
    ),
}


def scenario_names() -> list[str]:
    return list(SCENARIOS)


def build_mock_tmdb_client(name: str) -> MockFilterReplenishTmdbClient:
    return MockFilterReplenishTmdbClient(SCENARIOS[name])

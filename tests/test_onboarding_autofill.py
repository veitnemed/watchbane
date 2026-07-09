from __future__ import annotations

import json
from collections import Counter
from itertools import combinations
from datetime import date

import pytest

import candidates.onboarding.request_log as request_log
from candidates.onboarding import autofill
from candidates.models.keys import pool_entry_key, title_identity_key
from candidates.onboarding.autofill import (
    ANIMATION_MODE_ANIMATION_ONLY,
    ANIMATION_MODE_ANY,
    ANIMATION_MODE_LIVE_ACTION_ONLY,
    MEDIA_MOVIE,
    MEDIA_TV,
    TMDB_ANIMATION_GENRE_ID,
    OnboardingTasteProfile,
    build_country_plan,
    build_discover_request,
    build_fetch_buckets,
    country_selection_for_foreign_ru,
    country_selection_for_manual,
    country_selection_for_mixed_ru,
    media_weights,
    origin_weights,
    release_weights,
    resolve_tmdb_genre_ids,
    run_onboarding_autofill,
    vibe_weights,
)
from candidates.onboarding.taste_presets import (
    PRESET_ANIME,
    PRESET_FAMILY_ANIMATION,
    PRESET_K_DRAMA,
    PRESET_MANUAL,
    PRESET_TURKISH_DRAMAS,
    taste_preset_to_profile_payload,
)
from storage.sqlite.connection import connect
from storage.sqlite.candidate_pool_repository import save_candidate_pool_dict
from storage.sqlite.onboarding_repository import load_autofill_request_audits


MOVIE_GENRES = [
    {"id": 35, "name": "Comedy"},
    {"id": 10749, "name": "Romance"},
    {"id": 14, "name": "Fantasy"},
    {"id": 10751, "name": "Family"},
    {"id": 12, "name": "Adventure"},
    {"id": 18, "name": "Drama"},
    {"id": 53, "name": "Thriller"},
    {"id": 28, "name": "Action"},
    {"id": 80, "name": "Crime"},
    {"id": 9648, "name": "Mystery"},
]
TV_GENRES = [
    {"id": 35, "name": "Comedy"},
    {"id": 10751, "name": "Family"},
    {"id": 16, "name": "Animation"},
    {"id": 10765, "name": "Sci-Fi & Fantasy"},
    {"id": 18, "name": "Drama"},
    {"id": 80, "name": "Crime"},
    {"id": 9648, "name": "Mystery"},
    {"id": 10759, "name": "Action & Adventure"},
    {"id": 10768, "name": "War & Politics"},
]


class FakeTmdbClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []
        self.details_calls: list[tuple[str, int, str, tuple[str, ...]]] = []

    def movie_genres(self, language: str = "en") -> list[dict]:
        assert language == "en"
        return list(MOVIE_GENRES)

    def tv_genres(self, language: str = "en") -> list[dict]:
        assert language == "en"
        return list(TV_GENRES)

    def discover(self, endpoint: str, params: dict) -> dict:
        self.calls.append((endpoint, dict(params)))
        media = MEDIA_MOVIE if endpoint == "/discover/movie" else MEDIA_TV
        call_index = len(self.calls)
        genre_text = str(params.get("with_genres") or "")
        genre_ids = [int(item) for item in genre_text.split("|") if item.isdigit()]
        if not genre_ids:
            genre_ids = [35] if media == MEDIA_MOVIE else [18]
        country = params.get("with_origin_country") or "US"
        results = []
        for index in range(20):
            tmdb_id = call_index * 1000 + index
            year = int(params.get("primary_release_year") or params.get("first_air_date_year") or 2024)
            if media == MEDIA_MOVIE:
                results.append(
                    {
                        "id": tmdb_id,
                        "title": f"Movie {tmdb_id}",
                        "original_title": f"Movie {tmdb_id}",
                        "release_date": f"{year}-01-01",
                        "poster_path": f"/m{tmdb_id}.jpg",
                        "overview": "Overview",
                        "genre_ids": genre_ids,
                        "origin_country": [country],
                        "vote_average": 7.2,
                        "vote_count": 1200,
                        "popularity": 50,
                        "original_language": params.get("with_original_language") or "en",
                    }
                )
            else:
                results.append(
                    {
                        "id": tmdb_id,
                        "name": f"Series {tmdb_id}",
                        "original_name": f"Series {tmdb_id}",
                        "first_air_date": f"{year}-01-01",
                        "origin_country": [country],
                        "poster_path": f"/t{tmdb_id}.jpg",
                        "overview": "Overview",
                        "genre_ids": genre_ids,
                        "vote_average": 7.1,
                        "vote_count": 500,
                        "popularity": 40,
                        "original_language": params.get("with_original_language") or "en",
                    }
                )
        return {"results": results, "total_pages": 5}

    def movie_details(self, tmdb_id: int, language: str = "en", *, append_to_response=None) -> dict:
        appends = tuple(append_to_response or ())
        self.details_calls.append((MEDIA_MOVIE, int(tmdb_id), language, appends))
        return {
            "id": int(tmdb_id),
            "title": f"Movie {int(tmdb_id)}",
            "original_title": f"Movie {int(tmdb_id)}",
            "release_date": "2024-01-01",
            "overview": "Detailed overview",
            "genres": [{"id": 18, "name": "Drama"}],
            "production_countries": [{"iso_3166_1": "US", "name": "United States"}],
            "vote_average": 8.0,
            "vote_count": 500,
            "popularity": 60,
            "poster_path": f"/dm{int(tmdb_id)}.jpg",
            "external_ids": {"imdb_id": f"tt{int(tmdb_id):07d}"},
        }

    def tv_details(self, tmdb_id: int, language: str = "en", *, append_to_response=None) -> dict:
        appends = tuple(append_to_response or ())
        self.details_calls.append((MEDIA_TV, int(tmdb_id), language, appends))
        return {
            "id": int(tmdb_id),
            "name": f"Series {int(tmdb_id)}",
            "original_name": f"Series {int(tmdb_id)}",
            "first_air_date": "2024-01-01",
            "overview": "Detailed overview",
            "genres": [{"id": 18, "name": "Drama"}],
            "origin_country": ["US"],
            "vote_average": 8.0,
            "vote_count": 500,
            "popularity": 60,
            "poster_path": f"/dt{int(tmdb_id)}.jpg",
            "external_ids": {"imdb_id": f"tt{int(tmdb_id):07d}"},
        }


class EmptyTmdbClient(FakeTmdbClient):
    def discover(self, endpoint: str, params: dict) -> dict:
        self.calls.append((endpoint, dict(params)))
        return {"results": [], "total_pages": 1}


class FailingGenreTmdbClient(FakeTmdbClient):
    def movie_genres(self, language: str = "en") -> list[dict]:
        raise RuntimeError("boom token=secret-token db=D:\\runtime\\watchbane.sqlite3")


class ScarceTvTmdbClient(FakeTmdbClient):
    def discover(self, endpoint: str, params: dict) -> dict:
        if endpoint == "/discover/tv":
            self.calls.append((endpoint, dict(params)))
            return {"results": [], "total_pages": 1}
        return super().discover(endpoint, params)


class FutureTmdbClient(FakeTmdbClient):
    def discover(self, endpoint: str, params: dict) -> dict:
        self.calls.append((endpoint, dict(params)))
        media = MEDIA_MOVIE if endpoint == "/discover/movie" else MEDIA_TV
        date_key = "release_date" if media == MEDIA_MOVIE else "first_air_date"
        title_key = "title" if media == MEDIA_MOVIE else "name"
        original_title_key = "original_title" if media == MEDIA_MOVIE else "original_name"
        results = []
        for index in range(20):
            tmdb_id = len(self.calls) * 1000 + index
            results.append(
                {
                    "id": tmdb_id,
                    title_key: f"Future {tmdb_id}",
                    original_title_key: f"Future {tmdb_id}",
                    date_key: "2027-01-01",
                    "poster_path": f"/f{tmdb_id}.jpg",
                    "overview": "Overview",
                    "genre_ids": [35],
                    "vote_average": 7.2,
                    "vote_count": 1200,
                    "popularity": 50,
                    "original_language": params.get("with_original_language") or "en",
                    "origin_country": ["RU"] if params.get("with_origin_country") == "RU" else ["US"],
                }
            )
        return {"results": results, "total_pages": 1}


class DuplicateDiscoverTmdbClient(FakeTmdbClient):
    def discover(self, endpoint: str, params: dict) -> dict:
        self.calls.append((endpoint, dict(params)))
        media = MEDIA_MOVIE if endpoint == "/discover/movie" else MEDIA_TV
        country = params.get("with_origin_country") or "US"
        if media == MEDIA_MOVIE:
            item = {
                "id": 101,
                "title": "Duplicate Movie",
                "original_title": "Duplicate Movie",
                "release_date": "2024-01-01",
                "poster_path": "/dup.jpg",
                "overview": "",
                "genre_ids": [18],
                "origin_country": [country],
                "vote_average": 8.0,
                "vote_count": 500,
                "popularity": 50,
                "original_language": "en",
            }
        else:
            item = {
                "id": 101,
                "name": "Duplicate Series",
                "original_name": "Duplicate Series",
                "first_air_date": "2024-01-01",
                "poster_path": "/dup.jpg",
                "overview": "",
                "genre_ids": [18],
                "origin_country": [country],
                "vote_average": 8.0,
                "vote_count": 500,
                "popularity": 50,
                "original_language": "en",
            }
        return {"results": [dict(item), dict(item)], "total_pages": 1}


class DuplicateAcrossPagesTmdbClient(FakeTmdbClient):
    def discover(self, endpoint: str, params: dict) -> dict:
        self.calls.append((endpoint, dict(params)))
        page = int(params.get("page") or 1)
        country = params.get("with_origin_country") or "US"
        item = {
            "id": 202,
            "title": "Duplicate Across Pages",
            "original_title": "Duplicate Across Pages",
            "release_date": "2024-01-01",
            "poster_path": "/duplicate-pages.jpg",
            "overview": "",
            "genre_ids": [18],
            "origin_country": [country],
            "vote_average": 7.0,
            "vote_count": 100,
            "popularity": 30,
            "original_language": "en",
        }
        return {"results": [dict(item)] if page <= 2 else [], "total_pages": 2}


class DuplicateTitleDifferentIdsTmdbClient(FakeTmdbClient):
    def discover(self, endpoint: str, params: dict) -> dict:
        self.calls.append((endpoint, dict(params)))
        page = int(params.get("page") or 1)
        country = params.get("with_origin_country") or "US"
        tmdb_id = 300 + page
        return {
            "results": [
                {
                    "id": tmdb_id,
                    "title": "Duplicate-Like Title",
                    "original_title": "Duplicate-Like Title",
                    "release_date": "2024-01-01",
                    "poster_path": f"/duplicate-like-{tmdb_id}.jpg",
                    "overview": "",
                    "genre_ids": [18],
                    "origin_country": [country],
                    "vote_average": 7.0,
                    "vote_count": 100,
                    "popularity": 30,
                    "original_language": "en",
                }
            ]
            if page <= 2
            else [],
            "total_pages": 2,
        }


class SingleWatchedLikeTmdbClient(FakeTmdbClient):
    def discover(self, endpoint: str, params: dict) -> dict:
        self.calls.append((endpoint, dict(params)))
        country = params.get("with_origin_country") or "US"
        return {
            "results": [
                {
                    "id": 404,
                    "title": "Already Watched",
                    "original_title": "Already Watched",
                    "release_date": "2024-01-01",
                    "poster_path": "/already-watched.jpg",
                    "overview": "Overview",
                    "genre_ids": [18],
                    "origin_country": [country],
                    "vote_average": 7.0,
                    "vote_count": 100,
                    "popularity": 30,
                    "original_language": "en",
                }
            ],
            "total_pages": 1,
        }


class MissingOverviewLocalizationTmdbClient(FakeTmdbClient):
    def __init__(
        self,
        *,
        country: str = "JP",
        original_language: str = "ja",
        original_overview: str = "Original language overview",
        en_overview: str = "English overview",
    ) -> None:
        super().__init__()
        self.country = country
        self.original_language = original_language
        self.original_overview = original_overview
        self.en_overview = en_overview

    def discover(self, endpoint: str, params: dict) -> dict:
        self.calls.append((endpoint, dict(params)))
        country = params.get("with_origin_country") or self.country
        return {
            "results": [
                {
                    "id": 808,
                    "title": "Missing Overview Movie",
                    "original_title": "Missing Overview Movie",
                    "release_date": "2024-01-01",
                    "poster_path": "/missing-overview.jpg",
                    "overview": "",
                    "genre_ids": [18],
                    "origin_country": [country],
                    "vote_average": 7.5,
                    "vote_count": 40,
                    "popularity": 12,
                    "original_language": self.original_language,
                }
            ],
            "total_pages": 1,
        }

    def movie_details(self, tmdb_id: int, language: str = "en", *, append_to_response=None) -> dict:
        appends = tuple(append_to_response or ())
        self.details_calls.append((MEDIA_MOVIE, int(tmdb_id), language, appends))
        overview = ""
        if language == autofill._original_language_to_tmdb_locale(self.original_language):
            overview = self.original_overview
        elif language == "en-US":
            overview = self.en_overview
        return {
            "id": int(tmdb_id),
            "title": "Missing Overview Movie",
            "original_title": "Missing Overview Movie",
            "release_date": "2024-01-01",
            "overview": overview,
            "genres": [{"id": 18, "name": "Drama"}],
            "production_countries": [{"iso_3166_1": self.country, "name": self.country}],
            "vote_average": 7.5,
            "vote_count": 40,
            "popularity": 12,
            "poster_path": "/missing-overview-details.jpg",
            "original_language": self.original_language,
            "external_ids": {"imdb_id": f"tt{int(tmdb_id):07d}"},
        }


class LowConfidenceMissingOverviewTmdbClient(FakeTmdbClient):
    def discover(self, endpoint: str, params: dict) -> dict:
        self.calls.append((endpoint, dict(params)))
        country = params.get("with_origin_country") or "US"
        return {
            "results": [
                {
                    "id": 909,
                    "title": "Low Confidence Missing Overview",
                    "original_title": "Low Confidence Missing Overview",
                    "release_date": "2024-01-01",
                    "poster_path": "/low-confidence.jpg",
                    "overview": "",
                    "genre_ids": [18],
                    "origin_country": [country],
                    "vote_average": 5.0,
                    "vote_count": 1,
                    "popularity": 1,
                    "original_language": "en",
                }
            ],
            "total_pages": 1,
        }

    def movie_details(self, tmdb_id: int, language: str = "en", *, append_to_response=None) -> dict:
        appends = tuple(append_to_response or ())
        self.details_calls.append((MEDIA_MOVIE, int(tmdb_id), language, appends))
        return {
            "id": int(tmdb_id),
            "title": "Low Confidence Missing Overview",
            "original_title": "Low Confidence Missing Overview",
            "release_date": "2024-01-01",
            "overview": "",
            "genres": [{"id": 18, "name": "Drama"}],
            "production_countries": [{"iso_3166_1": "US", "name": "United States"}],
            "vote_average": 5.0,
            "vote_count": 1,
            "popularity": 1,
            "poster_path": "/low-confidence-details.jpg",
            "original_language": "en",
        }


class WeakLowVoteTmdbClient(FakeTmdbClient):
    def discover(self, endpoint: str, params: dict) -> dict:
        self.calls.append((endpoint, dict(params)))
        country = params.get("with_origin_country") or "US"
        return {
            "results": [
                {
                    "id": 707,
                    "title": "Weak But Useful",
                    "original_title": "Weak But Useful",
                    "release_date": "2023-01-01",
                    "poster_path": "/weak-but-useful.jpg",
                    "overview": "Useful overview",
                    "genre_ids": [18],
                    "origin_country": [country],
                    "vote_average": 7.0,
                    "vote_count": 10,
                    "popularity": 20,
                    "original_language": "en",
                }
            ],
            "total_pages": 1,
        }


class DetailsPriorityTmdbClient(FakeTmdbClient):
    def discover(self, endpoint: str, params: dict) -> dict:
        self.calls.append((endpoint, dict(params)))
        country = params.get("with_origin_country") or "JP"
        return {
            "results": [
                {
                    "id": 1001,
                    "title": "Complete High Score",
                    "original_title": "Complete High Score",
                    "release_date": "2024-01-01",
                    "poster_path": "/complete.jpg",
                    "overview": "Complete overview",
                    "genre_ids": [18],
                    "origin_country": [country],
                    "vote_average": 8.5,
                    "vote_count": 1000,
                    "popularity": 80,
                    "original_language": "ja",
                },
                {
                    "id": 1002,
                    "title": "Missing Overview Lower Score",
                    "original_title": "Missing Overview Lower Score",
                    "release_date": "2024-01-01",
                    "poster_path": "/missing.jpg",
                    "overview": "",
                    "genre_ids": [18],
                    "origin_country": [country],
                    "vote_average": 6.5,
                    "vote_count": 40,
                    "popularity": 12,
                    "original_language": "ja",
                },
            ],
            "total_pages": 1,
        }

    def movie_details(self, tmdb_id: int, language: str = "en", *, append_to_response=None) -> dict:
        appends = tuple(append_to_response or ())
        self.details_calls.append((MEDIA_MOVIE, int(tmdb_id), language, appends))
        return {
            "id": int(tmdb_id),
            "title": "Missing Overview Lower Score",
            "original_title": "Missing Overview Lower Score",
            "release_date": "2024-01-01",
            "overview": "Japanese overview" if language == "ja-JP" else "",
            "genres": [{"id": 18, "name": "Drama"}],
            "production_countries": [{"iso_3166_1": "JP", "name": "Japan"}],
            "vote_average": 6.5,
            "vote_count": 40,
            "popularity": 12,
            "poster_path": "/missing.jpg",
            "original_language": "ja",
            "external_ids": {"imdb_id": f"tt{int(tmdb_id):07d}"},
        }


class PagedYieldTmdbClient(FakeTmdbClient):
    def __init__(self, *, accepted_per_page: int, total_pages: int = 10, country: str = "US") -> None:
        super().__init__()
        self.accepted_per_page = accepted_per_page
        self.total_pages = total_pages
        self.country = country

    def discover(self, endpoint: str, params: dict) -> dict:
        self.calls.append((endpoint, dict(params)))
        media = MEDIA_MOVIE if endpoint == "/discover/movie" else MEDIA_TV
        page = int(params.get("page") or 1)
        country = params.get("with_origin_country") or self.country
        title_key = "title" if media == MEDIA_MOVIE else "name"
        original_title_key = "original_title" if media == MEDIA_MOVIE else "original_name"
        date_key = "release_date" if media == MEDIA_MOVIE else "first_air_date"
        results = []
        for index in range(self.accepted_per_page):
            tmdb_id = page * 1000 + index
            results.append(
                {
                    "id": tmdb_id,
                    title_key: f"Paged {media} {tmdb_id}",
                    original_title_key: f"Paged {media} {tmdb_id}",
                    date_key: "2024-01-01",
                    "poster_path": f"/paged{tmdb_id}.jpg",
                    "overview": "Useful overview",
                    "genre_ids": [18],
                    "origin_country": [country],
                    "vote_average": 7.0,
                    "vote_count": 100,
                    "popularity": 30,
                    "original_language": "en",
                }
            )
        return {"results": results, "total_pages": self.total_pages}


class LocalizedScenarioTmdbClient(PagedYieldTmdbClient):
    LANGUAGE_BY_COUNTRY = {
        "GB": "en",
        "JP": "ja",
        "KR": "ko",
        "RU": "ru",
        "US": "en",
    }

    def __init__(self, *, accepted_per_page: int = 20, total_pages: int = 10, country: str = "US") -> None:
        super().__init__(accepted_per_page=accepted_per_page, total_pages=total_pages, country=country)
        self.country_by_tmdb_id: dict[int, str] = {}

    def discover(self, endpoint: str, params: dict) -> dict:
        payload = super().discover(endpoint, params)
        country = str(params.get("with_origin_country") or self.country)
        original_language = self.LANGUAGE_BY_COUNTRY.get(country, "en")
        for item in payload.get("results") or []:
            self.country_by_tmdb_id[int(item["id"])] = country
            item["overview"] = ""
            item["original_language"] = original_language
        return payload

    def _details(self, tmdb_id: int, media_type: str, language: str, append_to_response=None) -> dict:
        appends = tuple(append_to_response or ())
        self.details_calls.append((media_type, int(tmdb_id), language, appends))
        country = self.country_by_tmdb_id.get(int(tmdb_id), self.country)
        original_language = self.LANGUAGE_BY_COUNTRY.get(country, "en")
        original_locale = autofill._original_language_to_tmdb_locale(original_language)
        overview = f"{country} localized overview" if language == original_locale else ""
        common = {
            "id": int(tmdb_id),
            "overview": overview,
            "genres": [{"id": 18, "name": "Drama"}],
            "vote_average": 7.4,
            "vote_count": 120,
            "popularity": 40,
            "poster_path": f"/localized-{tmdb_id}.jpg",
            "original_language": original_language,
            "external_ids": {"imdb_id": f"tt{int(tmdb_id):07d}"},
        }
        if media_type == MEDIA_MOVIE:
            common.update({
                "title": f"Localized Movie {tmdb_id}",
                "original_title": f"Localized Movie {tmdb_id}",
                "release_date": "2024-01-01",
                "production_countries": [{"iso_3166_1": country, "name": country}],
            })
        else:
            common.update({
                "name": f"Localized Series {tmdb_id}",
                "original_name": f"Localized Series {tmdb_id}",
                "first_air_date": "2024-01-01",
                "origin_country": [country],
            })
        return common

    def movie_details(self, tmdb_id: int, language: str = "en", *, append_to_response=None) -> dict:
        return self._details(tmdb_id, MEDIA_MOVIE, language, append_to_response)

    def tv_details(self, tmdb_id: int, language: str = "en", *, append_to_response=None) -> dict:
        return self._details(tmdb_id, MEDIA_TV, language, append_to_response)


def _profile(**overrides) -> OnboardingTasteProfile:
    data = {
        "media_preference": "both",
        "release_preference": "mixed",
        "vibe_preference": "mixed",
        "origin_preference": None,
        "ui_language": "en",
    }
    data.update(overrides)
    return OnboardingTasteProfile(**data)


def _quota_by(buckets, field: str) -> Counter:
    result = Counter()
    for bucket in buckets:
        result[getattr(bucket, field)] += bucket.quota
    return result


def _genre_filter_ids(params: dict, key: str) -> set[int]:
    text = str(params.get(key) or "")
    return {int(item) for item in text.replace("|", ",").split(",") if item.isdigit()}


def _scenario_profile(name: str, **overrides) -> OnboardingTasteProfile:
    from scripts.reports.run_onboarding_pool_rebuild import SCENARIOS

    data = dict(SCENARIOS[name])
    data.update(overrides)
    return OnboardingTasteProfile(**data)


def _candidate_country_hit_rate(candidates: list[dict]) -> float:
    if not candidates:
        return 0.0
    hit_count = 0
    for candidate in candidates:
        target = candidate.get("target_country")
        countries = set(candidate.get("country_codes") or candidate.get("countries") or [])
        if target and (not countries or target in countries):
            hit_count += 1
    return round(hit_count / len(candidates), 4)


def _candidate_quality_rate(candidates: list[dict], quality_class: str) -> float:
    if not candidates:
        return 0.0
    count = sum(1 for candidate in candidates if candidate.get("quality_class") == quality_class)
    return round(count / len(candidates), 4)


def _read_jsonl(path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _dark_vibe_hit_rate(candidates: list[dict]) -> float:
    dark_names = {"crime", "mystery", "thriller", "horror", "drama", "war", "war & politics"}
    if not candidates:
        return 0.0
    hits = 0
    for candidate in candidates:
        genres = {str(value or "").strip().casefold() for value in candidate.get("genres") or []}
        if genres & dark_names:
            hits += 1
    return round(hits / len(candidates), 4)


def _country_leakage_count(candidates: list[dict], country: str) -> int:
    return sum(1 for candidate in candidates if country in set(candidate.get("country_codes") or candidate.get("countries") or []))


def _assert_no_initial_discover_vote_filters(profile: OnboardingTasteProfile, *, expected_countries: set[str] | None = None) -> None:
    profile = profile.normalized()
    seen_countries: set[str] = set()
    for bucket in build_fetch_buckets(profile):
        _endpoint, params = build_discover_request(
            bucket,
            profile=profile,
            fallback="base",
            request_index=0,
            current_year=2026,
            current_date=date(2026, 7, 8),
        )
        if bucket.target_country:
            seen_countries.add(bucket.target_country)
            assert params.get("with_origin_country") == bucket.target_country
        assert "vote_count.gte" not in params, (bucket.bucket_id, params)
        assert "vote_average.gte" not in params, (bucket.bucket_id, params)
    if expected_countries is not None:
        assert expected_countries.issubset(seen_countries)


def test_media_preference_quota_weights_are_country_first_and_explicit() -> None:
    assert media_weights("movie") == {MEDIA_MOVIE: 1.0}
    assert media_weights("tv") == {MEDIA_TV: 1.0}
    assert media_weights("both") == {MEDIA_MOVIE: 0.50, MEDIA_TV: 0.50}
    assert _quota_by(build_fetch_buckets(_profile(media_preference="movie")), "media_type") == {MEDIA_MOVIE: 120}
    assert _quota_by(build_fetch_buckets(_profile(media_preference="tv")), "media_type") == {MEDIA_TV: 120}
    assert _quota_by(build_fetch_buckets(_profile(media_preference="both")), "media_type") == {MEDIA_MOVIE: 60, MEDIA_TV: 60}


def test_release_preferences_create_broad_date_ranges_not_exact_year_templates() -> None:
    assert release_weights("classic") == {"classic_sweep": 1.0}
    assert release_weights("new") == {"new_sweep": 1.0}
    classic_buckets = build_fetch_buckets(_profile(release_preference="classic"))
    assert {bucket.era for bucket in classic_buckets} == {"classic_sweep"}
    classic = next(bucket for bucket in classic_buckets if bucket.era == "classic_sweep")
    endpoint, params = build_discover_request(classic, profile=_profile(release_preference="classic"), fallback="base", request_index=0, current_year=2026, current_date=date(2026, 7, 8))
    assert endpoint in {"/discover/movie", "/discover/tv"}
    assert "primary_release_year" not in params
    assert "first_air_date_year" not in params
    assert (params.get("primary_release_date.gte") or params.get("first_air_date.gte")) == "2005-01-01"
    assert (params.get("primary_release_date.lte") or params.get("first_air_date.lte")) == "2021-12-31"
    new = next(bucket for bucket in build_fetch_buckets(_profile(release_preference="new")) if bucket.era == "new_sweep")
    _endpoint, params = build_discover_request(new, profile=_profile(release_preference="new"), fallback="base", request_index=0, current_year=2026, current_date=date(2026, 7, 8))
    assert (params.get("primary_release_date.gte") or params.get("first_air_date.gte")) == "2022-01-01"


def test_vibe_preference_is_scoring_target_not_discover_split() -> None:
    assert vibe_weights("light") == {"light": 1.0}
    assert vibe_weights("dark") == {"dark": 1.0}
    assert vibe_weights("mixed") == {"mixed": 1.0}
    assert _quota_by(build_fetch_buckets(_profile(vibe_preference="light")), "vibe") == {"light": 120}
    assert _quota_by(build_fetch_buckets(_profile(vibe_preference="dark")), "vibe") == {"dark": 120}


def test_country_selection_presets_create_contract_quotas() -> None:
    assert build_country_plan(country_selection_for_foreign_ru(), 120) == {"US": 60, "GB": 60}
    assert build_country_plan(country_selection_for_mixed_ru(), 120) == {"RU": 60, "US": 60}
    assert build_country_plan(country_selection_for_manual("RU", ["US", "KR"]), 120) == {"US": 60, "KR": 60}
    assert build_country_plan(country_selection_for_manual("RU", ["US", "KR"], ratio_preset="90/10"), 120) == {"US": 60, "KR": 60}
    assert build_country_plan(country_selection_for_manual("RU", ["US", "RU", "GB"]), 120) == {"US": 40, "RU": 40, "GB": 40}
    assert build_country_plan(country_selection_for_manual("RU", ["US", "RU", "GB", "KR", "JP"]), 120) == {
        "US": 24,
        "RU": 24,
        "GB": 24,
        "KR": 24,
        "JP": 24,
    }


def test_country_first_profile_replaces_broad_origin_defaults() -> None:
    assert origin_weights("foreign", ui_language="ru") == {"domestic": 0.30, "foreign": 0.70}
    assert origin_weights(None, ui_language="en") == {"any": 1.0}
    foreign_countries = _quota_by(build_fetch_buckets(_profile(ui_language="ru", origin_preference="foreign")), "target_country")
    mixed_countries = _quota_by(build_fetch_buckets(_profile(ui_language="ru", origin_preference="mixed")), "target_country")
    en_countries = _quota_by(build_fetch_buckets(_profile(ui_language="en")), "target_country")
    assert foreign_countries == {"US": 60, "GB": 60}
    assert mixed_countries == {"RU": 60, "US": 60}
    assert en_countries == {"US": 60, "GB": 60}


def test_country_first_selected_countries_all_use_origin_filter_and_plan_totals_to_target() -> None:
    for count in range(1, 6):
        countries = ["US", "RU", "GB", "KR", "JP"][:count]
        profile = _profile(country_selection={"selected_countries": countries, "home_country": "RU"}).normalized()
        country_plan = build_country_plan(profile.country_selection, autofill.STARTER_POOL_TARGET)
        assert sum(country_plan.values()) == autofill.STARTER_POOL_TARGET
        assert set(country_plan) == set(countries)
        for bucket in build_fetch_buckets(profile):
            _endpoint, params = build_discover_request(
                bucket,
                profile=profile,
                fallback="base",
                request_index=0,
                current_year=2026,
                current_date=date(2026, 7, 8),
            )
            assert bucket.target_country in countries
            assert params.get("with_origin_country") == bucket.target_country


def test_initial_onboarding_discover_never_uses_vote_or_rating_filters_across_variants() -> None:
    selected_countries = {"US", "KR", "JP"}
    for media_preference in ("movie", "tv", "both"):
        for release_preference in ("new", "mixed", "classic"):
            for vibe_preference in ("light", "dark", "mixed"):
                for animation_mode in (
                    ANIMATION_MODE_ANY,
                    ANIMATION_MODE_ANIMATION_ONLY,
                    ANIMATION_MODE_LIVE_ACTION_ONLY,
                ):
                    _assert_no_initial_discover_vote_filters(
                        _profile(
                            media_preference=media_preference,
                            release_preference=release_preference,
                            vibe_preference=vibe_preference,
                            animation_mode=animation_mode,
                            country_selection={"selected_countries": sorted(selected_countries), "home_country": "RU"},
                        ),
                        expected_countries=selected_countries,
                    )

    for preset_key in (
        PRESET_ANIME,
        PRESET_FAMILY_ANIMATION,
        PRESET_K_DRAMA,
        PRESET_TURKISH_DRAMAS,
        PRESET_MANUAL,
    ):
        overrides = (
            {
                "selected_countries": sorted(selected_countries),
                "home_country": "RU",
            }
            if preset_key == PRESET_MANUAL
            else {}
        )
        payload = taste_preset_to_profile_payload(
            preset_key,
            overrides,
            ui_language="ru",
        )
        _assert_no_initial_discover_vote_filters(
            OnboardingTasteProfile(**payload),
            expected_countries=selected_countries if preset_key == PRESET_MANUAL else None,
        )


def test_bucket_quotas_sum_exactly_to_target() -> None:
    profile = _profile(media_preference="movie", release_preference="new", vibe_preference="dark", ui_language="ru", origin_preference="foreign")
    buckets = build_fetch_buckets(profile)
    assert sum(bucket.quota for bucket in buckets) == autofill.STARTER_POOL_TARGET


def test_multiple_include_genres_are_or_by_default_and_strict_when_explicit() -> None:
    client = FakeTmdbClient()
    genre_ids = resolve_tmdb_genre_ids(client)
    assert genre_ids[MEDIA_MOVIE]["light"] == (35, 10749, 14, 10751, 12)
    assert genre_ids[MEDIA_TV]["dark"] == (18, 80, 9648, 10759, 10768)
    profile = _profile(include_genres=[18, 9648, 80])
    bucket = build_fetch_buckets(profile)[0]
    _endpoint, params = build_discover_request(bucket, profile=profile, fallback="base", request_index=0, current_year=2026, current_date=date(2026, 7, 8))
    assert params["with_genres"] == "18|9648|80"

    strict = _profile(include_genres=[18, 9648, 80], include_genre_mode="and")
    bucket = build_fetch_buckets(strict)[0]
    _endpoint, params = build_discover_request(bucket, profile=strict, fallback="base", request_index=0, current_year=2026, current_date=date(2026, 7, 8))
    assert params["with_genres"] == "18,9648,80"


def test_animation_only_forces_animation_genre_without_or_leakage() -> None:
    profile = _profile(animation_mode=ANIMATION_MODE_ANIMATION_ONLY, include_genres=[18, 80])
    bucket = build_fetch_buckets(profile)[0]

    _endpoint, params = build_discover_request(
        bucket,
        profile=profile,
        fallback="base",
        request_index=0,
        current_year=2026,
        current_date=date(2026, 7, 8),
    )

    assert params["with_genres"] == str(TMDB_ANIMATION_GENRE_ID)
    assert "|" not in params["with_genres"]
    assert "vote_count.gte" not in params
    assert "vote_average.gte" not in params


def test_live_action_only_excludes_animation_and_keeps_tv_junk_excludes() -> None:
    profile = _profile(media_preference="tv", animation_mode=ANIMATION_MODE_LIVE_ACTION_ONLY)
    bucket = build_fetch_buckets(profile)[0]

    endpoint, params = build_discover_request(
        bucket,
        profile=profile,
        fallback="base",
        request_index=0,
        current_year=2026,
        current_date=date(2026, 7, 8),
    )

    assert endpoint == "/discover/tv"
    excluded = _genre_filter_ids(params, "without_genres")
    assert TMDB_ANIMATION_GENRE_ID in excluded
    assert set(autofill.TV_JUNK_GENRE_IDS).issubset(excluded)
    assert "vote_count.gte" not in params
    assert "vote_average.gte" not in params


def test_animation_any_does_not_force_or_exclude_animation() -> None:
    profile = _profile(media_preference="movie", animation_mode=ANIMATION_MODE_ANY)
    bucket = build_fetch_buckets(profile)[0]

    _endpoint, params = build_discover_request(
        bucket,
        profile=profile,
        fallback="base",
        request_index=0,
        current_year=2026,
        current_date=date(2026, 7, 8),
    )

    assert "with_genres" not in params
    assert TMDB_ANIMATION_GENRE_ID not in _genre_filter_ids(params, "without_genres")


def test_starter_presets_feed_animation_mode_into_discover_contract() -> None:
    expected = {
        PRESET_ANIME: ("JP", ANIMATION_MODE_ANIMATION_ONLY, "both"),
        PRESET_K_DRAMA: ("KR", ANIMATION_MODE_LIVE_ACTION_ONLY, "tv"),
        PRESET_TURKISH_DRAMAS: ("TR", ANIMATION_MODE_LIVE_ACTION_ONLY, "tv"),
        PRESET_FAMILY_ANIMATION: ("US", ANIMATION_MODE_ANIMATION_ONLY, "both"),
    }

    for preset_key, (country, animation_mode, media_preference) in expected.items():
        profile = OnboardingTasteProfile(**taste_preset_to_profile_payload(preset_key)).normalized()
        bucket = next(bucket for bucket in build_fetch_buckets(profile) if bucket.target_country == country)
        _endpoint, params = build_discover_request(
            bucket,
            profile=profile,
            fallback="base",
            request_index=0,
            current_year=2026,
            current_date=date(2026, 7, 8),
        )

        assert profile.country_selection.selected_countries[0] == country
        assert profile.animation_mode == animation_mode
        assert profile.media_preference == media_preference
        if animation_mode == ANIMATION_MODE_ANIMATION_ONLY:
            assert params["with_genres"] == str(TMDB_ANIMATION_GENRE_ID)
        else:
            assert TMDB_ANIMATION_GENRE_ID in _genre_filter_ids(params, "without_genres")


def test_discover_params_use_media_specific_contract() -> None:
    movie = next(bucket for bucket in build_fetch_buckets(_profile(media_preference="movie", release_preference="new")) if bucket.media_type == MEDIA_MOVIE and bucket.era == "new_sweep")
    endpoint, params = build_discover_request(movie, profile=_profile(media_preference="movie", release_preference="new"), fallback="base", request_index=0, current_year=2026, current_date=date(2026, 7, 8))
    assert endpoint == "/discover/movie"
    assert params["with_origin_country"] == movie.target_country
    assert params["primary_release_date.gte"] == "2022-01-01"
    assert params["primary_release_date.lte"] == "2026-07-08"
    assert params["include_adult"] is False
    assert params["sort_by"] == "popularity.desc"
    assert "vote_count.gte" not in params
    assert "vote_average.gte" not in params
    tv = next(bucket for bucket in build_fetch_buckets(_profile(media_preference="tv", release_preference="new")) if bucket.media_type == MEDIA_TV and bucket.era == "new_sweep")
    endpoint, params = build_discover_request(tv, profile=_profile(media_preference="tv", release_preference="new"), fallback="base", request_index=0, current_year=2026, current_date=date(2026, 7, 8))
    assert endpoint == "/discover/tv"
    assert params["with_origin_country"] == tv.target_country
    assert params["first_air_date.gte"] == "2022-01-01"
    assert params["first_air_date.lte"] == "2026-07-08"
    assert params["without_genres"] == "10766,10764,10767,10763,10762,99"


def test_country_first_sweep_blocks_broad_origin_and_vote_filters() -> None:
    assert autofill.FALLBACK_ORDER == ("base",)
    profile = _profile(ui_language="ru", origin_preference="domestic", include_genres=[18, 9648, 80])
    bucket = next(bucket for bucket in build_fetch_buckets(profile) if bucket.target_country == "RU" and bucket.genre_ids)
    _endpoint, base = build_discover_request(bucket, profile=profile, fallback="base", request_index=0, current_year=2026, current_date=date(2026, 7, 8))
    _endpoint, relaxed_origin = build_discover_request(bucket, profile=profile, fallback="relax_origin", request_index=0, current_year=2026, current_date=date(2026, 7, 8))
    assert base["with_origin_country"] == "RU"
    assert relaxed_origin["with_origin_country"] == "RU"
    assert "with_original_language" not in relaxed_origin
    assert "vote_count.gte" not in base
    assert "vote_average.gte" not in base


def test_onboarding_wizard_starts_with_setup_preset_then_editable_questions(qapp) -> None:
    from desktop.onboarding import OnboardingAutofillDialog

    ru_dialog = OnboardingAutofillDialog(ui_language="ru")
    en_dialog = OnboardingAutofillDialog(ui_language="en")
    try:
        assert len(ru_dialog._active_questions()) == 5
        assert len(en_dialog._active_questions()) == 5
        assert ru_dialog._stack.currentIndex() == 0
        ru_dialog._go_next()
        assert ru_dialog._stack.currentIndex() == 1
        ru_dialog._go_next()
        assert ru_dialog._stack.currentIndex() == ru_dialog._question_start_index()
        assert ru_dialog._active_questions()[0].key == "country_selection"
        assert ru_dialog._active_questions()[2].key == "animation_mode"
        assert en_dialog._active_questions()[0].key == "country_selection"
    finally:
        ru_dialog.close()
        en_dialog.close()


def test_onboarding_wizard_preset_card_labels_are_localized(qapp) -> None:
    from desktop.onboarding import OnboardingAutofillDialog

    en_dialog = OnboardingAutofillDialog(ui_language="en")
    ru_dialog = OnboardingAutofillDialog(ui_language="ru")
    try:
        en_labels = [button.text() for button in en_dialog._preset_group.buttons()]
        ru_labels = [button.text() for button in ru_dialog._preset_group.buttons()]

        assert any("Anime" in label and "Japan" in label for label in en_labels)
        assert any("Manual" in label and "Choose countries" in label for label in en_labels)
        assert not any("Anime" in label for label in ru_labels)
    finally:
        en_dialog.close()
        ru_dialog.close()


def test_onboarding_wizard_russian_animation_question_is_not_mojibake(qapp) -> None:
    from desktop.onboarding import OnboardingAutofillDialog
    from desktop.onboarding import wizard as wizard_module

    dialog = OnboardingAutofillDialog(ui_language="ru")
    try:
        question = next(item for item in dialog._active_questions() if item.key == "animation_mode")
        texts = [
            dialog._text(question.title_ru, question.title_en),
            *[dialog._text(option_ru, option_en) for _answer, option_ru, option_en in question.options],
        ]

        assert texts == [
            "Как относимся к анимации?",
            "Не важно",
            "Только анимация",
            "Без анимации",
        ]
        assert not any(
            marker in text
            for text in texts
            for marker in wizard_module._MOJIBAKE_MARKERS
        )
    finally:
        dialog.close()


def test_onboarding_wizard_anime_preset_sets_profile_defaults(qapp) -> None:
    from desktop.onboarding import OnboardingAutofillDialog

    dialog = OnboardingAutofillDialog(ui_language="en")
    try:
        buttons = {button.property("answer"): button for button in dialog._preset_group.buttons()}
        buttons[PRESET_ANIME].click()
        profile = dialog._profile()

        assert profile["taste_preset"] == PRESET_ANIME
        assert profile["country_selection"]["selected_countries"] == ["JP"]
        assert profile["animation_mode"] == ANIMATION_MODE_ANIMATION_ONLY
        assert profile["media_preference"] == "both"
    finally:
        dialog.close()


def test_onboarding_wizard_presets_hide_locked_country_and_animation_questions(qapp) -> None:
    from desktop.onboarding import OnboardingAutofillDialog

    dialog = OnboardingAutofillDialog(ui_language="ru")
    try:
        buttons = {button.property("answer"): button for button in dialog._preset_group.buttons()}

        assert [question.key for question in dialog._active_questions()] == [
            "country_selection",
            "media_preference",
            "animation_mode",
            "release_preference",
            "vibe_preference",
        ]

        for preset_key in (PRESET_ANIME, PRESET_FAMILY_ANIMATION, PRESET_K_DRAMA, PRESET_TURKISH_DRAMAS):
            buttons[preset_key].click()
            active_keys = [question.key for question in dialog._active_questions()]

            assert "country_selection" not in active_keys
            assert "animation_mode" not in active_keys
            assert active_keys == ["media_preference", "release_preference", "vibe_preference"]

        buttons[PRESET_MANUAL].click()
        assert "country_selection" in [question.key for question in dialog._active_questions()]
        assert "animation_mode" in [question.key for question in dialog._active_questions()]
    finally:
        dialog.close()


def test_onboarding_wizard_k_drama_preset_sets_profile_defaults(qapp) -> None:
    from desktop.onboarding import OnboardingAutofillDialog

    dialog = OnboardingAutofillDialog(ui_language="en")
    try:
        buttons = {button.property("answer"): button for button in dialog._preset_group.buttons()}
        buttons[PRESET_K_DRAMA].click()
        profile = dialog._profile()

        assert profile["taste_preset"] == PRESET_K_DRAMA
        assert profile["country_selection"]["selected_countries"] == ["KR"]
        assert profile["animation_mode"] == ANIMATION_MODE_LIVE_ACTION_ONLY
        assert profile["media_preference"] == "tv"
    finally:
        dialog.close()


def test_onboarding_wizard_profile_contains_explicit_country_selection(qapp) -> None:
    from desktop.onboarding import OnboardingAutofillDialog

    dialog = OnboardingAutofillDialog(ui_language="ru")
    try:
        dialog._answers["country_selection"] = ["US", "GB"]
        profile = dialog._profile()
        assert profile["origin_preference"] == "foreign"
        assert profile["country_selection"]["selected_countries"] == ["US", "GB"]
        assert profile["country_selection"]["country_weights"] == {"US": 0.50, "GB": 0.50}
        assert profile["country_selection"]["exclude_home_country"] is False
        assert profile["country_selection"]["max_countries"] == 5
    finally:
        dialog.close()


def test_onboarding_wizard_country_buttons_use_localized_names(qapp) -> None:
    from desktop.onboarding import OnboardingAutofillDialog

    ru_dialog = OnboardingAutofillDialog(ui_language="ru")
    en_dialog = OnboardingAutofillDialog(ui_language="en")
    try:
        ru_labels = [button.text() for button in ru_dialog._question_pages[0][2].buttons()]
        en_labels = [button.text() for button in en_dialog._question_pages[0][2].buttons()]

        assert ru_labels == ["США", "Россия", "Великобритания", "Южная Корея", "Япония"]
        assert all(code not in " ".join(ru_labels) for code in ("RU", "US", "GB", "KR", "JP"))
        assert en_labels == [
            "United States",
            "Russia",
            "United Kingdom",
            "South Korea",
            "Japan",
        ]
        assert "US + GB" not in " ".join(en_labels)
        assert "RU" not in " ".join(en_labels)
    finally:
        ru_dialog.close()
        en_dialog.close()


def test_onboarding_wizard_country_buttons_are_multi_select(qapp) -> None:
    from desktop.onboarding import OnboardingAutofillDialog

    dialog = OnboardingAutofillDialog(ui_language="ru")
    try:
        dialog._set_page(dialog._question_start_index())
        group = dialog._question_pages[0][2]
        buttons = {button.property("answer"): button for button in group.buttons()}

        assert group.exclusive() is False
        assert buttons["US"].isChecked() is True
        buttons["RU"].click()
        buttons["GB"].click()

        assert dialog._answers["country_selection"] == ["US", "RU", "GB"]
        assert dialog._selected_answer(dialog._question_pages[0][0], group) == ["US", "RU", "GB"]
    finally:
        dialog.close()


def test_onboarding_wizard_manual_preset_keeps_five_country_picker_limit(qapp) -> None:
    from desktop.onboarding import OnboardingAutofillDialog

    dialog = OnboardingAutofillDialog(ui_language="en")
    try:
        buttons = {button.property("answer"): button for button in dialog._preset_group.buttons()}
        buttons[PRESET_MANUAL].click()
        group = dialog._question_pages[0][2]

        assert len(group.buttons()) == 5
        assert dialog._country_selection_payload()["max_countries"] == 5
    finally:
        dialog.close()


def test_onboarding_wizard_defaults_to_us_only_without_ru(qapp) -> None:
    from desktop.onboarding import OnboardingAutofillDialog

    dialog = OnboardingAutofillDialog(ui_language="ru")
    try:
        profile = dialog._profile()

        assert profile["origin_preference"] == "foreign"
        assert profile["country_selection"]["selected_countries"] == ["US"]
        assert profile["country_selection"]["country_weights"] == {"US": 1.0}
        assert profile["country_selection"]["exclude_home_country"] is False
        assert profile["country_selection"]["primary_country"] == "US"
    finally:
        dialog.close()


def test_onboarding_wizard_supports_all_country_chip_combinations(qapp) -> None:
    from desktop.onboarding import OnboardingAutofillDialog

    codes = ("US", "RU", "GB", "KR", "JP")
    dialog = OnboardingAutofillDialog(ui_language="ru")
    try:
        for size in range(1, len(codes) + 1):
            for combo in combinations(codes, size):
                dialog._answers["country_selection"] = list(combo)
                selection = dialog._country_selection_payload()
                plan = build_country_plan(autofill._coerce_country_selection(
                    selection,
                    ui_language="ru",
                    origin_preference=dialog._profile()["origin_preference"],
                ), 120)

                assert selection["selected_countries"] == list(combo)
                assert set(selection["country_weights"]) == set(combo)
                assert sum(plan.values()) == 120
                assert set(plan) == set(combo)
    finally:
        dialog.close()


def test_onboarding_wizard_scale_preview_has_sample_widgets(qapp) -> None:
    from PyQt6.QtWidgets import QFrame, QLabel, QPushButton

    from desktop.onboarding import OnboardingAutofillDialog

    dialog = OnboardingAutofillDialog(ui_language="ru")
    try:
        preview = dialog.findChild(QFrame, "onboardingScalePreview")
        action = dialog.findChild(QPushButton, "onboardingScalePreviewAction")
        chips = dialog.findChildren(QLabel, "onboardingScalePreviewChip")

        assert preview is not None
        assert action is not None
        assert action.text() == "Кнопка"
        assert [chip.text() for chip in chips] == ["Страна", "Жанр", "Оценка"]
    finally:
        dialog.close()


def test_onboarding_wizard_plan_summary_localizes_country_counts(qapp) -> None:
    from desktop.onboarding import OnboardingAutofillDialog

    dialog = OnboardingAutofillDialog(ui_language="ru")
    try:
        dialog._answers["country_selection"] = ["US", "GB"]
        summary = dialog._format_plan_summary()

        assert "Страны: США: 60, Великобритания: 60" in summary
        assert "US:" not in summary
        assert "GB:" not in summary
    finally:
        dialog.close()


def test_onboarding_wizard_plan_summary_shows_preset_axes(qapp) -> None:
    from desktop.onboarding import OnboardingAutofillDialog

    dialog = OnboardingAutofillDialog(ui_language="en")
    try:
        buttons = {button.property("answer"): button for button in dialog._preset_group.buttons()}
        buttons[PRESET_ANIME].click()
        summary = dialog._format_plan_summary()

        assert "Preset: Anime (anime)" in summary
        assert "Countries: Japan: 120" in summary
        assert "Media: No preference" in summary
        assert "Animation: Animation only" in summary
        assert "Movies: 60, series: 60" in summary
    finally:
        dialog.close()


def test_onboarding_preset_ui_smoke_object_names_and_screenshot_path(qapp) -> None:
    from pathlib import Path

    from PyQt6.QtWidgets import QPushButton, QScrollArea, QWidget

    from desktop.onboarding import OnboardingAutofillDialog

    dialog = OnboardingAutofillDialog(ui_language="en")
    try:
        assert dialog.objectName() == "onboardingAutofillDialog"
        dialog._set_page(1)
        assert dialog._stack.currentWidget() is dialog._preset_page
        assert dialog._preset_page.objectName() == "onboardingPage"
        assert dialog._preset_page.findChild(QScrollArea, "onboardingPresetScroll") is not None
        assert dialog._preset_page.findChild(QWidget, "onboardingPresetViewport") is not None
        cards = dialog._preset_page.findChildren(QPushButton, "onboardingPresetCard")
        assert cards
        preset_keys = {str(card.property("preset_key") or "") for card in cards}
        assert {PRESET_ANIME, PRESET_K_DRAMA, PRESET_MANUAL}.issubset(preset_keys)
        assert all(str(card.property("answer") or "") == str(card.property("preset_key") or "") for card in cards)

        buttons = {str(button.property("answer") or ""): button for button in cards}
        buttons[PRESET_ANIME].click()
        dialog._set_page(dialog._plan_index())
        assert dialog._plan_summary_label.objectName() == "onboardingPlanSummary"
        assert "Preset: Anime (anime)" in dialog._plan_summary_label.text()

        allowed_output = Path("screens/tmp_ui/onboarding") / "taste_scale100.png"
        assert allowed_output.as_posix().startswith("screens/tmp_ui/onboarding/")
    finally:
        dialog.close()


def test_run_autofill_uses_mocked_tmdb_and_persists_profile_audit_and_candidates(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("config.constant.APP_DATA_DIR", str(tmp_path / "data"))
    db_path = tmp_path / "watchbane.sqlite3"
    client = FakeTmdbClient()

    result = run_onboarding_autofill(_profile(media_preference="both"), client=client, path=db_path, current_year=2026)

    assert result.created_count == autofill.STARTER_POOL_TARGET
    assert result.api_requests <= autofill.MAX_TMDB_REQUESTS
    assert client.calls
    conn = connect(db_path)
    try:
        profile_count = conn.execute("SELECT COUNT(*) AS count FROM onboarding_profiles").fetchone()["count"]
        request_count = conn.execute("SELECT COUNT(*) AS count FROM candidate_autofill_requests").fetchone()["count"]
        candidate_count = conn.execute("SELECT COUNT(*) AS count FROM candidate_records").fetchone()["count"]
        media_counts = {
            row["media_type"]: row["count"]
            for row in conn.execute("SELECT media_type, COUNT(*) AS count FROM candidate_records GROUP BY media_type")
        }
        assert profile_count == 1
        assert request_count == result.api_requests + result.duplicate_requests_skipped
        assert candidate_count == autofill.STARTER_POOL_TARGET
        assert media_counts[MEDIA_MOVIE] == 60
        assert media_counts[MEDIA_TV] == 60
        row = conn.execute("SELECT source, source_bucket_id, onboarding_profile_id, candidate_score, fetch_rank FROM candidate_records LIMIT 1").fetchone()
        assert row["source"] == "onboarding_autofill"
        assert row["source_bucket_id"]
        assert row["onboarding_profile_id"] == result.profile_id
        assert row["candidate_score"] > 0
        assert row["fetch_rank"] > 0
        assert len(client.calls) == result.api_requests
        assert len({autofill.canonical_discover_request_key(endpoint, params) for endpoint, params in client.calls}) == result.api_requests
        assert result.api_requests <= 20
    finally:
        conn.close()


def test_onboarding_request_log_disabled_by_default(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("config.constant.APP_DATA_DIR", str(tmp_path / "data"))
    log_path = tmp_path / "reports" / "onboarding_request_log.jsonl"
    monkeypatch.setattr(request_log, "DEFAULT_LOG_PATH", log_path)
    monkeypatch.delenv(request_log.ENV_FLAG, raising=False)

    result = run_onboarding_autofill(
        _profile(media_preference="movie"),
        client=FakeTmdbClient(),
        path=tmp_path / "watchbane.sqlite3",
        current_year=2026,
    )

    assert result.created_count == autofill.STARTER_POOL_TARGET
    assert log_path.exists() is False


def test_onboarding_request_log_enabled_writes_one_sanitized_jsonl_entry(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("config.constant.APP_DATA_DIR", str(tmp_path / "data"))
    log_path = tmp_path / "reports" / "onboarding_request_log.jsonl"
    db_path = tmp_path / "runtime" / "watchbane.sqlite3"
    monkeypatch.setattr(request_log, "DEFAULT_LOG_PATH", log_path)
    monkeypatch.setenv(request_log.ENV_FLAG, "1")
    client = FakeTmdbClient()
    client.api_key = "secret-token"

    result = run_onboarding_autofill(
        _profile(
            taste_preset=PRESET_MANUAL,
            media_preference="movie",
            animation_mode=ANIMATION_MODE_LIVE_ACTION_ONLY,
            country_selection=country_selection_for_manual("US", ["US"]).as_repository_dict(),
            include_genres=(18,),
            exclude_genres=(35,),
            min_year=2010,
            max_year=2024,
        ),
        client=client,
        path=db_path,
        current_year=2026,
    )

    lines = _read_jsonl(log_path)
    raw = log_path.read_text(encoding="utf-8")
    assert len(lines) == 1
    entry = lines[0]
    assert entry["status"] == "success"
    assert entry["selected_countries"] == ["US"]
    assert entry["selected_preset"] == PRESET_MANUAL
    assert entry["media_type"] == "movie"
    assert entry["animation_mode"] == ANIMATION_MODE_LIVE_ACTION_ONLY
    assert entry["target_pool_size"] == autofill.STARTER_POOL_TARGET
    assert entry["generated_candidates_count"] == result.created_count
    assert entry["country_hit_rate"] == 1.0
    assert entry["country_plan"] == {"US": 120}
    assert entry["country_actual"] == {"US": result.created_count}
    assert entry["media_actual"] == {"movie": result.created_count}
    assert entry["discover_http_requests"] > 0
    assert entry["details_requests"] == result.details_requests
    assert "secret-token" not in raw
    assert "api_key" not in raw
    assert str(db_path) not in raw
    assert str(tmp_path) not in raw


def test_onboarding_request_log_sanitizer_removes_tokens_paths_and_control_chars() -> None:
    sanitized = request_log.sanitize_log_entry({
        "api_key": "secret-token",
        "tmdb_token": "secret-token",
        "error_message": "bad\x00 token=secret-token path D:\\runtime\\watchbane.sqlite3",
        "nested": {"authorization": "Bearer secret-token", "safe": "ok"},
    })

    dumped = json.dumps(sanitized, ensure_ascii=False)
    assert "api_key" not in dumped
    assert "tmdb_token" not in dumped
    assert "authorization" not in dumped
    assert "secret-token" not in dumped
    assert "D:\\runtime" not in dumped
    assert "\x00" not in dumped
    assert sanitized["nested"]["safe"] == "ok"


def test_onboarding_request_log_write_warning_does_not_break_generation(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("config.constant.APP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv(request_log.ENV_FLAG, "1")
    monkeypatch.setattr(autofill.request_log, "append_onboarding_request_log", lambda _entry: "request log failed")

    result = run_onboarding_autofill(
        _profile(media_preference="movie"),
        client=FakeTmdbClient(),
        path=tmp_path / "watchbane.sqlite3",
        current_year=2026,
    )

    assert result.ok is True
    assert result.created_count == autofill.STARTER_POOL_TARGET
    assert "request log failed" in result.warnings
    assert result.warning and "request log failed" in result.warning


def test_onboarding_request_log_failure_case_writes_failure_status(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("config.constant.APP_DATA_DIR", str(tmp_path / "data"))
    log_path = tmp_path / "reports" / "onboarding_request_log.jsonl"
    db_path = tmp_path / "runtime" / "watchbane.sqlite3"
    monkeypatch.setattr(request_log, "DEFAULT_LOG_PATH", log_path)
    monkeypatch.setenv(request_log.ENV_FLAG, "1")

    with pytest.raises(RuntimeError):
        run_onboarding_autofill(
            _profile(media_preference="movie"),
            client=FailingGenreTmdbClient(),
            path=db_path,
            current_year=2026,
        )

    lines = _read_jsonl(log_path)
    raw = log_path.read_text(encoding="utf-8")
    assert len(lines) == 1
    entry = lines[0]
    assert entry["status"] == "failure"
    assert entry["error_class"] == "RuntimeError"
    assert entry["generated_candidates_count"] == 0
    assert entry["target_pool_size"] == autofill.STARTER_POOL_TARGET
    assert "secret-token" not in raw
    assert str(db_path) not in raw
    assert str(tmp_path) not in raw
    assert "<redacted_path>" in entry["error_message"]


def test_run_autofill_keeps_tv_quota_when_tv_is_preferred(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("config.constant.APP_DATA_DIR", str(tmp_path / "data"))
    db_path = tmp_path / "watchbane.sqlite3"
    result = run_onboarding_autofill(
        _profile(media_preference="tv"),
        client=FakeTmdbClient(),
        path=db_path,
        current_year=2026,
    )

    assert result.created_count == autofill.STARTER_POOL_TARGET
    assert result.planned_counts["media_type"] == {MEDIA_TV: 120}
    assert result.actual_counts["media_type"] == {MEDIA_TV: 120}
    assert result.warning is None


def test_adaptive_pagination_continues_when_yield_is_high_and_quota_underfilled(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("config.constant.APP_DATA_DIR", str(tmp_path / "data"))
    client = PagedYieldTmdbClient(accepted_per_page=20, total_pages=10, country="US")

    result = run_onboarding_autofill(
        _profile(
            media_preference="movie",
            country_selection={"selected_countries": ["US"], "home_country": "US"},
            details_enrichment={"enabled": False},
        ),
        client=client,
        path=tmp_path / "watchbane.sqlite3",
        current_year=2026,
    )

    pages = [params["page"] for _endpoint, params in client.calls]
    assert result.created_count == autofill.STARTER_POOL_TARGET
    assert max(pages) == 6
    assert result.adaptive_pages_used == 1


def test_adaptive_pagination_stops_when_yield_is_low(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("config.constant.APP_DATA_DIR", str(tmp_path / "data"))
    client = PagedYieldTmdbClient(accepted_per_page=2, total_pages=10, country="US")

    result = run_onboarding_autofill(
        _profile(
            media_preference="movie",
            country_selection={"selected_countries": ["US"], "home_country": "US"},
            details_enrichment={"enabled": False},
        ),
        client=client,
        path=tmp_path / "watchbane.sqlite3",
        current_year=2026,
    )

    pages = [params["page"] for _endpoint, params in client.calls]
    assert pages == [1, 2, 3]
    assert result.created_count == 6
    assert result.pagination_stop_reasons["low_yield"] == 1
    assert result.adaptive_pages_used == 0


def test_selected_country_underfill_keeps_country_first_while_yield_is_high(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("config.constant.APP_DATA_DIR", str(tmp_path / "data"))
    client = PagedYieldTmdbClient(accepted_per_page=20, total_pages=10, country="KR")

    result = run_onboarding_autofill(
        _profile(
            media_preference="movie",
            ui_language="ru",
            country_selection={"selected_countries": ["KR"], "home_country": "RU"},
            details_enrichment={"enabled": False},
        ),
        client=client,
        path=tmp_path / "watchbane.sqlite3",
        current_year=2026,
    )

    assert result.created_count == autofill.STARTER_POOL_TARGET
    assert result.adaptive_pages_used == 1
    assert all(params.get("with_origin_country") == "KR" for _endpoint, params in client.calls)
    assert all("vote_count.gte" not in params and "vote_average.gte" not in params for _endpoint, params in client.calls)
    assert {candidate["source_query"]["fallback"] for candidate in result.candidates} == {"base"}


def test_run_autofill_underfills_scarce_tv_without_movie_overfill(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("config.constant.APP_DATA_DIR", str(tmp_path / "data"))
    db_path = tmp_path / "watchbane.sqlite3"
    result = run_onboarding_autofill(
        _profile(media_preference="tv"),
        client=ScarceTvTmdbClient(),
        path=db_path,
        current_year=2026,
    )

    assert result.planned_counts["media_type"] == {MEDIA_TV: 120}
    assert result.actual_counts.get("media_type", {}).get(MEDIA_MOVIE, 0) == 0
    assert result.actual_counts["media_type"].get(MEDIA_TV, 0) == 0
    assert result.created_count == 0
    assert result.adaptive_pages_used == 0
    assert result.pagination_stop_reasons["empty_page"] >= 1
    assert "Media quota underfilled: tv planned 120, actual 0." in result.warnings


def test_country_first_mocked_normal_scenario_has_no_broad_origin_or_fallback(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("config.constant.APP_DATA_DIR", str(tmp_path / "data"))
    client = PagedYieldTmdbClient(accepted_per_page=20, total_pages=10, country="US")

    result = run_onboarding_autofill(
        _profile(
            media_preference="movie",
            country_selection={"selected_countries": ["US"], "home_country": "US"},
            details_enrichment={"enabled": False},
        ),
        client=client,
        path=tmp_path / "watchbane.sqlite3",
        current_year=2026,
    )

    assert result.created_count == autofill.STARTER_POOL_TARGET
    assert _candidate_country_hit_rate(result.candidates) == 1.0
    assert all("with_origin_country" in params for _endpoint, params in client.calls)
    assert {candidate["source_query"]["fallback"] for candidate in result.candidates} == {"base"}


def test_country_leakage_metric_counts_off_country_candidate() -> None:
    from scripts.reports.run_onboarding_pool_rebuild import _country_metrics

    metrics = _country_metrics(
        [
            {
                "target_country": "US",
                "country_codes": ["RU"],
            }
        ],
        {
            "country_selection": {
                "selected_countries": ["US"],
                "home_country": "RU",
                "exclude_home_country": True,
            }
        },
    )

    assert metrics["country_hit_rate"] == 0.0
    assert metrics["country_leakage_count"] == 1
    assert metrics["wrong_country_count"] == 1


def test_acceptance_scenario_ru_tv_manual_serious_2010_adapts_without_vote_filters_or_foreign_fallback(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("config.constant.APP_DATA_DIR", str(tmp_path / "data"))
    client = PagedYieldTmdbClient(accepted_per_page=20, total_pages=10, country="RU")

    result = run_onboarding_autofill(
        _scenario_profile("ru-tv-manual-serious-2010"),
        client=client,
        path=tmp_path / "watchbane.sqlite3",
        current_year=2026,
    )

    assert result.created_count > 82
    assert result.created_count == autofill.STARTER_POOL_TARGET
    assert result.adaptive_pages_used >= 1
    assert _candidate_country_hit_rate(result.candidates) == 1.0
    assert _candidate_quality_rate(result.candidates, "garbage") == 0.0
    assert all(params.get("with_origin_country") == "RU" for _endpoint, params in client.calls)
    assert all("vote_count.gte" not in params and "vote_average.gte" not in params for _endpoint, params in client.calls)


def test_acceptance_scenario_ru_manual_jp_kr_uses_localization_fallback_and_keeps_country_hit(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("config.constant.APP_DATA_DIR", str(tmp_path / "data"))
    client = LocalizedScenarioTmdbClient()

    result = run_onboarding_autofill(
        _scenario_profile("ru-manual-jp-kr", details_limit=120),
        client=client,
        path=tmp_path / "watchbane.sqlite3",
        current_year=2026,
    )

    assert result.created_count == autofill.STARTER_POOL_TARGET
    assert _candidate_country_hit_rate(result.candidates) == 1.0
    assert _candidate_quality_rate(result.candidates, "garbage") < 0.3917
    assert result.localization_fallback_count > 0
    assert result.missing_overview_after_fallback < 10


def test_acceptance_scenario_ru_foreign_new_movies_us_gb_improves_missing_overview_without_broad_origin(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("config.constant.APP_DATA_DIR", str(tmp_path / "data"))
    client = LocalizedScenarioTmdbClient()

    result = run_onboarding_autofill(
        _scenario_profile("ru-foreign-new-movies-us-gb", details_limit=120),
        client=client,
        path=tmp_path / "watchbane.sqlite3",
        current_year=2026,
    )

    assert result.created_count > 0
    assert _candidate_country_hit_rate(result.candidates) == 1.0
    assert _candidate_quality_rate(result.candidates, "garbage") < 0.2417
    assert result.localization_fallback_count > 0
    assert result.missing_overview_after_fallback == 0
    assert all("with_origin_country" in params for _endpoint, params in client.calls)


def test_acceptance_scenario_dark_new_tv_us_gb_keeps_dark_vibe_and_country_clean(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("config.constant.APP_DATA_DIR", str(tmp_path / "data"))
    client = PagedYieldTmdbClient(accepted_per_page=20, total_pages=10, country="US")

    result = run_onboarding_autofill(
        _scenario_profile("dark-new-tv-us-gb", details_enrichment={"enabled": False}),
        client=client,
        path=tmp_path / "watchbane.sqlite3",
        current_year=2026,
    )

    assert result.created_count > 0
    assert _dark_vibe_hit_rate(result.candidates) >= 0.9
    assert _candidate_quality_rate(result.candidates, "garbage") == 0.0
    assert _country_leakage_count(result.candidates, "RU") == 0


def test_future_or_unreleased_results_are_rejected(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("config.constant.APP_DATA_DIR", str(tmp_path / "data"))
    db_path = tmp_path / "watchbane.sqlite3"
    result = run_onboarding_autofill(
        _profile(media_preference="movie", release_preference="new"),
        client=FutureTmdbClient(),
        path=db_path,
        current_year=2026,
    )

    assert result.created_count == 0
    assert result.rejected_future_count > 0
    assert any(warning.startswith("Rejected future/unreleased titles:") for warning in result.warnings)


def test_onboarding_plan_view_has_target_quotas_without_api_calls() -> None:
    from candidates import service

    plan = service.get_onboarding_autofill_plan_view({
        "media_preference": "movie",
        "release_preference": "new",
        "vibe_preference": "dark",
        "origin_preference": "foreign",
        "ui_language": "ru",
    })

    assert plan["target"] == autofill.STARTER_POOL_TARGET
    assert plan["quotas"]["media_type"][MEDIA_MOVIE] == 120
    assert MEDIA_TV not in plan["quotas"]["media_type"]
    assert plan["quotas"]["country"] == {"US": 60, "GB": 60}
    assert plan["country_plan"] == {"US": 60, "GB": 60}
    assert plan["country_selection"]["exclude_home_country"] is True
    assert plan["quotas"]["origin"] == {"foreign": 120}


def test_candidate_identity_is_media_type_plus_tmdb_id() -> None:
    index = {"tmdb_identities": {(MEDIA_MOVIE, 7)}, "media_title_year_keys": set()}
    movie = {"id": 7, "title": "Seven", "release_date": "1995-01-01"}
    tv = {"id": 7, "name": "Seven", "first_air_date": "1995-01-01"}
    assert autofill.discover_item_existing_reason(movie, index, media_type=MEDIA_MOVIE) == "tmdb_id"
    assert autofill.discover_item_existing_reason(tv, index, media_type=MEDIA_TV) is None


def test_watched_existing_and_hidden_candidates_are_skipped(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("config.constant.APP_DATA_DIR", str(tmp_path / "data"))
    bucket = build_fetch_buckets(_profile(media_preference="movie"))[0]
    result = {
        "id": 42,
        "title": "Skip Me",
        "release_date": "2024-01-01",
        "poster_path": "/p.jpg",
        "vote_average": 7.0,
        "vote_count": 2000,
    }
    assert autofill.accept_candidate(
        result,
        bucket,
        existing_index={"tmdb_identities": {(bucket.media_type, 42)}, "media_title_year_keys": set()},
        accepted_identities=set(),
        hidden_or_rejected_identities=set(),
        watched_signatures=set(),
        dataset_title_keys=set(),
    ) is False

    assert autofill.accept_candidate(
        result,
        bucket,
        existing_index={"tmdb_identities": set(), "media_title_year_keys": set()},
        accepted_identities={(bucket.media_type, 42)},
        hidden_or_rejected_identities=set(),
        watched_signatures=set(),
        dataset_title_keys=set(),
    ) is False

    assert autofill.accept_candidate(
        result,
        bucket,
        existing_index={"tmdb_identities": set(), "media_title_year_keys": set()},
        accepted_identities=set(),
        hidden_or_rejected_identities={"skip me|2024"},
        watched_signatures=set(),
        dataset_title_keys=set(),
    ) is False


def test_low_vote_candidate_is_not_filtered_before_local_scoring(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("config.constant.APP_DATA_DIR", str(tmp_path / "data"))
    bucket = build_fetch_buckets(_profile(media_preference="tv", country_selection={"selected_countries": ["RU"]}))[0]
    result = {
        "id": 777,
        "name": "Small Strong Show",
        "first_air_date": "2024-01-01",
        "origin_country": ["RU"],
        "poster_path": "/p.jpg",
        "vote_average": 8.5,
        "vote_count": 5,
    }

    assert autofill.accept_candidate(
        result,
        bucket,
        existing_index={"tmdb_identities": set(), "media_title_year_keys": set()},
        accepted_identities=set(),
        hidden_or_rejected_identities=set(),
        watched_signatures=set(),
        dataset_title_keys=set(),
        current_date=date(2026, 7, 8),
    ) is True


def test_vote_confidence_scales_rating_bonus_without_rejection() -> None:
    bucket = build_fetch_buckets(_profile(media_preference="movie"))[0]
    low_vote = {
        "id": 1,
        "title": "Tiny Perfect",
        "release_date": "2024-01-01",
        "vote_average": 10.0,
        "vote_count": 1,
        "popularity": 0,
    }
    strong = {
        "id": 2,
        "title": "Strong Eight",
        "release_date": "2024-01-01",
        "vote_average": 8.0,
        "vote_count": 500,
        "popularity": 0,
    }
    empty = {
        "id": 3,
        "title": "No Votes",
        "release_date": "2024-01-01",
        "vote_average": 0,
        "vote_count": 0,
        "popularity": 0,
    }

    low_debug = autofill.compute_candidate_score_debug(low_vote, bucket, page=1, index_on_page=0)
    strong_debug = autofill.compute_candidate_score_debug(strong, bucket, page=1, index_on_page=0)
    empty_debug = autofill.compute_candidate_score_debug(empty, bucket, page=1, index_on_page=0)

    assert autofill.vote_confidence_for_count(0) == 0.15
    assert low_debug["vote_confidence"] == 0.25
    assert strong_debug["vote_confidence"] == 1.0
    assert low_debug["rating_bonus_raw"] == 1000.0
    assert low_debug["rating_bonus_adjusted"] == 250.0
    assert low_debug["rating_bonus_adjusted"] < strong_debug["rating_bonus_adjusted"]
    assert low_debug["final_score"] < strong_debug["final_score"]
    assert empty_debug["rating_bonus_adjusted"] == 0.0


def test_onboarding_candidate_record_includes_score_debug_fields() -> None:
    bucket = build_fetch_buckets(_profile(media_preference="movie"))[0]
    result = {
        "id": 42,
        "title": "Debug Movie",
        "original_title": "Debug Movie",
        "release_date": "2024-01-01",
        "overview": "Overview",
        "genre_ids": [18],
        "origin_country": [bucket.target_country],
        "vote_average": 8.0,
        "vote_count": 500,
        "popularity": 50,
    }
    score_debug = autofill.compute_candidate_score_debug(result, bucket, page=1, index_on_page=0)

    candidate = autofill.build_candidate_record_from_result(
        result,
        bucket,
        genre_lookup={MEDIA_MOVIE: {18: "Drama"}, MEDIA_TV: {}},
        profile_id=1,
        candidate_score=float(score_debug["final_score"]),
        score_debug=score_debug,
        fetch_rank=1,
    )

    assert candidate["score_debug"]["rating_bonus_raw"] == 800.0
    assert candidate["score_debug"]["vote_confidence"] == 1.0
    assert candidate["score_debug"]["rating_bonus_adjusted"] == 800.0
    assert candidate["score_debug"]["final_score"] == score_debug["final_score"]
    assert 0 <= candidate["quality_score"] <= 1
    assert 0 <= candidate["hidden_gem_score"] <= 1
    assert 0 <= candidate["final_score"] <= 1


def test_details_enrichment_dedupes_before_details_requests(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("config.constant.APP_DATA_DIR", str(tmp_path / "data"))
    client = DuplicateDiscoverTmdbClient()

    result = run_onboarding_autofill(
        _profile(
            media_preference="movie",
            country_selection={"selected_countries": ["US"], "home_country": "US"},
            details_limit=10,
        ),
        client=client,
        path=tmp_path / "watchbane.sqlite3",
        current_year=2026,
    )

    assert result.created_count == 1
    assert result.details_requests == 1
    assert [(media, tmdb_id) for media, tmdb_id, _language, _appends in client.details_calls] == [(MEDIA_MOVIE, 101)]
    assert result.candidates[0]["details_enriched"] is True
    assert result.candidates[0]["imdb_id"] == "tt0000101"


def test_details_enrichment_dedupes_raw_tmdb_id_across_pages_before_details(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("config.constant.APP_DATA_DIR", str(tmp_path / "data"))
    client = DuplicateAcrossPagesTmdbClient()

    result = run_onboarding_autofill(
        _profile(
            media_preference="movie",
            country_selection={"selected_countries": ["US"], "home_country": "US"},
            details_limit=10,
        ),
        client=client,
        path=tmp_path / "watchbane.sqlite3",
        current_year=2026,
    )

    assert result.created_count == 1
    assert result.details_requests == 1
    assert [(media, tmdb_id) for media, tmdb_id, _language, _appends in client.details_calls] == [(MEDIA_MOVIE, 202)]


def test_details_enrichment_dedupes_title_year_before_details_for_different_tmdb_ids(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("config.constant.APP_DATA_DIR", str(tmp_path / "data"))
    client = DuplicateTitleDifferentIdsTmdbClient()

    result = run_onboarding_autofill(
        _profile(
            media_preference="movie",
            country_selection={"selected_countries": ["US"], "home_country": "US"},
            details_limit=10,
        ),
        client=client,
        path=tmp_path / "watchbane.sqlite3",
        current_year=2026,
    )

    assert result.created_count == 1
    assert result.details_requests == 1
    assert len(client.details_calls) == 1
    assert client.details_calls[0][1] == 301


def test_details_enrichment_skips_already_watched_before_details(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("config.constant.APP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(
        autofill,
        "build_watched_signatures",
        lambda: {title_identity_key({"title": "Already Watched", "year": 2024})},
    )
    monkeypatch.setattr(autofill, "build_dataset_title_keys", lambda: set())
    client = SingleWatchedLikeTmdbClient()

    result = run_onboarding_autofill(
        _profile(
            media_preference="movie",
            country_selection={"selected_countries": ["US"], "home_country": "US"},
            details_limit=10,
        ),
        client=client,
        path=tmp_path / "watchbane.sqlite3",
        current_year=2026,
    )

    assert result.created_count == 0
    assert result.details_requests == 0
    assert client.details_calls == []


def test_details_enrichment_skips_existing_pool_candidate_before_details(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("config.constant.APP_DATA_DIR", str(tmp_path / "data"))
    db_path = tmp_path / "watchbane.sqlite3"
    existing = {
        "media_type": MEDIA_MOVIE,
        "tmdb_id": 404,
        "title": "Already Watched",
        "year": 2024,
        "release_date": "2024-01-01",
        "tmdb_score": 7.0,
        "tmdb_votes": 100,
        "genres": ["Drama"],
        "countries": ["US"],
        "country_codes": ["US"],
    }
    save_candidate_pool_dict({pool_entry_key(existing): existing}, path=db_path, purge_watched=False)
    client = SingleWatchedLikeTmdbClient()

    result = run_onboarding_autofill(
        _profile(
            media_preference="movie",
            country_selection={"selected_countries": ["US"], "home_country": "US"},
            details_limit=10,
        ),
        client=client,
        path=db_path,
        current_year=2026,
    )

    assert result.created_count == 0
    assert result.details_requests == 0
    assert client.details_calls == []


def test_details_enrichment_respects_details_limit_per_bucket(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("config.constant.APP_DATA_DIR", str(tmp_path / "data"))
    client = LocalizedScenarioTmdbClient(country="JP")

    result = run_onboarding_autofill(
        _profile(
            media_preference="movie",
            ui_language="ru",
            country_selection={"selected_countries": ["JP"], "home_country": "RU"},
            details_limit=3,
        ),
        client=client,
        path=tmp_path / "watchbane.sqlite3",
        current_year=2026,
    )

    assert result.details_requests == 3
    assert len(client.details_calls) == 3
    assert all(call[0] == MEDIA_MOVIE for call in client.details_calls)


def test_details_enrichment_prioritizes_missing_overview_over_external_id_only(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("config.constant.APP_DATA_DIR", str(tmp_path / "data"))
    client = DetailsPriorityTmdbClient()

    result = run_onboarding_autofill(
        _profile(
            media_preference="movie",
            ui_language="ru",
            country_selection={"selected_countries": ["JP"], "home_country": "RU"},
            details_limit=1,
        ),
        client=client,
        path=tmp_path / "watchbane.sqlite3",
        current_year=2026,
    )

    assert result.details_requests == 1
    assert [call[1] for call in client.details_calls] == [1002]
    assert result.localization_fallback_count == 1


def test_details_enrichment_limit_includes_localization_fallback_requests(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("config.constant.APP_DATA_DIR", str(tmp_path / "data"))
    client = MissingOverviewLocalizationTmdbClient(
        country="JP",
        original_language="ja",
        original_overview="",
        en_overview="English overview",
    )

    result = run_onboarding_autofill(
        _profile(
            media_preference="movie",
            ui_language="ru",
            country_selection={"selected_countries": ["JP"], "home_country": "RU"},
            details_limit=2,
        ),
        client=client,
        path=tmp_path / "watchbane.sqlite3",
        current_year=2026,
    )

    assert result.details_requests == 2
    assert [call[2] for call in client.details_calls] == ["ru-RU", "ja-JP"]
    assert all(call[2] != "en-US" for call in client.details_calls)


def test_details_enrichment_can_be_disabled(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("config.constant.APP_DATA_DIR", str(tmp_path / "data"))
    client = FakeTmdbClient()

    result = run_onboarding_autofill(
        _profile(
            media_preference="movie",
            country_selection={"selected_countries": ["US"], "home_country": "US"},
            details_enrichment={"enabled": False},
        ),
        client=client,
        path=tmp_path / "watchbane.sqlite3",
        current_year=2026,
    )

    assert result.details_requests == 0
    assert client.details_calls == []
    assert all(candidate["details_enriched"] is False for candidate in result.candidates)


def test_missing_ru_overview_falls_back_to_original_language(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("config.constant.APP_DATA_DIR", str(tmp_path / "data"))
    client = MissingOverviewLocalizationTmdbClient(
        country="JP",
        original_language="ja",
        original_overview="Japanese overview",
        en_overview="English overview",
    )

    result = run_onboarding_autofill(
        _profile(
            media_preference="movie",
            ui_language="ru",
            country_selection={"selected_countries": ["JP"], "home_country": "RU"},
            details_limit=5,
        ),
        client=client,
        path=tmp_path / "watchbane.sqlite3",
        current_year=2026,
    )

    assert result.details_requests == 2
    assert [call[2] for call in client.details_calls] == ["ru-RU", "ja-JP"]
    assert result.localization_fallback_count == 1
    assert result.overview_fallback_original_language_count == 1
    assert result.overview_fallback_en_count == 0
    candidate = result.candidates[0]
    assert candidate["overview"] == "Japanese overview"
    assert candidate["overview_source"] == "original_language"
    assert candidate["metadata_missing_overview"] is False
    assert candidate["score_debug"]["metadata_overview_penalty"] == 150.0


def test_missing_ru_and_original_overview_falls_back_to_en(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("config.constant.APP_DATA_DIR", str(tmp_path / "data"))
    client = MissingOverviewLocalizationTmdbClient(
        country="JP",
        original_language="ja",
        original_overview="",
        en_overview="English overview",
    )

    result = run_onboarding_autofill(
        _profile(
            media_preference="movie",
            ui_language="ru",
            country_selection={"selected_countries": ["JP"], "home_country": "RU"},
            details_limit=5,
        ),
        client=client,
        path=tmp_path / "watchbane.sqlite3",
        current_year=2026,
    )

    assert result.details_requests == 3
    assert [call[2] for call in client.details_calls] == ["ru-RU", "ja-JP", "en-US"]
    assert result.localization_fallback_count == 1
    assert result.overview_fallback_original_language_count == 0
    assert result.overview_fallback_en_count == 1
    candidate = result.candidates[0]
    assert candidate["overview"] == "English overview"
    assert candidate["overview_source"] == "en-US"
    assert candidate["metadata_missing_overview"] is False
    assert candidate["score_debug"]["metadata_overview_penalty"] == 150.0


def test_missing_overview_after_fallback_gets_metadata_penalty(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("config.constant.APP_DATA_DIR", str(tmp_path / "data"))
    client = MissingOverviewLocalizationTmdbClient(
        country="JP",
        original_language="ja",
        original_overview="",
        en_overview="",
    )

    result = run_onboarding_autofill(
        _profile(
            media_preference="movie",
            ui_language="ru",
            country_selection={"selected_countries": ["JP"], "home_country": "RU"},
            details_limit=5,
        ),
        client=client,
        path=tmp_path / "watchbane.sqlite3",
        current_year=2026,
    )

    assert result.details_requests == 3
    assert result.localization_fallback_count == 1
    assert result.missing_overview_after_fallback == 1
    candidate = result.candidates[0]
    assert candidate["overview"] in (None, "")
    assert candidate["overview_source"] == "missing"
    assert candidate["metadata_missing_overview"] is True
    assert candidate["score_debug"]["metadata_overview_penalty"] == 1200.0


def test_jp_and_kr_missing_overview_trigger_localization_fallback(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("config.constant.APP_DATA_DIR", str(tmp_path / "data"))

    for country, language, expected_locale in (("JP", "ja", "ja-JP"), ("KR", "ko", "ko-KR")):
        client = MissingOverviewLocalizationTmdbClient(
            country=country,
            original_language=language,
            original_overview=f"{country} overview",
        )
        result = run_onboarding_autofill(
            _profile(
                media_preference="movie",
                ui_language="ru",
                country_selection={"selected_countries": [country], "home_country": "RU"},
                details_limit=5,
            ),
            client=client,
            path=tmp_path / f"{country.lower()}.sqlite3",
            current_year=2026,
        )

        assert result.localization_fallback_count == 1
        assert expected_locale in [call[2] for call in client.details_calls]
        assert result.candidates[0]["overview"] == f"{country} overview"
        assert result.candidates[0]["overview_source"] == "original_language"


def test_quality_gate_marks_missing_overview_and_missing_poster_as_garbage() -> None:
    bucket = build_fetch_buckets(_profile(media_preference="movie"))[0]
    result = {
        "id": 1,
        "title": "No Useful Metadata",
        "release_date": "2024-01-01",
        "poster_path": "",
        "overview": "",
        "genre_ids": [18],
        "origin_country": [bucket.target_country],
        "vote_average": 7.0,
        "vote_count": 100,
        "popularity": 20,
        "metadata_missing_overview": True,
        "overview_source": "missing",
    }

    decision = autofill.classify_candidate_quality(result, bucket)

    assert decision.quality_class == "garbage"
    assert "missing_poster_and_overview" in decision.quality_reasons


def test_quality_gate_marks_missing_overview_low_confidence_as_garbage() -> None:
    bucket = build_fetch_buckets(_profile(media_preference="movie"))[0]
    result = {
        "id": 2,
        "title": "Low Confidence",
        "release_date": "2024-01-01",
        "poster_path": "/poster.jpg",
        "overview": "",
        "genre_ids": [18],
        "origin_country": [bucket.target_country],
        "vote_average": 5.0,
        "vote_count": 5,
        "popularity": 1,
        "metadata_missing_overview": True,
        "overview_source": "missing",
    }

    decision = autofill.classify_candidate_quality(result, bucket)
    score_debug = autofill.compute_candidate_score_debug(result, bucket, page=1, index_on_page=0, quality_decision=decision)

    assert decision.quality_class == "garbage"
    assert "missing_overview_low_confidence" in decision.quality_reasons
    assert score_debug["garbage_penalty"] == 50000.0


def test_quality_gate_marks_wrong_country_media_junk_and_adult_title_as_garbage() -> None:
    movie_bucket = build_fetch_buckets(
        _profile(
            media_preference="movie",
            country_selection={"selected_countries": ["US"], "home_country": "US"},
        )
    )[0]
    tv_bucket = build_fetch_buckets(
        _profile(
            media_preference="tv",
            country_selection={"selected_countries": ["US"], "home_country": "US"},
        )
    )[0]
    base = {
        "id": 10,
        "title": "Useful",
        "release_date": "2024-01-01",
        "poster_path": "/poster.jpg",
        "overview": "Overview",
        "genre_ids": [18],
        "origin_country": ["US"],
        "vote_average": 7.0,
        "vote_count": 100,
        "popularity": 30,
        "external_ids": {"imdb_id": "tt0000010"},
    }

    wrong_country = {**base, "origin_country": ["FR"]}
    assert autofill.classify_candidate_quality(wrong_country, movie_bucket).quality_reasons == ("wrong_country",)

    wrong_media = {**base, "media_type": MEDIA_TV}
    media_decision = autofill.classify_candidate_quality(wrong_media, movie_bucket)
    assert media_decision.quality_class == "garbage"
    assert "wrong_media_type" in media_decision.quality_reasons

    junk_tv = {
        **base,
        "name": "Reality Junk",
        "first_air_date": "2024-01-01",
        "genre_ids": [autofill.TV_JUNK_GENRE_IDS[0]],
    }
    junk_decision = autofill.classify_candidate_quality(junk_tv, tv_bucket)
    assert junk_decision.quality_class == "garbage"
    assert "junk_genre" in junk_decision.quality_reasons

    adult_like = {
        **base,
        "title": "Erotic Night",
        "overview": "",
        "overview_source": "missing",
        "metadata_missing_overview": True,
        "adult": False,
    }
    adult_decision = autofill.classify_candidate_quality(adult_like, movie_bucket)
    assert adult_decision.quality_class == "garbage"
    assert "suspicious_adult_title" in adult_decision.quality_reasons

    adult_flag = {**base, "adult": True}
    adult_flag_decision = autofill.classify_candidate_quality(adult_flag, movie_bucket)
    assert adult_flag_decision.quality_class == "garbage"
    assert "adult_content" in adult_flag_decision.quality_reasons


def test_quality_gate_duplicate_like_flag_is_garbage() -> None:
    bucket = build_fetch_buckets(_profile(media_preference="movie"))[0]
    result = {
        "id": 11,
        "title": "Duplicate Candidate",
        "release_date": "2024-01-01",
        "poster_path": "/poster.jpg",
        "overview": "Overview",
        "genre_ids": [18],
        "origin_country": [bucket.target_country],
        "vote_average": 7.0,
        "vote_count": 100,
        "popularity": 30,
        "external_ids": {"imdb_id": "tt0000011"},
        "_duplicate_like": True,
    }

    decision = autofill.classify_candidate_quality(result, bucket)

    assert decision.quality_class == "garbage"
    assert "duplicate_like" in decision.quality_reasons


def test_quality_gate_fallback_overview_low_votes_and_rating_zero_are_weak_not_garbage() -> None:
    bucket = build_fetch_buckets(_profile(media_preference="movie"))[0]
    base = {
        "id": 12,
        "title": "Useful Weak Candidate",
        "release_date": "2024-01-01",
        "poster_path": "/poster.jpg",
        "overview": "Fallback overview",
        "genre_ids": [18],
        "origin_country": [bucket.target_country],
        "vote_average": 7.0,
        "vote_count": 100,
        "popularity": 30,
        "external_ids": {"imdb_id": "tt0000012"},
    }

    fallback_overview = {**base, "overview_source": "en-US"}
    fallback_decision = autofill.classify_candidate_quality(fallback_overview, bucket)
    assert fallback_decision.quality_class == "weak"
    assert "fallback_overview" in fallback_decision.quality_reasons

    low_votes = {**base, "vote_count": 10}
    low_vote_decision = autofill.classify_candidate_quality(low_votes, bucket)
    assert low_vote_decision.quality_class == "weak"
    assert "low_votes" in low_vote_decision.quality_reasons

    rating_zero = {**base, "vote_average": 0, "vote_count": 100, "popularity": 30}
    rating_decision = autofill.classify_candidate_quality(rating_zero, bucket)
    assert rating_decision.quality_class == "weak"
    assert "rating_0" in rating_decision.quality_reasons


def test_quality_gate_no_external_id_alone_does_not_make_strong_candidate_weak() -> None:
    bucket = build_fetch_buckets(_profile(media_preference="movie"))[0]
    result = {
        "id": 13,
        "title": "Strong Candidate",
        "release_date": "2024-01-01",
        "poster_path": "/poster.jpg",
        "overview": "Useful overview",
        "genre_ids": [18],
        "origin_country": [bucket.target_country],
        "vote_average": 8.0,
        "vote_count": 500,
        "popularity": 50,
    }

    decision = autofill.classify_candidate_quality(result, bucket)

    assert decision.quality_class == "good"
    assert "no_external_id" not in decision.quality_reasons


def test_quality_gate_blocks_garbage_candidates_from_normal_pool(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("config.constant.APP_DATA_DIR", str(tmp_path / "data"))
    client = LowConfidenceMissingOverviewTmdbClient()

    result = run_onboarding_autofill(
        _profile(
            media_preference="movie",
            country_selection={"selected_countries": ["US"], "home_country": "US"},
            details_limit=3,
        ),
        client=client,
        path=tmp_path / "watchbane.sqlite3",
        current_year=2026,
    )

    assert result.created_count == 0
    assert result.candidates == []
    assert result.details_requests == 1


def test_quality_gate_allows_weak_low_vote_candidates_when_metadata_is_good(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("config.constant.APP_DATA_DIR", str(tmp_path / "data"))
    client = WeakLowVoteTmdbClient()

    result = run_onboarding_autofill(
        _profile(
            media_preference="movie",
            country_selection={"selected_countries": ["US"], "home_country": "US"},
            details_enrichment={"enabled": False},
        ),
        client=client,
        path=tmp_path / "watchbane.sqlite3",
        current_year=2026,
    )

    assert result.created_count == 1
    candidate = result.candidates[0]
    assert candidate["quality_class"] == "weak"
    assert "low_votes" in candidate["quality_reasons"]
    assert candidate["score_debug"]["weak_penalty"] == 350.0


def test_quality_report_sample_includes_quality_class_and_reasons() -> None:
    from scripts.reports import run_onboarding_discover_quality_report as report

    row = report._candidate_row(
        {
            "fetch_rank": 1,
            "title": "Sample",
            "year": 2024,
            "media_type": "movie",
            "target_country": "US",
            "original_language": "en",
            "tmdb_score": 7.0,
            "tmdb_votes": 10,
            "tmdb_popularity": 20,
            "final_score": 9.5,
            "quality_class": "weak",
            "quality_reasons": ["low_votes"],
            "source_query": {"fallback": "base"},
        }
    )

    assert row["quality_class"] == "weak"
    assert row["quality_reasons"] == ["low_votes"]


def test_acceptance_ru_tv_manual_sweep_contract() -> None:
    profile = _profile(
        media_preference="tv",
        country_selection={"selected_countries": ["RU"], "home_country": "RU"},
        min_year=2010,
        include_genres=[18, 9648, 80],
        include_genre_mode="or",
        exclude_genres=[10766, 10764, 10767, 10763, 10762, 99],
        discover_pages=5,
    )
    buckets = build_fetch_buckets(profile)

    assert len(buckets) == 1
    bucket = buckets[0]
    endpoint, params = build_discover_request(
        bucket,
        profile=profile,
        fallback="base",
        request_index=0,
        current_year=2026,
        current_date=date(2026, 7, 8),
    )

    assert endpoint == "/discover/tv"
    assert params["with_origin_country"] == "RU"
    assert params["first_air_date.gte"] == "2010-01-01"
    assert params["first_air_date.lte"] == "2026-07-08"
    assert params["with_genres"] == "18|9648|80"
    assert params["without_genres"] == "10766,10764,10767,10763,10762,99"
    assert "vote_count.gte" not in params
    assert "vote_average.gte" not in params


def test_autofill_can_be_cancelled_before_api_requests(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("config.constant.APP_DATA_DIR", str(tmp_path / "data"))
    client = FakeTmdbClient()

    result = run_onboarding_autofill(
        _profile(),
        client=client,
        path=tmp_path / "watchbane.sqlite3",
        cancel_checker=lambda: True,
    )

    assert result.cancelled is True
    assert result.created_count == 0
    assert result.api_requests == 0


def test_request_audit_rows_are_loadable(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("config.constant.APP_DATA_DIR", str(tmp_path / "data"))
    db_path = tmp_path / "watchbane.sqlite3"
    result = run_onboarding_autofill(_profile(), client=EmptyTmdbClient(), path=db_path)

    audits = load_autofill_request_audits(result.profile_id, path=db_path)

    assert result.created_count == 0
    assert len(audits) == result.api_requests + result.duplicate_requests_skipped
    assert sum(1 for audit in audits if audit["status"] == "skipped_duplicate") == result.duplicate_requests_skipped
    assert audits[0]["endpoint"] in {"/discover/movie", "/discover/tv"}
    assert isinstance(audits[0]["params"], dict)

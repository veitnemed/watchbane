"""Run onboarding candidate-pool scenarios in an isolated SQLite database.

Examples:
    py scripts/reports/run_onboarding_pool_rebuild.py --mock --all --output reports/onboarding/analysis/pool_mock_report.md
    py scripts/reports/run_onboarding_pool_rebuild.py --live --all --require-live --output reports/onboarding/analysis/pool_live_report.md
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import tempfile
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from apis import tmdb_api
from candidates.onboarding import autofill
from candidates.onboarding.autofill import MEDIA_MOVIE, MEDIA_TV, OnboardingTasteProfile
from candidates.models import country_schema
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


def _country_selection(
    *,
    mode: str,
    home_country: str,
    selected_countries: list[str],
    country_weights: dict[str, float],
    exclude_home_country: bool = False,
) -> dict[str, Any]:
    return {
        "mode": mode,
        "home_country": home_country,
        "selected_countries": selected_countries,
        "country_weights": country_weights,
        "exclude_home_country": exclude_home_country,
        "max_countries": len(selected_countries),
        "primary_country": selected_countries[0] if selected_countries else None,
        "secondary_country": selected_countries[1] if len(selected_countries) > 1 else None,
    }


def _equal_country_selection(
    selected_countries: list[str],
    *,
    home_country: str = "RU",
) -> dict[str, Any]:
    weight = 1.0 / len(selected_countries)
    return _country_selection(
        mode="single_country" if len(selected_countries) == 1 else "multi_country",
        home_country=home_country,
        selected_countries=selected_countries,
        country_weights={country: weight for country in selected_countries},
    )


FOREIGN_RU_SELECTION = _country_selection(
    mode="preset_foreign",
    home_country="RU",
    selected_countries=["US", "GB"],
    country_weights={"US": 0.90, "GB": 0.10},
    exclude_home_country=True,
)


SCENARIOS: dict[str, dict[str, Any]] = {
    "ru-countries-us-only": {
        "ui_language": "ru",
        "media_preference": "both",
        "release_preference": "mixed",
        "vibe_preference": "mixed",
        "origin_preference": "foreign",
        "country_selection": _equal_country_selection(["US"]),
    },
    "ru-countries-ru-only": {
        "ui_language": "ru",
        "media_preference": "both",
        "release_preference": "mixed",
        "vibe_preference": "mixed",
        "origin_preference": "domestic",
        "country_selection": _equal_country_selection(["RU"]),
    },
    "ru-countries-us-ru-gb": {
        "ui_language": "ru",
        "media_preference": "both",
        "release_preference": "mixed",
        "vibe_preference": "mixed",
        "origin_preference": "mixed",
        "country_selection": _equal_country_selection(["US", "RU", "GB"]),
    },
    "ru-countries-all-five": {
        "ui_language": "ru",
        "media_preference": "both",
        "release_preference": "mixed",
        "vibe_preference": "mixed",
        "origin_preference": "mixed",
        "country_selection": _equal_country_selection(["US", "RU", "GB", "KR", "JP"]),
    },
    "ru-foreign-new-movies-us-gb": {
        "ui_language": "ru",
        "media_preference": "movie",
        "release_preference": "new",
        "vibe_preference": "mixed",
        "origin_preference": "foreign",
        "country_selection": FOREIGN_RU_SELECTION,
    },
    "ru-foreign-new-tv-us-gb": {
        "ui_language": "ru",
        "media_preference": "tv",
        "release_preference": "new",
        "vibe_preference": "mixed",
        "origin_preference": "foreign",
        "country_selection": FOREIGN_RU_SELECTION,
    },
    "ru-mixed-ru-us": {
        "ui_language": "ru",
        "media_preference": "both",
        "release_preference": "mixed",
        "vibe_preference": "mixed",
        "origin_preference": "mixed",
        "country_selection": _country_selection(
            mode="preset_mixed",
            home_country="RU",
            selected_countries=["RU", "US"],
            country_weights={"RU": 0.15, "US": 0.85},
        ),
    },
    "ru-manual-us-kr": {
        "ui_language": "ru",
        "media_preference": "both",
        "release_preference": "mixed",
        "vibe_preference": "mixed",
        "origin_preference": "foreign",
        "country_selection": _country_selection(
            mode="country_pair",
            home_country="RU",
            selected_countries=["US", "KR"],
            country_weights={"US": 0.70, "KR": 0.30},
        ),
    },
    "ru-manual-jp-kr": {
        "ui_language": "ru",
        "media_preference": "both",
        "release_preference": "mixed",
        "vibe_preference": "mixed",
        "origin_preference": "foreign",
        "country_selection": _country_selection(
            mode="country_pair",
            home_country="RU",
            selected_countries=["JP", "KR"],
            country_weights={"JP": 0.50, "KR": 0.50},
        ),
    },
    "ru-domestic-ru-only": {
        "ui_language": "ru",
        "media_preference": "movie",
        "release_preference": "classic",
        "vibe_preference": "light",
        "origin_preference": "domestic",
        "country_selection": _country_selection(
            mode="single_country",
            home_country="RU",
            selected_countries=["RU"],
            country_weights={"RU": 1.0},
        ),
    },
    "ru-tv-manual-serious-2010": {
        "ui_language": "ru",
        "media_preference": "tv",
        "release_preference": "mixed",
        "vibe_preference": "dark",
        "origin_preference": "domestic",
        "country_selection": _equal_country_selection(["RU"]),
        "min_year": 2010,
        "include_genres": [18, 9648, 80],
        "include_genre_mode": "or",
        "exclude_genres": [10766, 10764, 10767, 10763, 10762, 99],
        "discover_pages": 5,
        "details_limit": 50,
    },
    "en-country-pair-us-gb": {
        "ui_language": "en",
        "media_preference": "both",
        "release_preference": "mixed",
        "vibe_preference": "mixed",
        "origin_preference": None,
        "country_selection": _country_selection(
            mode="country_pair",
            home_country="US",
            selected_countries=["US", "GB"],
            country_weights={"US": 0.90, "GB": 0.10},
        ),
    },
    "dark-new-tv-us-gb": {
        "ui_language": "ru",
        "media_preference": "tv",
        "release_preference": "new",
        "vibe_preference": "dark",
        "origin_preference": "foreign",
        "country_selection": FOREIGN_RU_SELECTION,
    },
    "light-new-movies-us-gb": {
        "ui_language": "ru",
        "media_preference": "movie",
        "release_preference": "new",
        "vibe_preference": "light",
        "origin_preference": "foreign",
        "country_selection": FOREIGN_RU_SELECTION,
    },
    "classic-movies-fr-it": {
        "ui_language": "ru",
        "media_preference": "movie",
        "release_preference": "classic",
        "vibe_preference": "mixed",
        "origin_preference": "foreign",
        "country_selection": _country_selection(
            mode="country_pair",
            home_country="RU",
            selected_countries=["FR", "IT"],
            country_weights={"FR": 0.50, "IT": 0.50},
        ),
    },
}


class MockTmdbClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.details_calls: list[tuple[str, int, str, tuple[str, ...]]] = []
        self._metadata_by_id: dict[int, dict[str, Any]] = {}

    def movie_genres(self, language: str = "en") -> list[dict[str, Any]]:
        del language
        return list(MOVIE_GENRES)

    def tv_genres(self, language: str = "en") -> list[dict[str, Any]]:
        del language
        return list(TV_GENRES)

    def _language_for_country(self, country: str) -> str:
        return {
            "FR": "fr",
            "GB": "en",
            "IT": "it",
            "JP": "ja",
            "KR": "ko",
            "RU": "ru",
            "US": "en",
        }.get(str(country or "").upper(), "en")

    def _should_omit_overview(self, *, country: str, media_type: str, year: int, index: int) -> bool:
        country = str(country or "").upper()
        if country in {"JP", "KR"}:
            return index % 2 == 0
        if media_type == MEDIA_MOVIE and country in {"US", "GB"} and year >= 2022:
            return index % 5 == 0
        if media_type == MEDIA_MOVIE and country in {"FR", "IT"} and year <= 2021:
            return index % 7 == 0
        return False

    def _is_mock_garbage(self, *, country: str, media_type: str, year: int, index: int) -> bool:
        return media_type == MEDIA_MOVIE and year >= 2022 and str(country or "").upper() in {"US", "GB", "JP", "KR"} and index == 17

    def _mock_overview(self, *, country: str, media_type: str, year: int, index: int) -> str:
        if self._should_omit_overview(country=country, media_type=media_type, year=year, index=index):
            return ""
        return f"Mock {country} overview"

    def discover(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((endpoint, dict(params)))
        media_type = MEDIA_MOVIE if endpoint == "/discover/movie" else MEDIA_TV
        call_index = len(self.calls)
        year = int(params.get("primary_release_year") or params.get("first_air_date_year") or 2024)
        genre_text = str(params.get("with_genres") or "")
        genre_ids = [int(item) for item in genre_text.split("|") if item.isdigit()]
        if not genre_ids:
            genre_ids = [35] if media_type == MEDIA_MOVIE else [18]
        country = str(params.get("with_origin_country") or "US")
        results = []
        for index in range(20):
            tmdb_id = call_index * 1000 + index
            original_language = self._language_for_country(country)
            overview = self._mock_overview(country=country, media_type=media_type, year=year, index=index)
            poster_path = f"/movie{tmdb_id}.jpg" if media_type == MEDIA_MOVIE else f"/series{tmdb_id}.jpg"
            vote_average = 7.2 if media_type == MEDIA_MOVIE else 7.1
            vote_count = 1200 if media_type == MEDIA_MOVIE else 500
            popularity = 50 if media_type == MEDIA_MOVIE else 40
            title_prefix = "Mock Movie" if media_type == MEDIA_MOVIE else "Mock Series"
            if index % 11 == 0:
                vote_count = 10
                popularity = 20
            if self._is_mock_garbage(country=country, media_type=media_type, year=year, index=index):
                title_prefix = "Erotic Mock Junk"
                overview = ""
                poster_path = ""
                vote_average = 4.0
                vote_count = 1
                popularity = 1
            mock_title = f"{title_prefix} {tmdb_id}"
            self._metadata_by_id[int(tmdb_id)] = {
                "country": country,
                "media_type": media_type,
                "original_language": original_language,
                "overview": overview,
                "poster_path": poster_path,
                "vote_average": vote_average,
                "vote_count": vote_count,
                "popularity": popularity,
                "year": year,
                "title": mock_title,
                "mock_garbage": title_prefix == "Erotic Mock Junk",
            }
            if media_type == MEDIA_MOVIE:
                results.append(
                    {
                        "id": tmdb_id,
                        "title": mock_title,
                        "original_title": mock_title,
                        "release_date": f"{year}-01-01",
                        "poster_path": poster_path,
                        "overview": overview,
                        "genre_ids": genre_ids,
                        "origin_country": [country],
                        "vote_average": vote_average,
                        "vote_count": vote_count,
                        "popularity": popularity,
                        "original_language": params.get("with_original_language") or original_language,
                    }
                )
            else:
                results.append(
                    {
                        "id": tmdb_id,
                        "name": mock_title,
                        "original_name": mock_title,
                        "first_air_date": f"{year}-01-01",
                        "origin_country": [country],
                        "poster_path": poster_path,
                        "overview": overview,
                        "genre_ids": genre_ids,
                        "vote_average": vote_average,
                        "vote_count": vote_count,
                        "popularity": popularity,
                        "original_language": params.get("with_original_language") or original_language,
                    }
                )
        return {"results": results, "total_pages": 10}

    def _details(self, tmdb_id: int, media_type: str, language: str, append_to_response=None) -> dict[str, Any]:
        appends = tuple(append_to_response or ())
        self.details_calls.append((media_type, int(tmdb_id), language, appends))
        metadata = dict(self._metadata_by_id.get(int(tmdb_id)) or {})
        country = str(metadata.get("country") or "US")
        original_language = str(metadata.get("original_language") or self._language_for_country(country))
        original_locale = autofill._original_language_to_tmdb_locale(original_language)
        overview = ""
        if not bool(metadata.get("mock_garbage")):
            if language == original_locale:
                overview = f"Mock {country} localized overview"
            elif language == "en-US":
                overview = f"Mock {country} English overview"
            elif language == "ru-RU" and original_language == "ru":
                overview = f"Mock {country} overview"
            if metadata.get("overview") and language in {"ru-RU", "en-US", original_locale}:
                overview = str(metadata.get("overview"))
        poster_path = metadata.get("poster_path")
        if poster_path in (None, "") and not bool(metadata.get("mock_garbage")):
            poster_path = f"/details{int(tmdb_id)}.jpg"
        common = {
            "id": int(tmdb_id),
            "overview": overview,
            "genres": [{"id": 18, "name": "Drama"}],
            "vote_average": metadata.get("vote_average", 7.4),
            "vote_count": metadata.get("vote_count", 120),
            "popularity": metadata.get("popularity", 40),
            "poster_path": poster_path,
            "original_language": original_language,
            "external_ids": {"imdb_id": f"tt{int(tmdb_id):07d}"} if "external_ids" in appends else {},
        }
        if media_type == MEDIA_MOVIE:
            common.update({
                "title": str(metadata.get("title") or f"Mock Movie {int(tmdb_id)}"),
                "original_title": str(metadata.get("title") or f"Mock Movie {int(tmdb_id)}"),
                "release_date": f"{int(metadata.get('year') or 2024)}-01-01",
                "production_countries": [{"iso_3166_1": country, "name": country}],
            })
        else:
            common.update({
                "name": str(metadata.get("title") or f"Mock Series {int(tmdb_id)}"),
                "original_name": str(metadata.get("title") or f"Mock Series {int(tmdb_id)}"),
                "first_air_date": f"{int(metadata.get('year') or 2024)}-01-01",
                "origin_country": [country],
            })
        return common

    def movie_details(self, tmdb_id: int, language: str = "en", *, append_to_response=None) -> dict[str, Any]:
        return self._details(tmdb_id, MEDIA_MOVIE, language, append_to_response)

    def tv_details(self, tmdb_id: int, language: str = "en", *, append_to_response=None) -> dict[str, Any]:
        return self._details(tmdb_id, MEDIA_TV, language, append_to_response)


def _credentials_available() -> bool:
    try:
        tmdb_api.load_tmdb_credentials()
    except Exception:
        return False
    return True


def _counter(candidates: list[dict[str, Any]], key: str) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for candidate in candidates:
        value = candidate.get(key)
        if value not in (None, ""):
            counter[str(value)] += 1
    return dict(counter)


def _candidate_country_codes(candidate: dict[str, Any]) -> list[str]:
    return country_schema.normalize_country_filter_list(
        candidate.get("country_codes")
        or candidate.get("countries")
        or candidate.get("target_country")
    )


def _country_metrics(candidates: list[dict[str, Any]], profile: dict[str, Any]) -> dict[str, Any]:
    selection = profile.get("country_selection") if isinstance(profile.get("country_selection"), dict) else {}
    selected = set(country_schema.normalize_country_filter_list(selection.get("selected_countries")))
    home_country = country_schema.normalize_country_filter(selection.get("home_country")) or ""
    exclude_home_country = bool(selection.get("exclude_home_country"))
    hit_count = 0
    leakage_count = 0
    wrong_country_count = 0
    country_actual: Counter[str] = Counter()

    for candidate in candidates:
        target_country = country_schema.normalize_country_filter(candidate.get("target_country"))
        country_codes = _candidate_country_codes(candidate)
        if target_country:
            country_actual[target_country] += 1
        if target_country in selected and (not country_codes or target_country in country_codes):
            hit_count += 1
        elif selected and not (set(country_codes) & selected):
            wrong_country_count += 1
        if exclude_home_country and home_country and home_country in country_codes:
            leakage_count += 1

    total = len(candidates)
    return {
        "country_actual": dict(country_actual),
        "country_hit_count": hit_count,
        "country_hit_rate": round(hit_count / total, 4) if total else 0.0,
        "country_leakage_count": leakage_count,
        "country_leakage_rate": round(leakage_count / total, 4) if total else 0.0,
        "wrong_country_count": wrong_country_count,
    }


def _request_metrics(audits: list[dict[str, Any]]) -> dict[str, Any]:
    unique_requests: set[str] = set()
    without_country = 0
    duplicate_skipped = 0
    executed_count = 0
    for audit in audits:
        if audit.get("status") == "skipped_duplicate":
            duplicate_skipped += 1
            continue
        executed_count += 1
        params = dict(audit.get("params") or {})
        params.pop("_fallback", None)
        if "with_origin_country" not in params:
            without_country += 1
        unique_requests.add(json.dumps(
            {"endpoint": audit.get("endpoint"), "params": params},
            sort_keys=True,
            ensure_ascii=False,
        ))
    return {
        "requests_total": executed_count,
        "requests_unique": len(unique_requests),
        "requests_without_country": without_country,
        "duplicate_requests_observed": max(0, executed_count - len(unique_requests)),
        "duplicate_requests_skipped": duplicate_skipped,
    }


def _fallback_share(actual_counts: dict[str, dict[str, int]], total: int) -> float:
    fallback_counts = actual_counts.get("fallback", {})
    fallback_total = sum(
        int(count)
        for fallback, count in fallback_counts.items()
        if fallback != autofill.FALLBACK_BASE
    )
    return round(fallback_total / total, 4) if total else 0.0


def run_scenario(name: str, profile_data: dict[str, Any], *, live: bool, tmp_root: Path) -> dict[str, Any]:
    db_path = tmp_root / f"{name}.sqlite3"
    profile = OnboardingTasteProfile(**profile_data)
    client = None if live else MockTmdbClient()
    started_at = datetime.now(timezone.utc)
    result = autofill.run_onboarding_autofill(
        profile,
        client=client,
        path=db_path,
        current_year=started_at.year,
    )
    finished_at = datetime.now(timezone.utc)
    elapsed_ms = round((finished_at - started_at).total_seconds() * 1000, 1)
    candidates = result.candidates
    normalized_profile = profile.normalized().as_repository_dict()
    audits = load_autofill_request_audits(result.profile_id, path=db_path)
    country_metrics = _country_metrics(candidates, normalized_profile)
    request_metrics = _request_metrics(audits)
    return {
        "scenario": name,
        "mode": "live" if live else "mock",
        "db_path": str(db_path),
        "profile": normalized_profile,
        "ok": result.ok,
        "created_count": result.created_count,
        "pool_size": result.pool_size,
        "api_requests": result.api_requests,
        "details_requests": result.details_requests,
        "adaptive_pages_used": result.adaptive_pages_used,
        "pagination_stop_reasons": result.pagination_stop_reasons,
        "localization_fallback_count": result.localization_fallback_count,
        "overview_fallback_original_language_count": result.overview_fallback_original_language_count,
        "overview_fallback_en_count": result.overview_fallback_en_count,
        "missing_overview_after_fallback": result.missing_overview_after_fallback,
        "elapsed_ms": elapsed_ms,
        "planned_counts": result.planned_counts,
        "actual_counts": result.actual_counts,
        "country_plan": result.planned_counts.get("country", {}),
        **country_metrics,
        **request_metrics,
        "warnings": result.warnings,
        "rejected_future_count": result.rejected_future_count,
        "quality_gate_rejected_counts": result.quality_gate_rejected_counts or {},
        "quality_gate_rejected_reasons": result.quality_gate_rejected_reasons or {},
        "preference_diagnostics": result.preference_diagnostics or {},
        "preference_conflict_count": result.preference_conflict_count,
        "preference_warning_count": result.preference_warning_count,
        "preference_conflict_codes": list(result.preference_conflict_codes),
        "auto_fix_applied": result.preference_auto_fix_applied,
        "top_fallback_counts": result.actual_counts.get("fallback", {}),
        "fallback_share": _fallback_share(result.actual_counts, result.created_count),
        "candidate_media_counts": _counter(candidates, "media_type"),
        "candidate_origin_counts": _counter(candidates, "origin_bucket"),
    }


def _markdown(results: list[dict[str, Any]], *, live: bool, credentials_present: bool) -> str:
    lines = [
        "# Onboarding Pool Scenario Report",
        "",
        f"- Mode: {'live' if live else 'mock'}",
        f"- Generated: {datetime.now(timezone.utc).isoformat()}",
        f"- TMDb credentials present: {credentials_present}",
        f"- Target: {autofill.STARTER_POOL_TARGET}",
        "",
    ]
    for result in results:
        lines.extend(
            [
                f"## {result['scenario']}",
                "",
                f"- Profile: `{json.dumps(result['profile'], ensure_ascii=False)}`",
                f"- Created/pool: {result['created_count']} / {result['pool_size']}",
                f"- API requests: {result['api_requests']}",
                f"- Details requests: {result['details_requests']}",
                f"- Quality gate rejected: `{result.get('quality_gate_rejected_counts') or {}}`; reasons `{result.get('quality_gate_rejected_reasons') or {}}`",
                f"- Adaptive pages used: {result['adaptive_pages_used']}",
                f"- Pagination stop reasons: `{result['pagination_stop_reasons']}`",
                f"- Localization fallback: {result['localization_fallback_count']} "
                f"(original {result['overview_fallback_original_language_count']}, "
                f"en {result['overview_fallback_en_count']}, "
                f"missing {result['missing_overview_after_fallback']})",
                f"- Preference compatibility: conflicts {result.get('preference_conflict_count')}; "
                f"warnings {result.get('preference_warning_count')}; "
                f"codes `{result.get('preference_conflict_codes') or []}`; "
                f"auto fix {result.get('auto_fix_applied')}",
                f"- Elapsed ms: {result['elapsed_ms']}",
                f"- Country plan: `{result['country_plan']}`",
                f"- Country actual: `{result['country_actual']}`",
                f"- Country hit rate: {result['country_hit_rate']}",
                f"- Country leakage: {result['country_leakage_count']} ({result['country_leakage_rate']})",
                f"- Wrong country: {result['wrong_country_count']}",
                f"- Requests unique/total: {result['requests_unique']} / {result['requests_total']}",
                f"- Requests without country: {result['requests_without_country']}",
                f"- Duplicate requests skipped: {result['duplicate_requests_skipped']}",
                f"- Planned media: `{result['planned_counts'].get('media_type', {})}`",
                f"- Actual media: `{result['actual_counts'].get('media_type', {})}`",
                f"- Planned origin: `{result['planned_counts'].get('origin', {})}`",
                f"- Actual origin: `{result['actual_counts'].get('origin', {})}`",
                f"- Fallbacks: `{result['top_fallback_counts']}`",
                f"- Fallback share: {result['fallback_share']}",
                f"- Future rejected: {result['rejected_future_count']}",
                f"- Warnings: `{result['warnings']}`",
                "",
            ]
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run isolated onboarding pool rebuild scenarios.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--mock", action="store_true", help="Use deterministic in-process TMDb mock.")
    mode.add_argument("--live", action="store_true", help="Use live TMDb API credentials from env/.env.local.")
    parser.add_argument("--all", action="store_true", help="Run all built-in scenarios.")
    parser.add_argument("--scenario", choices=sorted(SCENARIOS), help="Run one built-in scenario.")
    parser.add_argument("--require-live", action="store_true", help="Fail if live mode has no TMDb credentials.")
    parser.add_argument("--output", type=Path, help="Markdown report path.")
    parser.add_argument("--json-output", type=Path, help="JSON report path.")
    parser.add_argument("--tmp-root", type=Path, help="Directory for isolated SQLite databases.")
    args = parser.parse_args()

    if not args.all and not args.scenario:
        parser.error("Pass --all or --scenario.")

    credentials_present = _credentials_available()
    if args.live and args.require_live and not credentials_present:
        print("TMDb credentials missing; live scenarios were not started.", file=sys.stderr)
        return 2

    names = sorted(SCENARIOS) if args.all else [args.scenario]
    tmp_root = args.tmp_root or Path(tempfile.mkdtemp(prefix="watchbane-onboarding-pool-"))
    tmp_root.mkdir(parents=True, exist_ok=True)
    results = [run_scenario(name, SCENARIOS[name], live=args.live, tmp_root=tmp_root) for name in names]

    payload = {
        "mode": "live" if args.live else "mock",
        "tmdb_credentials_present": credentials_present,
        "tmp_root": str(tmp_root),
        "results": results,
    }
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(_markdown(results, live=args.live, credentials_present=credentials_present), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

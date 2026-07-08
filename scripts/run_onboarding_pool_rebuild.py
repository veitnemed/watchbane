"""Run onboarding candidate-pool scenarios in an isolated SQLite database.

Examples:
    py scripts/run_onboarding_pool_rebuild.py --mock --all --output docs/onboarding_pool_mock_report.md
    py scripts/run_onboarding_pool_rebuild.py --live --all --require-live --output docs/onboarding_pool_live_report.md
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

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from apis import tmdb_api
from candidates.onboarding import autofill
from candidates.onboarding.autofill import MEDIA_MOVIE, MEDIA_TV, OnboardingTasteProfile


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


SCENARIOS: dict[str, dict[str, Any]] = {
    "ru-balanced": {
        "ui_language": "ru",
        "media_preference": "both",
        "release_preference": "mixed",
        "vibe_preference": "mixed",
        "origin_preference": "mixed",
    },
    "ru-domestic-movie-classic-light": {
        "ui_language": "ru",
        "media_preference": "movie",
        "release_preference": "classic",
        "vibe_preference": "light",
        "origin_preference": "domestic",
    },
    "en-tv-new-dark": {
        "ui_language": "en",
        "media_preference": "tv",
        "release_preference": "new",
        "vibe_preference": "dark",
        "origin_preference": None,
    },
}


class MockTmdbClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def movie_genres(self, language: str = "en") -> list[dict[str, Any]]:
        del language
        return list(MOVIE_GENRES)

    def tv_genres(self, language: str = "en") -> list[dict[str, Any]]:
        del language
        return list(TV_GENRES)

    def discover(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((endpoint, dict(params)))
        media_type = MEDIA_MOVIE if endpoint == "/discover/movie" else MEDIA_TV
        call_index = len(self.calls)
        year = int(params.get("primary_release_year") or params.get("first_air_date_year") or 2024)
        genre_text = str(params.get("with_genres") or "")
        genre_ids = [int(item) for item in genre_text.split("|") if item.isdigit()]
        if not genre_ids:
            genre_ids = [35] if media_type == MEDIA_MOVIE else [18]
        results = []
        for index in range(20):
            tmdb_id = call_index * 1000 + index
            if media_type == MEDIA_MOVIE:
                results.append(
                    {
                        "id": tmdb_id,
                        "title": f"Mock Movie {tmdb_id}",
                        "original_title": f"Mock Movie {tmdb_id}",
                        "release_date": f"{year}-01-01",
                        "poster_path": f"/movie{tmdb_id}.jpg",
                        "overview": "Mock overview",
                        "genre_ids": genre_ids,
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
                        "name": f"Mock Series {tmdb_id}",
                        "original_name": f"Mock Series {tmdb_id}",
                        "first_air_date": f"{year}-01-01",
                        "origin_country": ["RU"] if params.get("with_origin_country") == "RU" else ["US"],
                        "poster_path": f"/series{tmdb_id}.jpg",
                        "overview": "Mock overview",
                        "genre_ids": genre_ids,
                        "vote_average": 7.1,
                        "vote_count": 500,
                        "popularity": 40,
                        "original_language": params.get("with_original_language") or "en",
                    }
                )
        return {"results": results, "total_pages": 1}


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
    return {
        "scenario": name,
        "mode": "live" if live else "mock",
        "db_path": str(db_path),
        "profile": profile.normalized().as_repository_dict(),
        "ok": result.ok,
        "created_count": result.created_count,
        "pool_size": result.pool_size,
        "api_requests": result.api_requests,
        "elapsed_ms": elapsed_ms,
        "planned_counts": result.planned_counts,
        "actual_counts": result.actual_counts,
        "warnings": result.warnings,
        "rejected_future_count": result.rejected_future_count,
        "top_fallback_counts": result.actual_counts.get("fallback", {}),
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
                f"- Elapsed ms: {result['elapsed_ms']}",
                f"- Planned media: `{result['planned_counts'].get('media_type', {})}`",
                f"- Actual media: `{result['actual_counts'].get('media_type', {})}`",
                f"- Planned origin: `{result['planned_counts'].get('origin', {})}`",
                f"- Actual origin: `{result['actual_counts'].get('origin', {})}`",
                f"- Fallbacks: `{result['top_fallback_counts']}`",
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

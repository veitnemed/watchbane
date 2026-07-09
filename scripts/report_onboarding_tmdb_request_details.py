"""Generate a token-safe live TMDb request/detail report for onboarding autofill."""

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
from scripts.run_onboarding_pool_rebuild import SCENARIOS


def _safe_params(params: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in params.items()
        if "token" not in str(key).casefold() and "api_key" not in str(key).casefold()
    }


def _year(result: dict[str, Any], media_type: str) -> int | None:
    date_value = result.get("release_date") if media_type == MEDIA_MOVIE else result.get("first_air_date")
    return tmdb_api.get_year(date_value)


def _title(result: dict[str, Any], media_type: str) -> str:
    if media_type == MEDIA_MOVIE:
        return str(result.get("title") or result.get("original_title") or "").strip()
    return str(result.get("name") or result.get("original_name") or "").strip()


def _countries(result: dict[str, Any]) -> list[str]:
    values = result.get("origin_country") or []
    if isinstance(values, str):
        values = [values]
    return [str(value).strip().upper() for value in values if str(value).strip()]


def _genre_names(result: dict[str, Any], genre_lookup: dict[int, str]) -> list[str]:
    names: list[str] = []
    for genre_id in result.get("genre_ids") or []:
        try:
            name = genre_lookup.get(int(genre_id))
        except (TypeError, ValueError):
            name = None
        if name:
            names.append(name)
    return names


def _requested_year(params: dict[str, Any]) -> int | None:
    value = params.get("primary_release_year") or params.get("first_air_date_year")
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _fit_flags(result: dict[str, Any], endpoint: str, params: dict[str, Any], genre_lookup: dict[int, str]) -> dict[str, Any]:
    media_type = MEDIA_MOVIE if endpoint == "/discover/movie" else MEDIA_TV
    year = _year(result, media_type)
    requested_year = _requested_year(params)
    genre_filter = {
        int(item)
        for item in str(params.get("with_genres") or "").replace(",", "|").split("|")
        if item.isdigit()
    }
    result_genres = {
        int(item)
        for item in result.get("genre_ids") or []
        if str(item).strip().lstrip("-").isdigit()
    }
    countries = _countries(result)
    requested_language = str(params.get("with_original_language") or "").strip().casefold()
    flags = {
        "year_match": requested_year is None or year == requested_year,
        "genre_match": not genre_filter or bool(result_genres & genre_filter),
        "origin_country_match": params.get("with_origin_country") != "RU" or "RU" in countries,
        "language_match": not requested_language or str(result.get("original_language") or "").strip().casefold() == requested_language,
        "vote_count_match": int(result.get("vote_count") or 0) >= int(params.get("vote_count.gte") or 0),
        "has_poster": bool(result.get("poster_path")),
        "genres": _genre_names(result, genre_lookup),
    }
    hard_keys = ("origin_country_match", "language_match", "has_poster")
    soft_keys = ("year_match", "genre_match", "vote_count_match")
    flags["hard_fit"] = all(bool(flags[key]) for key in hard_keys)
    flags["soft_fit"] = all(bool(flags[key]) for key in soft_keys)
    flags["fit_score"] = round(
        sum(1 for key in (*hard_keys, *soft_keys) if bool(flags[key])) / 6,
        3,
    )
    return flags


class RecordingTmdbClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self._movie_genres: list[dict[str, Any]] | None = None
        self._tv_genres: list[dict[str, Any]] | None = None

    def movie_genres(self, language: str = "en") -> list[dict[str, Any]]:
        if self._movie_genres is None:
            self._movie_genres = tmdb_api.get_movie_genre_list(language=language)
        return list(self._movie_genres)

    def tv_genres(self, language: str = "en") -> list[dict[str, Any]]:
        if self._tv_genres is None:
            self._tv_genres = tmdb_api.get_tv_genre_list(language=language)
        return list(self._tv_genres)

    def discover(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        payload = tmdb_api.tmdb_get(endpoint, params=params)
        media_type = MEDIA_MOVIE if endpoint == "/discover/movie" else MEDIA_TV
        genre_lookup = {
            int(item["id"]): str(item["name"])
            for item in (self.movie_genres("en") if media_type == MEDIA_MOVIE else self.tv_genres("en"))
            if item.get("id") not in (None, "") and item.get("name")
        }
        results = payload.get("results") if isinstance(payload, dict) else []
        rows = []
        for rank, result in enumerate(results if isinstance(results, list) else [], start=1):
            fit = _fit_flags(result, endpoint, params, genre_lookup)
            rows.append(
                {
                    "rank": rank,
                    "tmdb_id": result.get("id"),
                    "title": _title(result, media_type),
                    "country": _countries(result),
                    "year": _year(result, media_type),
                    "genres": fit.pop("genres"),
                    "vote_average": result.get("vote_average"),
                    "vote_count": result.get("vote_count"),
                    "popularity": result.get("popularity"),
                    "original_language": result.get("original_language"),
                    "fit": fit,
                }
            )
        fit_counter = Counter()
        for row in rows[:20]:
            fit_counter["hard_fit"] += int(bool(row["fit"].get("hard_fit")))
            fit_counter["soft_fit"] += int(bool(row["fit"].get("soft_fit")))
            fit_counter["full_fit"] += int(bool(row["fit"].get("hard_fit")) and bool(row["fit"].get("soft_fit")))
        self.calls.append(
            {
                "request_index": len(self.calls) + 1,
                "endpoint": endpoint,
                "params": _safe_params(params),
                "total_pages": payload.get("total_pages") if isinstance(payload, dict) else None,
                "total_results": payload.get("total_results") if isinstance(payload, dict) else None,
                "top20_fit": {
                    "hard_fit": f"{fit_counter['hard_fit']}/{min(len(rows), 20)}",
                    "soft_fit": f"{fit_counter['soft_fit']}/{min(len(rows), 20)}",
                    "full_fit": f"{fit_counter['full_fit']}/{min(len(rows), 20)}",
                },
                "results": rows[:20],
            }
        )
        return payload


def _final_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sorted_candidates = sorted(candidates, key=lambda item: float(item.get("candidate_score") or 0), reverse=True)
    rows = []
    for rank, candidate in enumerate(sorted_candidates, start=1):
        rows.append(
            {
                "final_rank": rank,
                "title": candidate.get("title"),
                "media_type": candidate.get("media_type"),
                "country": candidate.get("country_codes") or candidate.get("countries"),
                "year": candidate.get("year"),
                "genres": candidate.get("genres"),
                "vote_average": candidate.get("tmdb_score"),
                "vote_count": candidate.get("tmdb_votes"),
                "candidate_score": candidate.get("candidate_score"),
                "source_stage": candidate.get("source_stage"),
                "origin_bucket": candidate.get("origin_bucket"),
                "source_bucket_id": candidate.get("source_bucket_id"),
            }
        )
    return rows


def _markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# TMDb Onboarding Request Detail Report",
        "",
        f"- Generated: {payload['generated_at']}",
        f"- Strategy: `{payload['strategy']}`",
        f"- Mode: live TMDb, isolated SQLite",
        f"- Token printed: no",
        "",
    ]
    for scenario in payload["scenarios"]:
        lines.extend(
            [
                f"## Scenario: {scenario['scenario']}",
                "",
                f"- Profile: `{json.dumps(scenario['profile'], ensure_ascii=False)}`",
                f"- Created: {scenario['created']} / {scenario['target']}",
                f"- Requests: {scenario['api_requests']}",
                f"- Planned media: `{scenario['planned_counts'].get('media_type', {})}`",
                f"- Actual media: `{scenario['actual_counts'].get('media_type', {})}`",
                f"- Planned origin: `{scenario['planned_counts'].get('origin', {})}`",
                f"- Actual origin: `{scenario['actual_counts'].get('origin', {})}`",
                f"- Source stats: `{scenario['source_stats']}`",
                f"- Warnings: `{scenario['warnings']}`",
                "",
                "### Final Ranked Pool",
                "",
                "| Rank | Title | Type | Country | Year | Genres | Votes | Score | Source |",
                "| ---: | --- | --- | --- | ---: | --- | ---: | ---: | --- |",
            ]
        )
        for row in scenario["final_ranked_candidates"]:
            lines.append(
                "| {rank} | {title} | {media} | {country} | {year} | {genres} | {votes} | {score} | {source} |".format(
                    rank=row["final_rank"],
                    title=str(row["title"] or "").replace("|", "/"),
                    media=row["media_type"],
                    country=", ".join(row["country"] or []),
                    year=row["year"] or "",
                    genres=", ".join(row["genres"] or []).replace("|", "/"),
                    votes=row["vote_count"] or 0,
                    score=row["candidate_score"] or 0,
                    source=row["source_stage"],
                )
            )
        lines.extend(["", "### TMDb Requests", ""])
        for request in scenario["tmdb_requests"]:
            lines.extend(
                [
                    f"#### Request {request['request_index']}: `{request['endpoint']}`",
                    "",
                    f"- Params: `{json.dumps(request['params'], ensure_ascii=False, sort_keys=True)}`",
                    f"- Total results/pages: {request['total_results']} / {request['total_pages']}",
                    f"- Top-20 hard/soft/full fit: `{request['top20_fit']}`",
                    "",
                    "| TMDb rank | Title | Country | Year | Genres | Votes | Avg | Lang | Fit |",
                    "| ---: | --- | --- | ---: | --- | ---: | ---: | --- | --- |",
                ]
            )
            for row in request["results"]:
                fit = row["fit"]
                lines.append(
                    "| {rank} | {title} | {country} | {year} | {genres} | {votes} | {avg} | {lang} | hard={hard}, soft={soft}, score={score} |".format(
                        rank=row["rank"],
                        title=str(row["title"] or "").replace("|", "/"),
                        country=", ".join(row["country"] or []),
                        year=row["year"] or "",
                        genres=", ".join(row["genres"] or []).replace("|", "/"),
                        votes=row["vote_count"] or 0,
                        avg=row["vote_average"] or "",
                        lang=row["original_language"] or "",
                        hard=fit.get("hard_fit"),
                        soft=fit.get("soft_fit"),
                        score=fit.get("fit_score"),
                    )
                )
            lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strategy", choices=autofill.SUPPORTED_AUTOFILL_STRATEGIES, default=autofill.DEFAULT_AUTOFILL_STRATEGY)
    parser.add_argument("--scenario", choices=sorted(SCENARIOS), action="append", help="Scenario to run. Defaults to all.")
    parser.add_argument("--json-output", type=Path, default=Path("logs/reports/onboarding_tmdb_request_detail_2026-07-09.json"))
    parser.add_argument("--output", type=Path, default=Path("docs/nightly/onboarding_tmdb_request_detail_2026-07-09.md"))
    parser.add_argument("--tmp-root", type=Path, default=None)
    args = parser.parse_args()

    try:
        tmdb_api.load_tmdb_credentials()
    except Exception as error:
        print(f"TMDb credentials unavailable: {error}", file=sys.stderr)
        return 2

    tmp_root = args.tmp_root or Path(tempfile.mkdtemp(prefix="watchbane-tmdb-request-detail-"))
    tmp_root.mkdir(parents=True, exist_ok=True)
    scenario_names = args.scenario or sorted(SCENARIOS)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "strategy": args.strategy,
        "tmp_root": str(tmp_root),
        "scenarios": [],
    }
    for scenario_name in scenario_names:
        client = RecordingTmdbClient()
        profile = OnboardingTasteProfile(**SCENARIOS[scenario_name])
        db_path = tmp_root / f"{args.strategy}_{scenario_name}.sqlite3"
        result = autofill.run_onboarding_autofill(
            profile,
            client=client,
            path=db_path,
            current_year=datetime.now(timezone.utc).year,
            strategy=args.strategy,
        )
        payload["scenarios"].append(
            {
                "scenario": scenario_name,
                "profile": profile.normalized().as_repository_dict(),
                "target": autofill.STARTER_POOL_TARGET,
                "created": result.created_count,
                "pool_size": result.pool_size,
                "api_requests": result.api_requests,
                "planned_counts": result.planned_counts,
                "actual_counts": result.actual_counts,
                "source_stats": result.source_stats,
                "rejection_counts": result.rejection_counts,
                "warnings": result.warnings,
                "tmdb_requests": client.calls,
                "final_ranked_candidates": _final_candidates(result.candidates),
            }
        )
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(_markdown(payload), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "json_output": str(args.json_output), "scenarios": scenario_names}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

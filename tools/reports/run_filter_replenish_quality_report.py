"""Run mocked quality scenarios for filter-driven candidate replenish."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from candidates.replenish.filter_discover import (  # noqa: E402
    discover_params_have_broad_origin_fallback,
    discover_params_have_vote_rating_filters,
)
from candidates.replenish.filter_intent import FilterReplenishIntent  # noqa: E402
from candidates.replenish.filter_replenisher import replenish_candidates_for_filters  # noqa: E402
from tests.fixtures.filter_replenish_tmdb import build_mock_tmdb_client  # noqa: E402


DEFAULT_MD_OUTPUT = Path("data/reports/candidates/replenish/mock_filter_replenish_quality.md")
DEFAULT_JSON_OUTPUT = Path("data/reports/candidates/replenish/mock_filter_replenish_quality.json")

SCENARIOS: dict[str, dict[str, Any]] = {
    "ru_dark_tv": {
        "fixture": "ru_dark_tv_enough",
        "label": "A. RU dark TV",
        "intent": {
            "countries": ["RU"],
            "media_type": "tv",
            "animation_mode": "live_action_only",
            "vibe": "dark",
            "include_genres": ["Drama", "Crime"],
            "target_add_count": 30,
        },
        "expected_saved_count": 30,
    },
    "anime_jp": {
        "fixture": "anime_jp_enough",
        "label": "B. Anime JP",
        "intent": {
            "preset_id": "anime",
            "countries": ["JP"],
            "media_type": "both",
            "animation_mode": "animation_only",
            "target_add_count": 30,
        },
        "expected_saved_count": 30,
    },
    "k_drama_kr": {
        "fixture": "k_drama_kr_live_tv",
        "label": "C. K-drama KR",
        "intent": {
            "preset_id": "k_drama",
            "countries": ["KR"],
            "media_type": "tv",
            "animation_mode": "live_action_only",
            "genre_groups": ["drama", "romance"],
            "target_add_count": 30,
        },
        "expected_saved_count": 30,
    },
    "us_gb_new_movies": {
        "fixture": "us_gb_new_movies_balanced",
        "label": "D. US/GB new movies",
        "intent": {
            "countries": ["US", "GB"],
            "media_type": "movie",
            "release_preference": "new",
            "target_add_count": 30,
        },
        "expected_saved_count": 30,
    },
    "sparse_tr": {
        "fixture": "sparse_tr_underfilled",
        "label": "E. Sparse TR",
        "intent": {
            "countries": ["TR"],
            "media_type": "tv",
            "target_add_count": 30,
        },
        "expected_saved_count": 5,
    },
    "duplicate_heavy": {
        "fixture": "duplicate_heavy",
        "label": "F. Duplicate-heavy",
        "intent": {
            "countries": ["US"],
            "media_type": "movie",
            "target_add_count": 30,
        },
        "expected_saved_count": 14,
    },
}


def _rate(numerator: int | float, denominator: int | float) -> float:
    if denominator <= 0:
        return 1.0
    return round(float(numerator) / float(denominator), 4)


def _candidate_country_match(candidate: dict[str, Any], expected: set[str]) -> bool:
    if not expected:
        return True
    countries = {
        str(value or "").strip().upper()
        for value in (
            list(candidate.get("country_codes") or [])
            + list(candidate.get("countries") or [])
            + list(candidate.get("origin_country") or [])
        )
        if str(value or "").strip()
    }
    return bool(countries & expected)


def _candidate_media_match(candidate: dict[str, Any], expected_media: str | None) -> bool:
    if expected_media in (None, "", "both"):
        return str(candidate.get("media_type") or "") in {"movie", "tv"}
    return str(candidate.get("media_type") or "") == expected_media


def _candidate_animation_match(candidate: dict[str, Any], animation_mode: str) -> bool:
    genre_ids = {int(value) for value in candidate.get("genre_ids") or [] if str(value).isdigit()}
    if animation_mode == "animation_only":
        return 16 in genre_ids
    if animation_mode == "live_action_only":
        return 16 not in genre_ids
    return True


def _guardrail_counts(samples: list[dict[str, Any]], expected_countries: set[str]) -> tuple[int, int]:
    vote_rating = 0
    broad_origin = 0
    for params in samples:
        if discover_params_have_vote_rating_filters(params):
            vote_rating += 1
        if discover_params_have_broad_origin_fallback(params):
            broad_origin += 1
        if expected_countries and params.get("with_origin_country") not in expected_countries:
            broad_origin += 1
    return vote_rating, broad_origin


def run_mock_scenario(name: str) -> dict[str, Any]:
    config = SCENARIOS[name]
    intent = FilterReplenishIntent.from_dict(config["intent"])
    client = build_mock_tmdb_client(config["fixture"])
    result = replenish_candidates_for_filters(
        intent,
        tmdb_client=client,
        dry_run=True,
    )
    candidates = list(result.get("candidates") or [])
    expected_countries = set(intent.countries)
    expected_media = intent.media_type
    animation_mode = intent.animation_mode
    duplicate_ids = len(candidates) - len({(item.get("media_type"), item.get("tmdb_id")) for item in candidates})
    vote_violations, broad_origin_count = _guardrail_counts(
        list(result.get("discover_params_sample") or []),
        expected_countries,
    )
    country_matches = sum(1 for candidate in candidates if _candidate_country_match(candidate, expected_countries))
    media_matches = sum(1 for candidate in candidates if _candidate_media_match(candidate, expected_media))
    animation_matches = sum(1 for candidate in candidates if _candidate_animation_match(candidate, animation_mode))
    selected_tmdb_ids = {int(candidate.get("tmdb_id")) for candidate in candidates if candidate.get("tmdb_id") is not None}
    watched_leak_count = len(selected_tmdb_ids & set(client.scenario.watched_tmdb_ids))
    existing_pool_duplicate_leak_count = duplicate_ids + len(selected_tmdb_ids & set(client.scenario.existing_tmdb_ids))
    requested_count = int(result.get("requested_count") or 0)
    saved_count = int(result.get("created_count") or 0)
    raw_seen_count = int(result.get("raw_seen_count") or 0)
    duplicate_count = int(result.get("duplicate_count") or 0)

    return {
        "scenario": name,
        "label": config["label"],
        "ok": bool(result.get("ok")),
        "requested_count": requested_count,
        "saved_count": saved_count,
        "expected_saved_count": int(config["expected_saved_count"]),
        "fill_rate": _rate(saved_count, requested_count),
        "raw_seen_count": raw_seen_count,
        "duplicate_count": duplicate_count,
        "duplicate_rate": _rate(duplicate_count, raw_seen_count),
        "country_match_rate": _rate(country_matches, len(candidates)),
        "media_match_rate": _rate(media_matches, len(candidates)),
        "animation_match_rate": _rate(animation_matches, len(candidates)),
        "api_requests": int(result.get("api_requests") or 0),
        "details_requests": int(result.get("details_requests") or 0),
        "no_vote_rating_filter_violation_count": vote_violations,
        "broad_origin_fallback_count": broad_origin_count,
        "watched_leak_count": watched_leak_count,
        "existing_pool_duplicate_leak_count": existing_pool_duplicate_leak_count,
    }


def build_quality_report(scenario_names: list[str]) -> dict[str, Any]:
    rows = [run_mock_scenario(name) for name in scenario_names]
    return {
        "scenario_count": len(rows),
        "rows": rows,
        "summary": {
            "total_requested": sum(row["requested_count"] for row in rows),
            "total_saved": sum(row["saved_count"] for row in rows),
            "total_duplicates": sum(row["duplicate_count"] for row in rows),
            "guardrail_violations": sum(
                row["no_vote_rating_filter_violation_count"] + row["broad_origin_fallback_count"]
                for row in rows
            ),
            "watched_leaks": sum(row["watched_leak_count"] for row in rows),
            "existing_pool_duplicate_leaks": sum(row["existing_pool_duplicate_leak_count"] for row in rows),
        },
    }


def markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# Mock Filter Replenish Quality Report",
        "",
        f"- scenario_count: {report['scenario_count']}",
        f"- total_requested: {report['summary']['total_requested']}",
        f"- total_saved: {report['summary']['total_saved']}",
        f"- total_duplicates: {report['summary']['total_duplicates']}",
        f"- guardrail_violations: {report['summary']['guardrail_violations']}",
        "",
        "| Scenario | Saved | Fill rate | Duplicates | Country | Media | Animation | API | Details | Guardrails |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in report["rows"]:
        guardrails = row["no_vote_rating_filter_violation_count"] + row["broad_origin_fallback_count"]
        lines.append(
            "| {label} | {saved_count}/{requested_count} | {fill_rate:.2f} | {duplicate_count} | "
            "{country_match_rate:.2f} | {media_match_rate:.2f} | {animation_match_rate:.2f} | "
            "{api_requests} | {details_requests} | {guardrails} |".format(
                guardrails=guardrails,
                **row,
            )
        )
    return "\n".join(lines) + "\n"


def write_quality_report(report: dict[str, Any], *, output: Path, json_output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    json_output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(markdown_report(report), encoding="utf-8")
    json_output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mock", action="store_true", help="Run mocked scenarios only.")
    parser.add_argument("--all", action="store_true", help="Run all mocked scenarios.")
    parser.add_argument("--scenario", choices=sorted(SCENARIOS), help="Run one mocked scenario.")
    parser.add_argument("--output", type=Path, default=DEFAULT_MD_OUTPUT)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.mock:
        raise SystemExit("Only --mock mode is supported by this report script.")
    if args.all:
        names = list(SCENARIOS)
    elif args.scenario:
        names = [args.scenario]
    else:
        raise SystemExit("Use --all or --scenario <name>.")
    report = build_quality_report(names)
    write_quality_report(report, output=args.output, json_output=args.json_output)
    print(markdown_report(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

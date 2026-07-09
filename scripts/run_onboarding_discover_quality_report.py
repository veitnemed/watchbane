"""Generate a detailed live/mock TMDb Discover quality report for onboarding."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import date, datetime, timezone
import json
from pathlib import Path
from statistics import median
import sys
import tempfile
from time import perf_counter
from typing import Any
from urllib.parse import urlencode

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from apis import tmdb_api
from candidates.onboarding import autofill
from candidates.onboarding.autofill import OnboardingTasteProfile
from scripts.run_onboarding_pool_rebuild import (
    MockTmdbClient,
    SCENARIOS,
    _country_metrics,
    _credentials_available,
    _fallback_share,
    _request_metrics,
)
from storage.sqlite.onboarding_repository import load_autofill_request_audits


SCENARIO_ORDER = (
    "ru-countries-us-only",
    "ru-countries-ru-only",
    "ru-countries-all-five",
    "ru-foreign-new-movies-us-gb",
    "ru-foreign-new-tv-us-gb",
    "ru-mixed-ru-us",
    "ru-manual-us-kr",
    "ru-manual-jp-kr",
    "dark-new-tv-us-gb",
    "light-new-movies-us-gb",
    "classic-movies-fr-it",
    "en-country-pair-us-gb",
)


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _short_json(value: Any, *, max_len: int = 260) -> str:
    text = _json(value)
    if len(text) <= max_len:
        return text
    return f"{text[: max_len - 1]}..."


def _discover_url(endpoint: str, params: dict[str, Any]) -> str:
    query = urlencode(params, doseq=True)
    return f"{endpoint}?{query}" if query else endpoint


def _result_title(item: dict[str, Any]) -> str:
    return str(item.get("title") or item.get("name") or item.get("original_title") or item.get("original_name") or "")


def _result_date(item: dict[str, Any]) -> str:
    return str(item.get("release_date") or item.get("first_air_date") or "")


def _result_sample(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": item.get("id"),
        "title": _result_title(item),
        "date": _result_date(item),
        "origin_country": item.get("origin_country") or [],
        "original_language": item.get("original_language"),
        "vote_average": item.get("vote_average"),
        "vote_count": item.get("vote_count"),
        "popularity": item.get("popularity"),
    }


class InstrumentedTmdbClient:
    def __init__(self, *, live: bool) -> None:
        self.live = bool(live)
        self.mock = MockTmdbClient()
        self.discover_logs: list[dict[str, Any]] = []
        self.genre_logs: list[dict[str, Any]] = []

    def movie_genres(self, language: str = "en") -> list[dict[str, Any]]:
        started = perf_counter()
        try:
            genres = tmdb_api.get_movie_genre_list(language=language) if self.live else self.mock.movie_genres(language)
            self.genre_logs.append({
                "kind": "movie",
                "language": language,
                "elapsed_ms": round((perf_counter() - started) * 1000, 1),
                "count": len(genres),
                "error": None,
            })
            return genres
        except Exception as error:
            self.genre_logs.append({
                "kind": "movie",
                "language": language,
                "elapsed_ms": round((perf_counter() - started) * 1000, 1),
                "count": 0,
                "error": str(error),
            })
            raise

    def tv_genres(self, language: str = "en") -> list[dict[str, Any]]:
        started = perf_counter()
        try:
            genres = tmdb_api.get_tv_genre_list(language=language) if self.live else self.mock.tv_genres(language)
            self.genre_logs.append({
                "kind": "tv",
                "language": language,
                "elapsed_ms": round((perf_counter() - started) * 1000, 1),
                "count": len(genres),
                "error": None,
            })
            return genres
        except Exception as error:
            self.genre_logs.append({
                "kind": "tv",
                "language": language,
                "elapsed_ms": round((perf_counter() - started) * 1000, 1),
                "count": 0,
                "error": str(error),
            })
            raise

    def discover(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        request_index = len(self.discover_logs) + 1
        clean_params = dict(params)
        started = perf_counter()
        log_entry: dict[str, Any] = {
            "index": request_index,
            "endpoint": endpoint,
            "params": clean_params,
            "url": _discover_url(endpoint, clean_params),
            "elapsed_ms": 0.0,
            "returned_count": 0,
            "total_pages": None,
            "total_results": None,
            "sample": [],
            "error": None,
        }
        try:
            payload = tmdb_api.tmdb_get(endpoint, params=clean_params) if self.live else self.mock.discover(endpoint, clean_params)
            results = payload.get("results") if isinstance(payload, dict) else []
            results = results if isinstance(results, list) else []
            log_entry.update({
                "elapsed_ms": round((perf_counter() - started) * 1000, 1),
                "returned_count": len(results),
                "total_pages": payload.get("total_pages") if isinstance(payload, dict) else None,
                "total_results": payload.get("total_results") if isinstance(payload, dict) else None,
                "sample": [_result_sample(item) for item in results[:5] if isinstance(item, dict)],
            })
            return payload
        except Exception as error:
            log_entry.update({
                "elapsed_ms": round((perf_counter() - started) * 1000, 1),
                "error": str(error),
            })
            raise
        finally:
            self.discover_logs.append(log_entry)


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * percentile)))
    return round(float(ordered[index]), 1)


def _speed_stats(logs: list[dict[str, Any]], elapsed_ms: float) -> dict[str, Any]:
    values = [float(log.get("elapsed_ms") or 0.0) for log in logs]
    return {
        "elapsed_ms": round(elapsed_ms, 1),
        "elapsed_s": round(elapsed_ms / 1000, 2),
        "discover_network_ms_total": round(sum(values), 1),
        "discover_avg_ms": round(sum(values) / len(values), 1) if values else 0.0,
        "discover_p50_ms": round(float(median(values)), 1) if values else 0.0,
        "discover_p95_ms": _percentile(values, 0.95),
        "discover_max_ms": round(max(values), 1) if values else 0.0,
    }


def _number_values(candidates: list[dict[str, Any]], field_name: str) -> list[float]:
    values = []
    for candidate in candidates:
        try:
            value = candidate.get(field_name)
            if value in (None, ""):
                continue
            values.append(float(value))
        except (TypeError, ValueError):
            continue
    return values


def _avg(values: list[float]) -> float:
    return round(sum(values) / len(values), 4) if values else 0.0


def _candidate_metrics(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    media_counter = Counter(str(item.get("media_type") or "") for item in candidates)
    tv_candidates = [item for item in candidates if item.get("media_type") == "tv"]
    return {
        "media_counts": dict(media_counter),
        "avg_tmdb_score": _avg(_number_values(candidates, "tmdb_score")),
        "avg_tmdb_votes": _avg(_number_values(candidates, "tmdb_votes")),
        "avg_popularity": _avg(_number_values(candidates, "tmdb_popularity")),
        "avg_candidate_score": _avg(_number_values(candidates, "candidate_score")),
        "avg_final_score": _avg(_number_values(candidates, "final_score")),
        "poster_missing_count": sum(1 for item in candidates if item.get("poster_path") in (None, "")),
        "overview_missing_count": sum(1 for item in candidates if item.get("overview") in (None, "")),
        "tv_count": len(tv_candidates),
        "tv_with_seasons": sum(1 for item in tv_candidates if item.get("number_of_seasons") not in (None, "", 0, "0")),
        "tv_with_episodes": sum(1 for item in tv_candidates if item.get("number_of_episodes") not in (None, "", 0, "0")),
    }


def _candidate_row(candidate: dict[str, Any]) -> dict[str, Any]:
    source_query = candidate.get("source_query") if isinstance(candidate.get("source_query"), dict) else {}
    return {
        "rank": candidate.get("fetch_rank"),
        "title": candidate.get("title"),
        "year": candidate.get("year"),
        "media": candidate.get("media_type"),
        "country": candidate.get("target_country"),
        "countries": candidate.get("country_codes") or candidate.get("countries") or [],
        "language": candidate.get("original_language"),
        "tmdb_score": candidate.get("tmdb_score"),
        "tmdb_votes": candidate.get("tmdb_votes"),
        "popularity": candidate.get("tmdb_popularity"),
        "final_score": candidate.get("final_score"),
        "fallback": source_query.get("fallback"),
    }


def _top_candidates(candidates: list[dict[str, Any]], *, limit: int) -> list[dict[str, Any]]:
    ordered = sorted(
        candidates,
        key=lambda item: (
            float(item.get("final_score") or 0),
            float(item.get("tmdb_score") or 0),
            float(item.get("tmdb_votes") or 0),
        ),
        reverse=True,
    )
    return [_candidate_row(item) for item in ordered[:limit]]


def _combine_requests(audits: list[dict[str, Any]], logs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    combined = []
    log_index = 0
    for audit in audits:
        params = dict(audit.get("params") or {})
        fallback = params.pop("_fallback", None)
        log = None
        if audit.get("status") != "skipped_duplicate":
            if log_index < len(logs):
                log = logs[log_index]
            log_index += 1
        combined.append({
            "id": audit.get("id"),
            "bucket_id": audit.get("bucket_id"),
            "fallback": fallback,
            "endpoint": audit.get("endpoint"),
            "page": audit.get("page"),
            "status": audit.get("status"),
            "accepted_count": audit.get("accepted_count"),
            "rejected_count": audit.get("rejected_count"),
            "params": params,
            "url": log.get("url") if isinstance(log, dict) else _discover_url(str(audit.get("endpoint") or ""), params),
            "elapsed_ms": log.get("elapsed_ms") if isinstance(log, dict) else None,
            "returned_count": log.get("returned_count") if isinstance(log, dict) else None,
            "total_pages": log.get("total_pages") if isinstance(log, dict) else None,
            "total_results": log.get("total_results") if isinstance(log, dict) else None,
            "sample": log.get("sample") if isinstance(log, dict) else [],
            "error": audit.get("error_text") or (log.get("error") if isinstance(log, dict) else None),
        })
    return combined


def run_scenario(name: str, profile_data: dict[str, Any], *, live: bool, tmp_root: Path, current_year: int, sample_limit: int) -> dict[str, Any]:
    db_path = tmp_root / f"{name}.sqlite3"
    profile = OnboardingTasteProfile(**profile_data)
    client = InstrumentedTmdbClient(live=live)
    started_at = datetime.now(timezone.utc)
    start_counter = perf_counter()
    result = autofill.run_onboarding_autofill(
        profile,
        client=client,
        path=db_path,
        current_year=current_year,
    )
    elapsed_ms = (perf_counter() - start_counter) * 1000
    finished_at = datetime.now(timezone.utc)
    candidates = result.candidates
    normalized_profile = profile.normalized().as_repository_dict()
    audits = load_autofill_request_audits(result.profile_id, path=db_path)
    request_rows = _combine_requests(audits, client.discover_logs)
    request_metrics = _request_metrics(audits)
    country_metrics = _country_metrics(candidates, normalized_profile)
    speed = _speed_stats(client.discover_logs, elapsed_ms)
    candidate_metrics = _candidate_metrics(candidates)
    return {
        "scenario": name,
        "mode": "live" if live else "mock",
        "db_path": str(db_path),
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "profile": normalized_profile,
        "ok": result.ok,
        "created_count": result.created_count,
        "pool_size": result.pool_size,
        "api_requests": result.api_requests,
        "planned_counts": result.planned_counts,
        "actual_counts": result.actual_counts,
        "warnings": result.warnings,
        "rejected_future_count": result.rejected_future_count,
        "duplicate_requests_skipped": result.duplicate_requests_skipped,
        "fallback_share": _fallback_share(result.actual_counts, result.created_count),
        "fallback_counts": result.actual_counts.get("fallback", {}),
        "genre_requests": client.genre_logs,
        "discover_requests": request_rows,
        "top_candidates": _top_candidates(candidates, limit=sample_limit),
        **speed,
        **request_metrics,
        **country_metrics,
        **candidate_metrics,
    }


def _format_count_map(value: dict[str, Any]) -> str:
    if not value:
        return "-"
    return ", ".join(f"{key}: {count}" for key, count in value.items())


def _sample_text(sample: list[dict[str, Any]]) -> str:
    if not sample:
        return "-"
    chunks = []
    for item in sample[:3]:
        title = item.get("title") or "?"
        year = str(item.get("date") or "")[:4]
        country = ",".join(str(value) for value in item.get("origin_country") or [])
        score = item.get("vote_average")
        votes = item.get("vote_count")
        chunks.append(f"{title} ({year}, {country}, {score}/{votes})")
    return "; ".join(chunks)


def _markdown(results: list[dict[str, Any]], *, live: bool, credentials_present: bool, tmp_root: Path) -> str:
    all_request_logs = [
        request
        for result in results
        for request in result.get("discover_requests", [])
        if request.get("status") != "skipped_duplicate"
    ]
    all_elapsed = [float(request.get("elapsed_ms") or 0.0) for request in all_request_logs]
    full_pool_count = sum(1 for result in results if int(result.get("created_count") or 0) >= autofill.STARTER_POOL_TARGET)
    min_country_hit = min((float(result.get("country_hit_rate") or 0.0) for result in results), default=0.0)
    total_requests = sum(int(result.get("requests_total") or 0) for result in results)
    total_candidates = sum(int(result.get("created_count") or 0) for result in results)
    tv_total = sum(int(result.get("tv_count") or 0) for result in results)
    tv_with_seasons = sum(int(result.get("tv_with_seasons") or 0) for result in results)
    lines = [
        "# Onboarding Discover Quality Report",
        "",
        f"- Дата: {date.today().isoformat()}",
        f"- Режим: {'live TMDb' if live else 'mock'}",
        f"- TMDb credentials present: {credentials_present}",
        f"- Проходов: {len(results)}",
        f"- Цель на проход: {autofill.STARTER_POOL_TARGET} кандидатов",
        f"- Временные SQLite базы: `{tmp_root}`",
        "",
        "## Короткий вывод",
        "",
        f"- Полный пул 120/120 собран в {full_pool_count} из {len(results)} проходов.",
        f"- Всего создано кандидатов: {total_candidates}.",
        f"- Всего выполнено discover-запросов: {total_requests}.",
        f"- Среднее время discover-запроса: {round(sum(all_elapsed) / len(all_elapsed), 1) if all_elapsed else 0.0} ms.",
        f"- P95 discover-запроса: {_percentile(all_elapsed, 0.95)} ms.",
        f"- Минимальный country hit rate: {min_country_hit}.",
        f"- TV candidates with seasons initially: {tv_with_seasons}/{tv_total}.",
        "",
        "Примечание по сериалам: TMDb `/discover/tv` не отдаёт `number_of_seasons` и `number_of_episodes`. "
        "Поэтому в стартовом пуле эти поля ожидаемо пустые до ленивого `/tv/{id}` details enrichment при открытии карточки.",
        "",
        "## Сводная таблица",
        "",
        "| Scenario | Created | API req | Time | Avg req | Country plan | Country actual | Media actual | Hit | Warnings |",
        "| --- | ---: | ---: | ---: | ---: | --- | --- | --- | ---: | --- |",
    ]
    for result in results:
        warnings = "; ".join(result.get("warnings") or []) or "-"
        lines.append(
            "| "
            f"`{result['scenario']}` | "
            f"{result['created_count']} | "
            f"{result['api_requests']} | "
            f"{result['elapsed_s']}s | "
            f"{result['discover_avg_ms']}ms | "
            f"{_format_count_map(result['planned_counts'].get('country', {}))} | "
            f"{_format_count_map(result.get('country_actual', {}))} | "
            f"{_format_count_map(result['actual_counts'].get('media_type', {}))} | "
            f"{result.get('country_hit_rate')} | "
            f"{warnings} |"
        )

    for result in results:
        lines.extend([
            "",
            f"## {result['scenario']}",
            "",
            f"- Profile: `{_json(result['profile'])}`",
            f"- Created/pool: {result['created_count']} / {result['pool_size']}",
            f"- API requests: {result['api_requests']}; unique/total: {result['requests_unique']} / {result['requests_total']}",
            f"- Duplicate skipped: {result['duplicate_requests_skipped']}",
            f"- Speed: total {result['elapsed_s']}s; discover avg {result['discover_avg_ms']}ms; p50 {result['discover_p50_ms']}ms; p95 {result['discover_p95_ms']}ms; max {result['discover_max_ms']}ms",
            f"- Planned media: `{_json(result['planned_counts'].get('media_type', {}))}`",
            f"- Actual media: `{_json(result['actual_counts'].get('media_type', {}))}`",
            f"- Planned country: `{_json(result['planned_counts'].get('country', {}))}`",
            f"- Actual country: `{_json(result.get('country_actual', {}))}`",
            f"- Country hit/leak/wrong: {result.get('country_hit_rate')} / {result.get('country_leakage_rate')} / {result.get('wrong_country_count')}",
            f"- Fallbacks: `{_json(result.get('fallback_counts', {}))}`; fallback share {result.get('fallback_share')}",
            f"- Avg TMDb score/votes/popularity: {result.get('avg_tmdb_score')} / {result.get('avg_tmdb_votes')} / {result.get('avg_popularity')}",
            f"- Missing poster/overview: {result.get('poster_missing_count')} / {result.get('overview_missing_count')}",
            f"- TV seasons/episodes present initially: {result.get('tv_with_seasons')}/{result.get('tv_count')} and {result.get('tv_with_episodes')}/{result.get('tv_count')}",
            f"- Warnings: `{_json(result.get('warnings') or [])}`",
            "",
            "### Top output sample",
            "",
            "| Rank | Title | Year | Media | Country | Lang | TMDb | Votes | Popularity | Final | Fallback |",
            "| ---: | --- | ---: | --- | --- | --- | ---: | ---: | ---: | ---: | --- |",
        ])
        for item in result.get("top_candidates", []):
            lines.append(
                "| "
                f"{item.get('rank')} | "
                f"{item.get('title')} | "
                f"{item.get('year')} | "
                f"{item.get('media')} | "
                f"{item.get('country')} | "
                f"{item.get('language')} | "
                f"{item.get('tmdb_score')} | "
                f"{item.get('tmdb_votes')} | "
                f"{item.get('popularity')} | "
                f"{item.get('final_score')} | "
                f"{item.get('fallback')} |"
            )

        lines.extend([
            "",
            "### Detailed Discover Requests",
            "",
        ])
        for index, request in enumerate(result.get("discover_requests", []), start=1):
            lines.extend([
                f"{index}. `{request.get('url')}`",
                f"   - bucket: `{request.get('bucket_id')}`",
                f"   - fallback/status/page: `{request.get('fallback')}` / `{request.get('status')}` / {request.get('page')}",
                f"   - accepted/rejected: {request.get('accepted_count')} / {request.get('rejected_count')}",
                f"   - speed/results: {request.get('elapsed_ms')} ms; returned {request.get('returned_count')} of total {request.get('total_results')}; pages {request.get('total_pages')}",
                f"   - params: `{_short_json(request.get('params') or {})}`",
                f"   - sample: {_sample_text(request.get('sample') or [])}",
            ])
            if request.get("error"):
                lines.append(f"   - error: `{request.get('error')}`")
            lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a detailed onboarding Discover quality report.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--live", action="store_true", help="Use live TMDb requests.")
    mode.add_argument("--mock", action="store_true", help="Use deterministic mock responses.")
    parser.add_argument("--limit", type=int, default=10, help="Number of built-in scenarios to run.")
    parser.add_argument("--all", action="store_true", help="Run all built-in report scenarios.")
    parser.add_argument("--scenario", action="append", choices=SCENARIO_ORDER, help="Run selected scenario; repeatable.")
    parser.add_argument("--require-live", action="store_true", help="Fail when --live has no credentials.")
    parser.add_argument("--current-year", type=int, default=date.today().year)
    parser.add_argument("--sample-limit", type=int, default=12, help="Top output rows per scenario.")
    parser.add_argument("--output", type=Path, default=ROOT_DIR / "docs" / "onboarding_discover_quality_report.md")
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--tmp-root", type=Path)
    args = parser.parse_args()

    credentials_present = _credentials_available()
    if args.live and args.require_live and credentials_present is False:
        print("TMDb credentials missing; live report was not started.", file=sys.stderr)
        return 2

    if args.scenario:
        scenario_names = list(dict.fromkeys(args.scenario))
    elif args.all:
        scenario_names = list(SCENARIO_ORDER)
    else:
        scenario_names = list(SCENARIO_ORDER[: max(1, int(args.limit))])

    tmp_root = args.tmp_root or Path(tempfile.mkdtemp(prefix="watchbane-discover-quality-"))
    tmp_root.mkdir(parents=True, exist_ok=True)
    results = [
        run_scenario(
            name,
            SCENARIOS[name],
            live=args.live,
            tmp_root=tmp_root,
            current_year=int(args.current_year),
            sample_limit=max(1, int(args.sample_limit)),
        )
        for name in scenario_names
    ]

    payload = {
        "mode": "live" if args.live else "mock",
        "tmdb_credentials_present": credentials_present,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tmp_root": str(tmp_root),
        "scenario_count": len(results),
        "results": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        _markdown(results, live=args.live, credentials_present=credentials_present, tmp_root=tmp_root),
        encoding="utf-8",
    )
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({
        "ok": True,
        "mode": payload["mode"],
        "scenario_count": len(results),
        "output": str(args.output),
        "json_output": str(args.json_output) if args.json_output else None,
        "created_total": sum(int(result.get("created_count") or 0) for result in results),
        "discover_requests_total": sum(int(result.get("requests_total") or 0) for result in results),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

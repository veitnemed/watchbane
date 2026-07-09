"""Benchmark FTS search: legacy full-pool intersect vs SQL pre-filter path."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from time import perf_counter

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.core.explain import explain_candidate  # noqa: E402
from app.core.filters import filter_candidates  # noqa: E402
from app.core.ranking import rank_candidates  # noqa: E402
from candidates import service as candidate_service  # noqa: E402
from candidates.search.fts_index import search_fts, search_fts_prefiltered  # noqa: E402
from candidates.search.structural_sql import build_structural_sql_filters  # noqa: E402
from storage.sqlite.candidate_query_repository import load_candidate_records_by_pool_keys  # noqa: E402
from storage.sqlite.connection import connect  # noqa: E402

DEFAULT_QUERIES = [
    "бригада",
    "метод",
    "шерлок",
    "игра престолов",
    "криминал",
    "комедия",
    "фантастика",
    "2020",
    "one piece",
    "сериал про",
]

DEFAULT_FILTER_SETS = [
    {},
    {"media_type": "tv"},
    {"year_min": 2015, "year_max": 2022},
    {"min_tmdb_score": 7.0},
]


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int(round((pct / 100.0) * (len(ordered) - 1)))))
    return round(ordered[index], 2)


def _legacy_path_ms(
    candidates: list[dict],
    criteria: dict,
    query: str,
    conn,
) -> tuple[float, int]:
    started = perf_counter()
    fts_hits = search_fts(conn, query)
    fts_keys = {pool_key for pool_key, _ in fts_hits}
    search_view = candidate_service.search_candidate_pool(candidates, criteria)
    result_count = sum(
        1
        for candidate in search_view.get("candidates") or []
        if candidate_service._candidate_pool_key(candidate) in fts_keys
    )
    elapsed_ms = round((perf_counter() - started) * 1000, 2)
    return elapsed_ms, result_count


def _sql_path_ms(criteria: dict, query: str, conn) -> tuple[float, int]:
    started = perf_counter()
    structural_clauses, structural_params = build_structural_sql_filters(criteria)
    fts_hits = search_fts_prefiltered(
        conn,
        query,
        structural_clauses=structural_clauses or None,
        structural_params=structural_params or None,
    )
    if fts_hits:
        hit_keys = [pool_key for pool_key, _ in fts_hits]
        hit_candidates = load_candidate_records_by_pool_keys(hit_keys, conn=conn)
        filtered = filter_candidates(hit_candidates, criteria)
        ranked = rank_candidates(filtered)
        for candidate in ranked:
            candidate["explanation"] = explain_candidate(candidate, criteria)
        result_count = len(ranked)
    else:
        result_count = 0
    elapsed_ms = round((perf_counter() - started) * 1000, 2)
    return elapsed_ms, result_count


def run_benchmark(
    *,
    queries: list[str],
    filter_sets: list[dict],
    repeats: int,
) -> dict:
    overview = candidate_service.get_search_overview_view()
    candidates = overview.get("candidates") or []
    pool_size = len(candidates)
    conn = connect()
    legacy_latencies: list[float] = []
    sql_latencies: list[float] = []
    cases: list[dict] = []
    try:
        for filters in filter_sets:
            criteria = candidate_service._prepare_text_search_criteria(filters)
            for query in queries:
                legacy_samples: list[float] = []
                sql_samples: list[float] = []
                legacy_count = 0
                sql_count = 0
                for _ in range(repeats):
                    legacy_ms, legacy_count = _legacy_path_ms(candidates, criteria, query, conn)
                    sql_ms, sql_count = _sql_path_ms(criteria, query, conn)
                    legacy_samples.append(legacy_ms)
                    sql_samples.append(sql_ms)
                legacy_latencies.extend(legacy_samples)
                sql_latencies.extend(sql_samples)
                cases.append(
                    {
                        "query": query,
                        "filters": filters,
                        "legacy_p50_ms": _percentile(legacy_samples, 50),
                        "sql_p50_ms": _percentile(sql_samples, 50),
                        "legacy_count": legacy_count,
                        "sql_count": sql_count,
                    }
                )
    finally:
        conn.close()

    return {
        "pool_size": pool_size,
        "repeats": repeats,
        "case_count": len(cases),
        "legacy_p50_ms": _percentile(legacy_latencies, 50),
        "legacy_p95_ms": _percentile(legacy_latencies, 95),
        "sql_p50_ms": _percentile(sql_latencies, 50),
        "sql_p95_ms": _percentile(sql_latencies, 95),
        "legacy_mean_ms": round(statistics.mean(legacy_latencies), 2) if legacy_latencies else 0.0,
        "sql_mean_ms": round(statistics.mean(sql_latencies), 2) if sql_latencies else 0.0,
        "cases": cases,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--query", action="append", dest="queries", default=None)
    args = parser.parse_args(argv)

    queries = args.queries or DEFAULT_QUERIES
    report = run_benchmark(queries=queries, filter_sets=DEFAULT_FILTER_SETS, repeats=max(1, args.repeats))
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    print(payload)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

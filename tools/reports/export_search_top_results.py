"""Export top-N local search results for manual curation/review.

Uses the exact same ranking pipeline as the desktop Candidates tab
(``get_search_overview_view`` -> ``search_candidate_pool`` -> ``sort_search_candidates``)
plus the same substring haystack for the optional ``--query`` text filter.

No TMDb requests, no ranking changes: this reads the saved candidate pool and
writes a JSON review file. ``reports/`` is git-ignored.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from candidates import service as candidate_service  # noqa: E402
from candidates.onboarding.request_log import current_git_commit  # noqa: E402
from desktop.candidates.presenters import candidate_search_text  # noqa: E402

DEFAULT_OUTPUT = ROOT_DIR / "reports" / "search" / "curation" / "search_top50_review.json"


def _as_list(value) -> list:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [item for item in value]
    if isinstance(value, str):
        text = value.strip()
        if text == "":
            return []
        if "," in text:
            return [part.strip() for part in text.split(",") if part.strip()]
        return [text]
    return [value]


def _safe_float(value):
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def build_filters(args: argparse.Namespace) -> dict:
    filters = dict(candidate_service_default_filters())
    if args.media_type:
        filters["media_type"] = args.media_type
    if args.country:
        filters["country"] = list(args.country)
    if args.year_min is not None:
        filters["year_min"] = args.year_min
    if args.year_max is not None:
        filters["year_max"] = args.year_max
    if args.include_genre:
        filters["include_genres"] = list(args.include_genre)
    if args.exclude_genre:
        filters["exclude_genres"] = list(args.exclude_genre)
    return filters


def candidate_service_default_filters() -> dict:
    from desktop.candidates.session import DEFAULT_BROWSE_FILTERS

    return DEFAULT_BROWSE_FILTERS


def rank_candidates(query: str | None, filters: dict, sort_mode: str) -> tuple[list[dict], dict]:
    overview = candidate_service.get_search_overview_view()
    if overview.get("is_empty"):
        return [], overview
    normalized_query = str(query or "").strip()
    if normalized_query and candidate_service.is_fts_search_enabled():
        search_view = candidate_service.search_candidate_pool_text(
            overview["candidates"],
            filters,
            text_query=normalized_query,
        )
    else:
        search_view = candidate_service.search_candidate_pool(overview["candidates"], filters)
    filtered = list(search_view.get("candidates") or [])
    sort_view = candidate_service.sort_search_candidates(filtered, sort_mode)
    ranked = list(sort_view.get("candidates") or [])
    if normalized_query and not candidate_service.is_fts_search_enabled():
        normalized = normalized_query.casefold()
        ranked = [
            candidate
            for candidate in ranked
            if normalized in candidate_search_text(candidate)
        ]
    return ranked, overview


def build_item(candidate: dict, rank: int) -> dict:
    tmdb_id = candidate.get("tmdb_id")
    if tmdb_id in (None, ""):
        source_query = candidate.get("source_query")
        if isinstance(source_query, dict):
            tmdb_id = source_query.get("tmdb_id")
    country_codes = _as_list(
        candidate.get("country_codes")
        or candidate.get("origin_country")
        or candidate.get("tmdb_production_countries")
    )
    genres = _as_list(candidate.get("genres_tmdb") or candidate.get("genres"))
    is_complete = None
    try:
        is_complete = not candidate_service.is_candidate_incomplete(candidate)
    except Exception:
        is_complete = None
    return {
        "rank": rank,
        "tmdb_id": tmdb_id if tmdb_id not in (None, "") else None,
        "title": candidate.get("title") or candidate.get("name") or "",
        "original_title": candidate.get("original_title") or candidate.get("original_name") or "",
        "year": candidate.get("year"),
        "country_codes": country_codes,
        "genres": genres,
        "final_score": _safe_float(candidate.get("final_score")),
        "quality_score": _safe_float(candidate.get("quality_score")),
        "text_relevance_score": _safe_float(candidate.get("text_relevance_score")),
        "combined_relevance_score": _safe_float(candidate.get("combined_relevance_score")),
        "matched_fields": list(candidate.get("matched_fields") or []),
        "is_complete": is_complete,
        "review": None,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export top-N local search results for review.")
    parser.add_argument("--query", default=None, help="Optional text query (FTS when WATCHBANE_FTS_SEARCH=1).")
    parser.add_argument("--top", type=int, default=50, help="Number of top results to export.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Output JSON path.")
    parser.add_argument("--sort-mode", default=candidate_service.DEFAULT_SEARCH_SORT_MODE)
    parser.add_argument("--media-type", default=None, help="Filter by media type (movie/tv).")
    parser.add_argument("--country", action="append", default=None, help="Country code filter (repeatable).")
    parser.add_argument("--year-min", type=int, default=None)
    parser.add_argument("--year-max", type=int, default=None)
    parser.add_argument("--include-genre", action="append", default=None, help="Include genre (repeatable).")
    parser.add_argument("--exclude-genre", action="append", default=None, help="Exclude genre (repeatable).")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    filters = build_filters(args)
    sort_mode = args.sort_mode if args.sort_mode in candidate_service.SEARCH_SORT_MODES else candidate_service.DEFAULT_SEARCH_SORT_MODE
    ranked, _overview = rank_candidates(args.query, filters, sort_mode)
    top = ranked[: max(0, args.top)]
    items = [build_item(candidate, rank) for rank, candidate in enumerate(top, start=1)]

    payload = {
        "query": args.query or "",
        "filters": filters,
        "sort_mode": sort_mode,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "git_commit": current_git_commit(),
        "count": len(items),
        "items": items,
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)

    summary = {
        "query": payload["query"],
        "count": payload["count"],
        "sort_mode": sort_mode,
        "output": str(output_path),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

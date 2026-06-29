"""CLI for building TMDb + IMDb SQL candidate pools."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from apis import imdb_sql as sql_search
from candidates.tmdb_candidate_pool import (
    build_candidate_pool,
    build_summary_lines,
    save_candidate_pool_result,
    set_progress_reporter,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build candidate_pool v1 from TMDb Discover and local IMDb SQL.")
    parser.add_argument(
        "--country",
        default="RU",
        metavar="COUNTRY",
        help="ISO-2 country code, default RU.",
    )
    parser.add_argument("--pages", type=int, default=3, help="TMDb Discover pages to scan.")
    parser.add_argument("--details-limit", type=int, default=50, help="How many top Discover results get /tv details.")
    parser.add_argument("--mode", choices=["quality", "hidden_gems"], default="quality", help="Final ranking mode.")
    parser.add_argument("--force-refresh", action="store_true", help="Ignore TMDb cache and refresh API responses.")
    parser.add_argument(
        "--imdb-db",
        default=str(sql_search.DEFAULT_DB_PATH),
        help="Path to local IMDb SQLite database.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    pages = max(1, min(args.pages, 20))
    details_limit = max(1, min(args.details_limit, 300))

    set_progress_reporter(lambda source, status: print(f"{source}: {status}"))

    result = build_candidate_pool(
        country=args.country,
        pages=pages,
        details_limit=details_limit,
        mode=args.mode,
        force_refresh=args.force_refresh,
        db_path=Path(args.imdb_db),
    )
    json_path, csv_path = save_candidate_pool_result(result)
    for line in build_summary_lines(result):
        print(line)
    print("")
    print(f"Saved JSON: {json_path}")
    print(f"Saved CSV: {csv_path}")


if __name__ == "__main__":
    main()

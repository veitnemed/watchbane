"""Backfill localized strings from TMDb Details."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dataset.migrations.tmdb_localized import (
    backfill_candidate_pool_from_tmdb,
    backfill_watched_meta_from_tmdb,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", default="watched-meta", choices=("watched-meta", "candidate-pool", "all"))
    parser.add_argument("--language", default="en", choices=("ru", "en"))
    parser.add_argument("--meta-path", default=None)
    parser.add_argument("--pool-path", default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--force-refresh", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    reports = {}
    if args.target in {"watched-meta", "all"}:
        reports["watched_meta"] = backfill_watched_meta_from_tmdb(
            meta_path=args.meta_path,
            data_language=args.language,
            dry_run=args.dry_run,
            force_refresh=args.force_refresh,
            limit=args.limit,
        )
    if args.target in {"candidate-pool", "all"}:
        reports["candidate_pool"] = backfill_candidate_pool_from_tmdb(
            pool_path=args.pool_path,
            data_language=args.language,
            dry_run=args.dry_run,
            force_refresh=args.force_refresh,
            limit=args.limit,
        )

    report = reports if args.target == "all" else next(iter(reports.values()))
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

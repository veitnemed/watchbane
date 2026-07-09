"""Aggregate precision@10 across reviewed search export JSON files."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.reports.evaluate_search_relevance import evaluate_payload


def summarize_directory(directory: Path, *, k: int = 10) -> dict:
    files = sorted(directory.glob("*.json"))
    rows: list[dict] = []
    precisions: list[float] = []
    for path in files:
        payload = json.loads(path.read_text(encoding="utf-8"))
        result = evaluate_payload(payload, k=k)
        precision_key = f"precision_at_{k}"
        precision = result.get(precision_key)
        row = {
            "file": path.name,
            "query": result.get("query") or "",
            precision_key: precision,
        }
        rows.append(row)
        if precision is not None:
            precisions.append(float(precision))

    average = sum(precisions) / len(precisions) if precisions else None
    weak = [
        row
        for row in rows
        if row.get(f"precision_at_{k}") is not None and row[f"precision_at_{k}"] < 0.5
    ]
    return {
        "directory": str(directory),
        "files": len(files),
        "reviewed_queries": len(precisions),
        f"average_precision_at_{k}": average,
        "weak_queries": weak,
        "results": rows,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Summarize reviewed search eval JSON files.")
    parser.add_argument(
        "directory",
        nargs="?",
        default="reports/search/curation",
        help="Directory with reviewed export JSON files.",
    )
    parser.add_argument("--k", type=int, default=10)
    args = parser.parse_args(argv)

    summary = summarize_directory(Path(args.directory), k=max(1, args.k))
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

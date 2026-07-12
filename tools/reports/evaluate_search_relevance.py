"""Evaluate precision@10 for manually reviewed search export JSON files."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def _precision_at_k(items: list[dict], k: int = 10) -> float | None:
    reviewed = [item for item in items[:k] if item.get("review") in {"relevant", "irrelevant"}]
    if not reviewed:
        return None
    relevant = sum(1 for item in reviewed if item.get("review") == "relevant")
    return relevant / len(reviewed)


def evaluate_payload(payload: dict, *, k: int = 10) -> dict:
    items = list(payload.get("items") or [])
    precision = _precision_at_k(items, k=k)
    reviewed_total = sum(1 for item in items if item.get("review") in {"relevant", "irrelevant"})
    relevant_total = sum(1 for item in items if item.get("review") == "relevant")
    irrelevant_total = sum(1 for item in items if item.get("review") == "irrelevant")
    missing_total = sum(1 for item in items if item.get("review") == "missing")
    return {
        "query": payload.get("query") or "",
        "sort_mode": payload.get("sort_mode"),
        "count": len(items),
        "reviewed_total": reviewed_total,
        "relevant_total": relevant_total,
        "irrelevant_total": irrelevant_total,
        "missing_total": missing_total,
        f"precision_at_{k}": precision,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate precision@K for reviewed search exports.")
    parser.add_argument("input", help="Path to search_top*_review.json")
    parser.add_argument("--k", type=int, default=10)
    args = parser.parse_args(argv)

    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    result = evaluate_payload(payload, k=max(1, args.k))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

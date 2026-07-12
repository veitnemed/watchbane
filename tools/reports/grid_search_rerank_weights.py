"""Grid search W_BM25 / W_FINAL against bootstrap calibration specs."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.reports.bootstrap_search_curation import (  # noqa: E402
    CALIBRATION_SPECS,
    build_item,
    candidate_service_default_filters,
    label_items,
    rank_candidates,
)
from scripts.reports.evaluate_search_relevance import evaluate_payload  # noqa: E402


def _eval_weights(w_bm25: float, w_final: float, *, top: int = 10) -> dict:
    import candidates.search.rerank as rerank

    rerank.W_BM25 = w_bm25
    rerank.W_FINAL = w_final
    filters = dict(candidate_service_default_filters())
    precisions: list[float] = []
    for spec in CALIBRATION_SPECS:
        ranked, _overview = rank_candidates(spec["query"], filters, "relevance")
        items = [build_item(candidate, rank) for rank, candidate in enumerate(ranked[:top], start=1)]
        items = label_items(items, spec)
        result = evaluate_payload({"query": spec["query"], "items": items}, k=10)
        precision = result.get("precision_at_10")
        if precision is not None:
            precisions.append(float(precision))
    average = sum(precisions) / len(precisions) if precisions else 0.0
    return {
        "w_bm25": w_bm25,
        "w_final": w_final,
        "average_precision_at_10": average,
        "reviewed_queries": len(precisions),
    }


def main() -> int:
    rows: list[dict] = []
    for w_bm25_int in range(3, 8):
        w_bm25 = w_bm25_int / 10.0
        w_final = round(1.0 - w_bm25, 1)
        rows.append(_eval_weights(w_bm25, w_final))
    best = max(rows, key=lambda row: row["average_precision_at_10"])
    print(json.dumps({"best": best, "grid": rows}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

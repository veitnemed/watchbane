"""Evaluate a sealed plot-search test set against one local catalog and model."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


def score(cases, ranked, known_ids, *, limit=5):
    """Keep corpus coverage distinct from ranking and avoid grading unknown hits."""
    if not 1 <= limit <= 10:
        raise ValueError("limit must be 1 to 10")
    seen = set()
    report = []
    totals: Counter = Counter()
    for case in cases:
        case_id, expectation = case["id"], case["expect"]
        if case_id in seen or expectation not in ("match", "uncertain", "no_match"):
            raise ValueError("Duplicate case ID or invalid expectation")
        seen.add(case_id)
        expected = set(case.get("full", ()))
        if bool(expected) != (expectation == "match"):
            raise ValueError("Only positive cases require one or more expected titles")
        covered = expected & known_ids
        ids = list(ranked[case_id])[:limit]
        if len(ids) != len(set(ids)) or set(ids) - known_ids:
            raise ValueError("Results contain duplicate or unknown title IDs")
        first_rank = next((i for i, item in enumerate(ids, 1) if item in covered), None)
        traps = set(case.get("traps", ()))
        totals["positive_cases"] += expectation == "match"
        totals["positive_cases_covered"] += bool(covered)
        totals["hit_1"] += first_rank == 1
        if limit != 1:
            totals[f"hit_{limit}"] += first_rank is not None
        totals["negative_no_match_cases"] += expectation == "no_match"
        totals["negative_no_match_with_cards"] += expectation == "no_match" and bool(ids)
        totals["uncertain_cases"] += expectation == "uncertain"
        totals["uncertain_cases_with_cards"] += expectation == "uncertain" and bool(ids)
        report.append({
            "id": case_id, "expect": expectation, "covered_titles": sorted(covered),
            "missing_titles": sorted(expected - known_ids), "first_full_rank": first_rank,
            "ranking": ids, "annotated_traps_returned": [item for item in ids if item in traps],
        })
    return {"counts": dict(totals), "cases": report,
            "grading_limit": "Annotated traps are not exhaustive; review unannotated evidence manually."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", required=True, type=Path)
    parser.add_argument("--sha256", required=True, help="Digest recorded before looking at the rankings")
    parser.add_argument("--catalog", required=True, type=Path)
    parser.add_argument("--model-dir", required=True, type=Path)
    parser.add_argument("--profile", required=True, type=Path, help="Dedicated disposable QA profile")
    args = parser.parse_args()
    fixture = args.cases.read_bytes()
    if hashlib.sha256(fixture).hexdigest() != args.sha256.lower():
        parser.error("The case file does not match its sealed digest")
    cases = json.loads(fixture)["cases"]
    from tools.qa.isolation import apply_isolated_data_dir
    apply_isolated_data_dir(args.profile)
    from candidates.story_service import local_story_catalog
    from candidates.story_search import StorySearch

    hybrid, _ = local_story_catalog(args.model_dir, seed_path=args.catalog)
    if not hybrid.documents:
        parser.error("The selected catalog has no searchable descriptions")
    known_ids = {doc.key for doc in hybrid.documents}
    word_search = StorySearch(hybrid.documents)
    result = {"fixture_sha256": args.sha256.lower(), "indexed_titles": len(known_ids)}
    for name, engine in (("hybrid", hybrid), ("words", word_search)):
        rankings = {
            case["id"]: [hit.document.key for hit in engine.search(case["query"]).hits]
            for case in cases
        }
        result[name] = score(cases, rankings, known_ids)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

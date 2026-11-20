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


_V2_GROUPS = ("clean", "typo", "wrong_name", "ambiguous", "near", "ood")
_ACTIONS = {"RESULTS", "CLARIFY", "NO_MATCH", "UNSUPPORTED", "ERROR"}


def score_v2(cases, ranked, known_ids, *, annotations=None, limit=5):
    """Grade retrieval mechanically and leave user-visible intent to reviewers.

    Annotations are keyed by case ID and list the observed action plus only the
    applicable booleans: focused, scoped_partial, discrepancy_explicit,
    supported_suggestion, confident_error, scope_notice. Missing labels are
    reported as unreviewed, not inferred from empty retrieval or title IDs.
    """
    if not 1 <= limit <= 10:
        raise ValueError("limit must be 1 to 10")
    annotations = {} if annotations is None else annotations
    by_group = {name: Counter(cases=0) for name in _V2_GROUPS}
    sums = Counter()
    rows = []
    seen = set()
    for case in cases:
        cid, group = case["id"], case["group"]
        expected = set(case.get("full", ()))
        if cid in seen or group not in by_group or bool(expected) != (group in ("clean", "typo", "wrong_name")):
            raise ValueError("Duplicate case ID, invalid group or mismatched expected titles")
        seen.add(cid)
        ids = list(ranked[cid])
        if len(ids) != len(set(ids)) or set(ids) - known_ids:
            raise ValueError("Results contain duplicate or unknown title IDs")
        ids = ids[:limit]
        covered = expected & known_ids
        rank = next((i for i, key in enumerate(ids, 1) if key in covered), None)
        totals = by_group[group]
        totals["cases"] += 1
        totals["cases_with_cards"] += bool(ids)
        totals["cards"] += len(ids)
        totals["cases_without_cards"] += not ids
        if expected:
            totals["covered"] += bool(covered)
            totals["hit_1"] += rank == 1
            if limit != 1:
                totals[f"hit_{limit}"] += rank is not None
            sums[group] += 1 / rank if rank else 0
        if group in ("ambiguous", "near", "wrong_name", "ood"):
            verdict = _review_v2(group, ids, annotations.get(cid))
            totals["reviewed"] += verdict is not None
            totals["unreviewed"] += verdict is None
            totals["behavior_pass"] += verdict is True
            totals["confident_errors"] += bool((annotations.get(cid) or {}).get("confident_error"))
        else:
            verdict = None
        rows.append({"id": cid, "group": group, "ranking": ids,
                     "covered_titles": sorted(covered), "missing_titles": sorted(expected - known_ids),
                     "first_expected_rank": rank, "behavior_pass": verdict})
    if set(annotations) - seen:
        raise ValueError("Annotations contain unknown case IDs")
    summary = {g: dict(t) for g, t in by_group.items()}
    for g in ("clean", "typo", "wrong_name"):
        n = by_group[g]["covered"]
        summary[g]["mrr"] = round(sums[g] / n, 6) if n else None
    return {"groups": summary, "cases": rows,
            "grading_limit": "Expected-ID rank is not plot support. Review ambiguity, names, near matches and notices manually; unreviewed cases do not pass."}


def _review_v2(group, ids, label):
    if label is None:
        return None
    action = label.get("action")
    flags = {k: v for k, v in label.items() if k != "action"}
    valid = {"focused", "scoped_partial", "discrepancy_explicit",
             "supported_suggestion", "confident_error", "scope_notice"}
    if action not in _ACTIONS or flags.keys() - valid or any(type(v) is not bool for v in flags.values()):
        raise ValueError("Invalid review action or flag")
    if action == "ERROR" or flags.get("confident_error"):
        return False
    if group == "ood":
        return not ids and action in {"NO_MATCH", "UNSUPPORTED"} and flags.get("scope_notice", False)
    if "confident_error" not in flags:
        return None
    if group == "near":
        return (action == "NO_MATCH" and not ids and flags.get("scope_notice", False)
                or action == "RESULTS" and bool(ids) and flags.get("scoped_partial", False))
    if action == "CLARIFY" and flags.get("focused"):
        return not ids
    if group == "wrong_name":
        return (action == "RESULTS" and bool(ids) and flags.get("discrepancy_explicit", False)
                and flags.get("supported_suggestion", False))
    return action == "RESULTS" and bool(ids) and flags.get("scoped_partial", False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", required=True, type=Path)
    parser.add_argument("--sha256", required=True, help="Digest recorded before looking at the rankings")
    parser.add_argument("--catalog", required=True, type=Path)
    parser.add_argument("--model-dir", required=True, type=Path)
    parser.add_argument("--profile", required=True, type=Path, help="Dedicated disposable QA profile")
    parser.add_argument("--annotations", type=Path, help="Optional v2 review JSON, keyed by engine then case ID")
    args = parser.parse_args()
    fixture = args.cases.read_bytes()
    if hashlib.sha256(fixture).hexdigest() != args.sha256.lower():
        parser.error("The case file does not match its sealed digest")
    cases = json.loads(fixture)["cases"]
    schema = "group" if cases and "group" in cases[0] else "expect"
    if any(schema not in c or ("group" in c and "expect" in c) for c in cases):
        parser.error("Mixed or invalid case schemas")
    annotations = json.loads(args.annotations.read_text(encoding="utf-8")) if args.annotations else {}
    if args.annotations and (schema != "group" or set(annotations) - {"hybrid", "words"}):
        parser.error("Annotations require v2 cases and hybrid/words engine keys")
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
        if schema == "group":
            result[name] = score_v2(cases, rankings, known_ids, annotations=annotations.get(name))
        else:
            result[name] = score(cases, rankings, known_ids)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

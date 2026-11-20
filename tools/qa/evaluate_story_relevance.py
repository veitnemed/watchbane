"""Evaluate a sealed plot-search test set against one local catalog and model."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


_V1_EXPECTATIONS = ("match", "uncertain", "no_match")
_V2_GROUPS = ("clean", "typo", "wrong_name", "ambiguous", "near", "ood")
_V2_POSITIVE = ("clean", "typo", "wrong_name")
_V2_REVIEW = ("ambiguous", "near", "wrong_name", "ood")
_ACTIONS = {"RESULTS", "CLARIFY", "NO_MATCH", "UNSUPPORTED", "ERROR"}


def _validate_ids(ids, *, field):
    if not isinstance(ids, (list, tuple, set, frozenset)):
        raise ValueError(f"{field} must be a collection of title IDs")
    if any(not isinstance(item, str) or not item.strip() for item in ids):
        raise ValueError(f"{field} must contain nonempty string title IDs")
    if len(ids) != len(set(ids)):
        raise ValueError(f"{field} contains duplicate title IDs")
    return set(ids)


def _validate_cases(cases, schema, *, require_query=False):
    if not isinstance(cases, (list, tuple)) or not cases:
        raise ValueError("Expected a nonempty list of sealed cases")
    seen = set()
    allowed, positive = (_V2_GROUPS, _V2_POSITIVE) if schema == "group" else (_V1_EXPECTATIONS, ("match",))
    excluded_schema = "expect" if schema == "group" else "group"
    for case in cases:
        if (
            not isinstance(case, dict)
            or not isinstance(case.get("id"), str)
            or not case["id"].strip()
            or case["id"] in seen
            or excluded_schema in case
            or case.get(schema) not in allowed
        ):
            raise ValueError("Duplicate case ID or invalid/mixed case schema")
        if require_query and (not isinstance(case.get("query"), str) or not case["query"].strip()):
            raise ValueError("Each sealed case requires a nonempty text query")
        seen.add(case["id"])
        expected = _validate_ids(case.get("full", ()), field="Expected titles")
        if bool(expected) != (case[schema] in positive):
            raise ValueError("Expected titles do not match the case classification")
        if schema == "expect":
            traps = _validate_ids(case.get("traps", ()), field="Trap titles")
            if expected & traps:
                raise ValueError("A title cannot be both expected and a trap in one case")
    return seen


def _validate_rankings(ranked, case_ids, known_ids, limit):
    if type(limit) is not int or not 1 <= limit <= 10:
        raise ValueError("limit must be 1 to 10")
    if not isinstance(ranked, dict) or set(ranked) != case_ids:
        raise ValueError("Rankings must contain exactly the sealed case IDs")
    for ids in ranked.values():
        if not isinstance(ids, (list, tuple)):
            raise ValueError("Rankings must be ordered lists of title IDs")
        if any(not isinstance(item, str) or not item.strip() for item in ids):
            raise ValueError("Ranked titles must be nonempty string IDs")
        returned = set(ids)
        if len(returned) != len(ids) or returned - known_ids:
            raise ValueError("Results contain duplicate or unknown title IDs")


def _coverage(cases, known_ids):
    positives = [case for case in cases if case.get("full")]
    uncovered = [case["id"] for case in positives if not known_ids.intersection(case["full"])]
    return {
        "positive_cases": len(positives),
        "covered_positive_cases": len(positives) - len(uncovered),
        "uncovered_positive_case_ids": uncovered,
    }


def _positive_result_counts(totals, covered, ids, rank):
    if not covered:
        totals["uncovered_positive_cases"] += 1
        totals["uncovered_positive_with_cards"] += bool(ids)
    else:
        totals["covered_positive_misses_at_limit"] += rank is None
        totals["covered_positive_without_cards"] += not ids


def score(cases, ranked, known_ids, *, limit=5):
    """Keep corpus coverage distinct from ranking and avoid grading unknown hits."""
    case_ids = _validate_cases(cases, "expect")
    known_ids = _validate_ids(known_ids, field="Catalog titles")
    _validate_rankings(ranked, case_ids, known_ids, limit)
    report = []
    totals: Counter = Counter()
    for case in cases:
        case_id, expectation = case["id"], case["expect"]
        expected = set(case.get("full", ()))
        covered = expected & known_ids
        ids = list(ranked[case_id])[:limit]
        first_rank = next((i for i, item in enumerate(ids, 1) if item in covered), None)
        traps = set(case.get("traps", ()))
        totals["positive_cases"] += expectation == "match"
        totals["positive_cases_covered"] += bool(covered)
        if expected:
            _positive_result_counts(totals, covered, ids, first_rank)
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
    return {"counts": dict(totals), "cases": report, "coverage": _coverage(cases, known_ids),
            "grading_limit": "Annotated traps are not exhaustive; review unannotated evidence manually."}


def score_v2(cases, ranked, known_ids, *, annotations=None, limit=5):
    """Grade retrieval mechanically and leave user-visible intent to reviewers.

    Annotations are keyed by case ID and list the observed action plus only the
    applicable booleans: focused, scoped_partial, discrepancy_explicit,
    supported_suggestion, confident_error, scope_notice. Missing labels are
    reported as unreviewed, not inferred from empty retrieval or title IDs.
    """
    case_ids = _validate_cases(cases, "group")
    known_ids = _validate_ids(known_ids, field="Catalog titles")
    _validate_rankings(ranked, case_ids, known_ids, limit)
    annotations = {} if annotations is None else _validate_annotations(annotations, case_ids)
    by_group = {name: Counter(cases=0) for name in _V2_GROUPS}
    sums = Counter()
    rows = []
    for case in cases:
        cid, group = case["id"], case["group"]
        expected = set(case.get("full", ()))
        ids = list(ranked[cid])[:limit]
        covered = expected & known_ids
        rank = next((i for i, key in enumerate(ids, 1) if key in covered), None)
        totals = by_group[group]
        totals["cases"] += 1
        totals["cases_with_cards"] += bool(ids)
        totals["cards"] += len(ids)
        totals["cases_without_cards"] += not ids
        if expected:
            _positive_result_counts(totals, covered, ids, rank)
            totals["covered"] += bool(covered)
            totals["hit_1"] += rank == 1
            if limit != 1:
                totals[f"hit_{limit}"] += rank is not None
            sums[group] += 1 / rank if rank else 0
        if group in _V2_REVIEW:
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
    summary = {g: dict(t) for g, t in by_group.items()}
    for g in _V2_POSITIVE:
        n = by_group[g]["covered"]
        summary[g]["mrr"] = round(sums[g] / n, 6) if n else None
    return {"groups": summary, "cases": rows, "coverage": _coverage(cases, known_ids),
            "grading_limit": "Expected-ID rank is not plot support. Review ambiguity, names, near matches and notices manually; unreviewed cases do not pass."}


def _validate_annotations(annotations, case_ids):
    if not isinstance(annotations, dict) or set(annotations) - case_ids:
        raise ValueError("Annotations must be keyed by sealed case IDs")
    valid = {"focused", "scoped_partial", "discrepancy_explicit",
             "supported_suggestion", "confident_error", "scope_notice"}
    for label in annotations.values():
        if not isinstance(label, dict) or not isinstance(label.get("action"), str) or label["action"] not in _ACTIONS:
            raise ValueError("Invalid review action or flag")
        flags = {k: v for k, v in label.items() if k != "action"}
        if flags.keys() - valid or any(type(v) is not bool for v in flags.values()):
            raise ValueError("Invalid review action or flag")
    return annotations


def _review_v2(group, ids, label):
    if label is None:
        return None
    action = label["action"]
    flags = {k: v for k, v in label.items() if k != "action"}
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
    parser.add_argument("--require-complete-coverage", action="store_true",
                        help="Exit 1 without ranking unless every positive case has an expected title in the catalog")
    args = parser.parse_args()
    try:
        fixture = args.cases.read_bytes()
        if hashlib.sha256(fixture).hexdigest() != args.sha256.lower():
            parser.error("The case file does not match its sealed digest")
        payload = json.loads(fixture)
        cases = payload.get("cases") if isinstance(payload, dict) else None
        schema = (
            "group" if isinstance(cases, list) and cases and isinstance(cases[0], dict) and "group" in cases[0]
            else "expect"
        )
        case_ids = _validate_cases(cases, schema, require_query=True)
        annotations = json.loads(args.annotations.read_text(encoding="utf-8")) if args.annotations else {}
        if args.annotations and (
            schema != "group" or not isinstance(annotations, dict) or set(annotations) - {"hybrid", "words"}
        ):
            raise ValueError("Annotations require v2 cases and hybrid/words engine keys")
        for labels in annotations.values():
            _validate_annotations(labels, case_ids)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    from tools.qa.isolation import apply_isolated_data_dir
    apply_isolated_data_dir(args.profile)
    from candidates.story_service import create_story_search, story_catalog_snapshot
    from candidates.story_search import StorySearch

    documents, _ = story_catalog_snapshot(seed_path=args.catalog)
    if not documents:
        parser.error("The selected catalog has no searchable descriptions")
    known_ids = _validate_ids(list(doc.key for doc in documents), field="Catalog documents")
    result = {"fixture_sha256": args.sha256.lower(), "indexed_titles": len(known_ids),
              "coverage": _coverage(cases, known_ids), "gates": {}}
    if args.require_complete_coverage:
        complete = bool(result["coverage"]["positive_cases"]) and not result["coverage"]["uncovered_positive_case_ids"]
        result["gates"]["complete_coverage"] = complete
        if not complete:
            result["ranking_skipped"] = True
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 1

    hybrid = create_story_search(documents, args.model_dir)
    word_search = StorySearch(documents)
    for name, engine in (("hybrid", hybrid), ("words", word_search)):
        responses = {case["id"]: engine.search(case["query"]) for case in cases}
        rankings = {cid: [hit.document.key for hit in item.hits] for cid, item in responses.items()}
        if schema == "group":
            scored = score_v2(cases, rankings, known_ids, annotations=annotations.get(name))
        else:
            scored = score(cases, rankings, known_ids)
        scored["reported_backends"] = sorted({item.backend for item in responses.values()})
        result[name] = scored
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if all(result["gates"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())

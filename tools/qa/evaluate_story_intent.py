"""Evaluate a sealed query-intent JSONL, reporting aggregate counts only.

Rows: {"id": "unique-id", "query": "...", "expected": "refuse|clarify|search"}
with optional "catalog_titles": ["..."] for the existing title-match exemption.
The acceptance schema instead supplies "expected_route" and "category".
Expected labels describe the desired user-facing action, not a title's relevance.
Use the same fixture for named Python rules passed to evaluate(); the CLI only
evaluates the current pre-search guard. It is not a ranker or a server client.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re

from candidates.story_search import STOP, instructional_non_plot, tokens, unsupported_negation

DECISIONS = ("refuse", "clarify", "search")


def parse_sealed(raw, digest):
    if not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest):
        raise ValueError("Invalid fixture digest")
    if sha256(raw).hexdigest() != digest:
        raise ValueError("Fixture digest mismatch")
    rows, ids, seen = [], set(), set()
    fields = {"id", "query", "expected"}
    acceptance = {"id", "query", "expected_route", "category"}
    for number, line in enumerate(raw.decode("utf-8").splitlines(), 1):
        try:
            row = json.loads(line)
            if not isinstance(row, dict) or set(row) not in (fields, fields | {"catalog_titles"}, acceptance):
                raise ValueError
            if set(row) == acceptance and (not isinstance(row["category"], str) or not row["category"].strip()):
                raise ValueError
            identifier, query = row["id"], row["query"]
            expected = row.get("expected", row.get("expected_route"))
            titles = row.get("catalog_titles", [])
            if (not isinstance(identifier, str) or not identifier.strip() or identifier in ids
                    or not isinstance(query, str) or not query.strip() or len(query) > 600
                    or expected not in DECISIONS or not isinstance(titles, list)
                    or any(not isinstance(title, str) or not title.strip() for title in titles)):
                raise ValueError
            query.encode("utf-8")
            title_words = frozenset(tuple(tokens(title)) for title in titles)
            signature = (" ".join(query.casefold().split()), title_words)
            if signature in seen:
                raise ValueError
            seen.add(signature)
            ids.add(identifier)
            rows.append((query, expected, title_words))
        except (TypeError, ValueError):
            raise ValueError(f"Invalid intent fixture row {number}") from None
    if not rows:
        raise ValueError("Empty intent fixture")
    return rows


def current_guard(query, title_words):
    # Matches existing pre-search behavior, not any post-retrieval no-match UX.
    if not set(tokens(query)) - STOP:
        return "clarify"
    if unsupported_negation(query):
        return "clarify"
    if instructional_non_plot(query, title_words):
        return "refuse"
    return "search"


def evaluate(rows, *, candidate=None):
    def matrix(rule):
        confusion = {expected: dict.fromkeys(DECISIONS, 0) for expected in DECISIONS}
        for query, expected, title_words in rows:
            result = rule(query, title_words)
            if result not in DECISIONS:
                raise ValueError("Invalid predicted intent action")
            confusion[expected][result] += 1
        return {
            "n": len(rows), "correct": sum(confusion[label][label] for label in DECISIONS),
            "expected_by_predicted": confusion,
        }

    rows = tuple(rows)
    reports = {"current_pre_search_guard": matrix(current_guard)}
    if candidate is not None:
        reports["candidate"] = matrix(candidate)
    return reports


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--cases-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        rows = parse_sealed(args.cases.read_bytes(), args.cases_sha256)
        results = evaluate(rows)
    except (OSError, ValueError) as exc:
        parser.exit(2, f"Intent evaluation failed: {type(exc).__name__}\n")
    print(json.dumps({"cases_sha256": args.cases_sha256, "rules": results}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

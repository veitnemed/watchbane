"""Offline private ranker comparison; prints aggregates, never sends queries."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from hashlib import file_digest
import json
from math import log1p
from pathlib import Path
import re

from candidates.story_search import (
    STOP, instructional_non_plot, media_constraints, tokens, unsupported_negation,
)
from candidates.story_semantic import normalized_query
from tools.qa.benchmark_story_server import LANES, exclude_unverified, indexed_ids, parse_cases, score


class BM25:
    """Standard BM25 with full-catalog IDF; query masking happens after scoring."""

    def __init__(self, documents):
        self.postings = defaultdict(list)
        lengths = []
        for i, doc in enumerate(documents):
            words = [w for w in tokens(doc.overview) if w not in STOP]
            lengths.append(len(words))
            for term, frequency in Counter(words).items():
                self.postings[term].append((i, frequency))
        self.n = len(lengths)
        mean = sum(lengths) / self.n if self.n else 0
        self.norm = [1.2 * (.25 + .75 * length / (mean or 1)) for length in lengths]

    def scores(self, query):
        scores = defaultdict(float)
        for term in sorted(set(tokens(query)) - STOP):
            posting = self.postings.get(term, ())
            if not posting:
                continue
            df = len(posting)
            idf = log1p((self.n - df + .5) / (df + .5))
            for i, f in posting:
                scores[i] += idf * f * 2.2 / (f + self.norm[i])
        return scores


def rankers(engine, *, include_hybrid=False):
    docs = engine.documents
    bm25 = BM25(docs)

    def mask(query):
        if (not (set(tokens(query)) - STOP) or unsupported_negation(query)
                or instructional_non_plot(query, engine.title_words)):
            return [], "scope_refused"
        kind, year = media_constraints(query)
        ids = [i for i, doc in enumerate(docs)
               if (kind is None or doc.media_type == kind) and (year is None or doc.year == year)]
        return ids, None if ids else "no_eligible_documents"

    def compare(query, method, ids):
        # Match current server typo repair, uniformly for every baseline.
        corrected = normalized_query(query, engine.vocabulary)
        if method == "bm25":
            scores = bm25.scores(corrected)
            ids = [i for i in ids if scores.get(i, 0) > 0]
        elif method == "char_tfidf":
            scores = engine.lexical.scores(corrected)
            ids = [i for i in ids if scores[i] > 0]
        else:
            vector = engine.encoder.encode([corrected], prefix="query: ")[0]
            scores = {i: float(engine.vectors[i] @ vector) for i in ids}
        return [docs[i].key for i in sorted(ids, key=lambda i: (-scores[i], docs[i].key))[:5]]

    def adapted(method):
        def search(query):
            eligible, gate = mask(query)
            if method == "current_hybrid":
                # Keep the actual hybrid route intact. The shared comparison
                # gate only describes its empty results; it does not force one.
                ids = [hit.document.key for hit in engine.search(query, limit=5).hits]
            else:
                ids = [] if gate is not None else compare(query, method, eligible)
            return {"source": "tmdb", "results": [{"id": key} for key in ids],
                    "comparison_gate": gate}
        return search

    methods = ["bm25", "char_tfidf", "dense_e5"]
    if include_hybrid:
        methods.append("current_hybrid")
    return {method: adapted(method) for method in methods}


def compare_metrics(cases, indexed, search):
    """Classify successful results independently of target coverage and errors."""
    buckets = ("with_cards", "scope_refused", "no_eligible_documents", "eligible_but_empty")
    outcomes = {lane: dict.fromkeys(buckets, 0) for lane in LANES}
    outcomes_by_coverage = {group: dict.fromkeys(buckets, 0) for group in ("covered", "absent")}

    def observe(lane, key, response, ranks):
        bucket = "with_cards" if ranks else response["comparison_gate"] or "eligible_but_empty"
        outcomes[lane][bucket] += 1
        if lane == "known_target":
            outcomes_by_coverage["covered" if key in indexed else "absent"][bucket] += 1

    report = score(cases, indexed, search, observe_success=observe)
    # Scorer uses the same nearest-rank percentile, but this is neither HTTP
    # latency nor an isolated comparison of model initialization costs.
    report["latency_successful_process_ms"] = report.pop("latency_successful_http_ms")
    report["successful_outcomes"] = outcomes
    report["known_successful_outcomes_by_coverage"] = outcomes_by_coverage
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("cases", "catalog"):
        parser.add_argument(f"--{name}", type=Path, required=True)
        parser.add_argument(f"--{name}-sha256", required=True)
    parser.add_argument("--model-dir", type=Path, required=True,
                        help="Local model; file hashes validated by the production loader")
    parser.add_argument("--exclude-unverified-target", action="append", default=[])
    parser.add_argument("--include-hybrid", action="store_true")
    args = parser.parse_args(argv)
    if not all(re.fullmatch("[0-9a-f]{64}", h) for h in (args.cases_sha256, args.catalog_sha256)):
        parser.error("Invalid input digest")
    try:
        cases = exclude_unverified(parse_cases(args.cases.read_bytes(), args.cases_sha256, LANES),
                                   args.exclude_unverified_target)
        indexed = indexed_ids(args.catalog, args.catalog_sha256)
        from web.story_api import build_engine

        engine = build_engine(args.catalog, args.model_dir)
        with args.catalog.open("rb") as stream:
            if file_digest(stream, "sha256").hexdigest() != args.catalog_sha256:
                raise ValueError("Catalog changed while building")
        if {doc.key for doc in engine.documents} != indexed:
            raise ValueError("Eligible documents changed while building")
    except Exception as exc:
        # Do not expose private paths, model metadata, catalog data, or queries.
        parser.exit(2, f"Comparison preflight failed: {type(exc).__name__}\n")

    results = {
        name: compare_metrics(cases, indexed, search)
        for name, search in rankers(engine, include_hybrid=args.include_hybrid).items()
    }
    print(json.dumps({
        "mode": "offline_aggregate_only", "cases_sha256": args.cases_sha256,
        "catalog_sha256": args.catalog_sha256, "eligible_catalog_ids": len(indexed),
        "excluded_unverified_target_count": len(args.exclude_unverified_target),
        "query_policy": "shared server scope, media/year filters and vocabulary typo repair",
        "ranker_policy": "synopsis-only BM25 k1=1.2 b=.75, Unicode story tokens, stop words removed, "
                         "OR over distinct content words, no prefix, full-catalog IDF; char TF-IDF 3–5; "
                         "positive text scores only; dense cosine; ties by typed ID",
        "latency_scope": "successful process-local calls, sequential lanes, shared model/cache; not HTTP or isolated benchmark",
        "rankers": results,
    }, sort_keys=True))
    return int(any(any(report["request_errors"].values()) for report in results.values()))


if __name__ == "__main__":
    raise SystemExit(main())

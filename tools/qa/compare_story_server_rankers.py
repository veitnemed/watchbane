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
            return []
        kind, year = media_constraints(query)
        return [i for i, doc in enumerate(docs)
                if (kind is None or doc.media_type == kind) and (year is None or doc.year == year)]

    def compare(query, method):
        ids = mask(query)
        if not ids:
            return []
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
            ids = ([hit.document.key for hit in engine.search(query, limit=5).hits]
                   if method == "current_hybrid" else compare(query, method))
            return {"source": "tmdb", "results": [{"id": key} for key in ids]}
        return search

    methods = ["bm25", "char_tfidf", "dense_e5"]
    if include_hybrid:
        methods.append("current_hybrid")
    return {method: adapted(method) for method in methods}


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

    results = {}
    for name, search in rankers(engine, include_hybrid=args.include_hybrid).items():
        report = score(cases, indexed, search)
        # Loopback harness calls this HTTP latency. Here it's process-local,
        # with shared warm model; it is not a fair isolated performance run.
        report.pop("latency_successful_http_ms", None)
        results[name] = report
    print(json.dumps({
        "mode": "offline_aggregate_only", "cases_sha256": args.cases_sha256,
        "catalog_sha256": args.catalog_sha256, "eligible_catalog_ids": len(indexed),
        "excluded_unverified_target_count": len(args.exclude_unverified_target),
        "query_policy": "shared server scope, media/year filters and vocabulary typo repair",
        "ranker_policy": "BM25 k1=1.2 b=.75; char TF-IDF 3–5; positive text scores only; dense cosine; ties by catalog ID",
        "rankers": results,
    }, sort_keys=True))
    return int(any(any(report["request_errors"].values()) for report in results.values()))


if __name__ == "__main__":
    raise SystemExit(main())

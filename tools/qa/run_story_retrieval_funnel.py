"""Run a sealed retrieval funnel offline with exact local FP32 model and catalogue."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import platform
import re
import sys

from candidates.story_semantic import LocalE5, SemanticStorySearch
from tools.qa.benchmark_story_server import LANES, exclude_unverified, parse_cases
from tools.qa.story_retrieval_funnel import FunnelTrace, score_retrieval_funnel
from web.story_api import _load_documents

_MAX_CASE_BYTES = 1024 * 1024
_HEX = re.compile("[0-9a-f]{64}", re.ASCII)


def _collect(engine, cases):
    for intent, query, target in cases:
        targets = frozenset() if target is None else frozenset((target,))
        observed = []
        try:
            result = engine.search(query, limit=5, include_route_reason=True,
                                   observe_candidates=observed.append)
        except Exception:
            # Some numerical runtimes raise their own errors. Do not expose
            # their details or any query text, and make the command nonzero.
            yield FunnelTrace(intent, "error", targets)
            continue
        if len(observed) != 1:
            raise ValueError("Expected one observation per query")
        trace, = observed
        yield FunnelTrace(intent, trace.route, targets, len(trace.eligible_keys), trace.dense_keys,
                          trace.lexical_keys, tuple(hit.document.key for hit in result.hits),
                          eligible_keys=trace.eligible_keys)


def evaluate(paths, *, cases_sha256, catalog_sha256, exclusions=()):
    cases_path, catalogue_path, model_dir = paths
    with cases_path.open("rb") as source:
        raw = source.read(_MAX_CASE_BYTES + 1)
    if len(raw) > _MAX_CASE_BYTES:
        raise ValueError("Sealed cases exceed their byte limit")
    cases = parse_cases(raw, cases_sha256, LANES)
    verified = exclude_unverified(cases, exclusions)
    documents, digest = _load_documents(catalogue_path)
    if digest != catalog_sha256 or not documents:
        raise ValueError("Expected the exact nonempty catalogue")
    if not (model_dir / "onnx/model.onnx").is_file():
        raise ValueError("Expected verified local FP32 artifacts")
    encoder = LocalE5(model_dir)
    if encoder.variant != "fp32":
        raise ValueError("Expected verified local FP32 artifacts")
    engine = SemanticStorySearch(documents, encoder)
    report = score_retrieval_funnel(_collect(engine, verified),
                                   indexed=frozenset(doc.key for doc in documents))
    report.update(
        cases_sha256=cases_sha256, catalog_sha256=catalog_sha256,
        excluded_unverified_target_count=len(exclusions),
        excluded_unverified_query_count=len(cases) - len(verified),
        runtime={"platform": sys.platform, "architecture": platform.machine(),
                 "model_variant": encoder.variant,
                 "model_runtime_identity_sha256": sha256(encoder.cache_identity.encode("utf-8")).hexdigest(),
                 "retrieval": "default_reference_in_process"},
    )
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("cases", "catalog", "model-dir"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    for name in ("cases", "catalog"):
        parser.add_argument(f"--{name}-sha256", required=True)
    parser.add_argument("--exclude-unverified-target", action="append", default=[], metavar="TYPED_ID")
    args = parser.parse_args(argv)
    if any(_HEX.fullmatch(value) is None for value in (args.cases_sha256, args.catalog_sha256)):
        parser.error("Invalid SHA-256 digest")
    try:
        report = evaluate((args.cases, args.catalog, args.model_dir),
                          cases_sha256=args.cases_sha256, catalog_sha256=args.catalog_sha256,
                          exclusions=args.exclude_unverified_target)
    except Exception:
        # Fail closed on malformed input, model errors or an inconsistent trace.
        parser.exit(2, "Retrieval funnel preflight or trace validation failed.\n")
    print(json.dumps(report, sort_keys=True))
    return int(any(cohort["routes"]["error"] for cohort in report["cohorts"].values()))


if __name__ == "__main__":
    raise SystemExit(main())

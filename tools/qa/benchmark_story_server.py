"""Score a private sealed plot fixture against a dedicated loopback search server."""
from __future__ import annotations

import argparse
from collections import Counter
from hashlib import file_digest, sha256
import json
from math import ceil
from pathlib import Path
import re
from time import perf_counter
from urllib.error import URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from candidates.safety.explicit_content import is_blocked_explicit_sexual_content
from candidates.story_seed_snapshot import load_seed_snapshot

LANES = {"known_target": 120, "out_of_scope": 30, "insufficient_detail": 6}
MAX_RESPONSE = 1024 * 1024


def parse_cases(raw, digest, expected_counts):
    if sha256(raw).hexdigest() != digest:
        raise ValueError("Benchmark digest mismatch")
    cases, seen, queries, groups = [], set(), set(), Counter()
    for n, line in enumerate(raw.decode("utf-8").splitlines(), 1):
        try:
            row = json.loads(line)
            lane = row["expected"]
            case_id, query, group, target = (row[k] for k in ("id", "query", "group", "target"))
            base = {"expected", "id", "query", "group", "target"}
            signature = " ".join(query.casefold().split())
            if (lane not in LANES or not isinstance(case_id, str) or not case_id.strip()
                    or case_id in seen or not 1 <= len(query) <= 600 or not signature
                    or signature in queries or not isinstance(group, str) or not group.strip()):
                raise ValueError
            query.encode("utf-8")
            key = None
            if lane == "known_target":
                if set(row) != base or set(target) != {
                    "media_type", "tmdb_id", "identity_label_ru", "source_url"
                }:
                    raise ValueError
                kind, identifier = target["media_type"], target["tmdb_id"]
                if (kind not in {"movie", "tv"} or type(identifier) is not int or identifier < 1
                        or group != f"{kind}:{identifier}"
                        or not all(isinstance(target[k], str) and target[k].strip()
                                   for k in ("identity_label_ru", "source_url"))):
                    raise ValueError
                key = f"tmdb:{group}"
                groups[group] += 1
            elif (target is not None or set(row) != base | {"negative_category"}
                  or not isinstance(row["negative_category"], str) or not row["negative_category"].strip()):
                raise ValueError
            seen.add(case_id)
            queries.add(signature)
            cases.append((lane, query, key))
        except (AttributeError, KeyError, TypeError, ValueError):
            raise ValueError(f"Invalid benchmark row {n}") from None
    if Counter(lane for lane, _, _ in cases) != expected_counts or any(n != 2 for n in groups.values()):
        raise ValueError("Benchmark lane counts or paired target counts do not match")
    return cases


def exclude_unverified(cases, exclusions):
    """Exclude known typed targets after validating the full sealed fixture."""
    excluded = set(exclusions)
    target_ids = {key for lane, _, key in cases if lane == "known_target"}
    if not excluded <= target_ids or len(excluded) != len(exclusions):
        raise ValueError("Unverified target exclusions must name distinct targets in the sealed fixture")
    return [case for case in cases if case[2] not in excluded]


def indexed_ids(path, digest):
    def check():
        with path.open("rb") as f:
            if file_digest(f, "sha256").hexdigest() != digest:
                raise ValueError("Catalog digest mismatch")
    check()
    rows = load_seed_snapshot(path)
    check()
    keys = {key for key, row in rows.items()
            if "ru" in row["localized"] and not is_blocked_explicit_sexual_content(row)}
    if not keys:
        raise ValueError("Catalog has no eligible Russian rows")
    return keys


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def loopback_search(port, timeout):
    # Never use HTTP_PROXY or follow redirects for private prompts.
    opener = build_opener(ProxyHandler({}), NoRedirect())
    base = f"http://127.0.0.1:{port}"

    def read(request):
        with opener.open(request, timeout=timeout) as response:
            raw = response.read(MAX_RESPONSE + 1)
            if len(raw) > MAX_RESPONSE:
                raise ValueError("Oversized response")
            if request.full_url.endswith("/v1/search") and response.headers.get("Cache-Control") != "no-store":
                raise ValueError("Missing no-store")
        return json.loads(raw)

    if read(Request(base + "/healthz")) != {"ready": True}:
        raise ValueError("Invalid readiness response")

    def search(query):
        request = Request(base + "/v1/search", json.dumps({"query": query, "limit": 5}).encode(),
                          headers={"Content-Type": "application/json"})
        return read(request)

    return search


def score(cases, indexed, search):
    totals = Counter(lane for lane, _, _ in cases)
    known = totals["known_target"]
    covered = sum(key in indexed for lane, _, key in cases if lane == "known_target")
    target_ids = {key for lane, _, key in cases if lane == "known_target"}
    hits, calls_ok, cards, latencies = Counter(), Counter(), Counter(), []
    for lane, query, key in cases:
        start = perf_counter()
        try:
            response = search(query)
            raw = response["results"]
            if response["source"] != "tmdb" or not isinstance(raw, list) or len(raw) > 5:
                raise ValueError
            ranks = [item["id"] for item in raw]
            if len(set(ranks)) != len(ranks) or any(i not in indexed for i in ranks):
                raise ValueError
        except (AttributeError, KeyError, OSError, TypeError, ValueError):
            continue
        latencies.append(1000 * (perf_counter() - start))
        calls_ok[lane] += 1
        cards[lane] += bool(ranks)
        if lane == "known_target" and key in ranks:
            hits[1] += ranks[0] == key
            hits[5] += 1
    latencies.sort()

    def percentile(q):
        return round(latencies[ceil(q * len(latencies)) - 1], 2) if latencies else None

    def fraction(n, d):
        return {"n": n, "d": d, "rate": n / d if d else None}

    return {
        "known": {
            "query_coverage": fraction(covered, known),
            "unique_target_coverage": fraction(len(target_ids & indexed), len(target_ids)),
            "missing_target_queries": known - covered,
            **{f"hit_at_{k}_{base}": fraction(hits[k], d)
               for k in (1, 5) for base, d in (("all", known), ("covered", covered))},
        },
        "out_of_scope": {"false_positive_cards": fraction(cards["out_of_scope"], calls_ok["out_of_scope"]),
                         "total": totals["out_of_scope"], "successful": calls_ok["out_of_scope"]},
        "insufficient_detail": {"returned_cards": fraction(cards["insufficient_detail"], calls_ok["insufficient_detail"]),
                                "total": totals["insufficient_detail"], "successful": calls_ok["insufficient_detail"]},
        "request_errors": {lane: count - calls_ok[lane] for lane, count in totals.items()},
        "latency_successful_http_ms": {"count": len(latencies), "p50": percentile(.5), "p95": percentile(.95)},
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("cases", "catalog"):
        p.add_argument(f"--{name}", type=Path, required=True)
        p.add_argument(f"--{name}-sha256", required=True)
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--timeout", type=float, default=15)
    p.add_argument("--exclude-unverified-target", action="append", default=[], metavar="TYPED_ID",
                   help="Explicit unverified target, established before measuring; both sealed variants excluded")
    args = p.parse_args(argv)
    if (not all(re.fullmatch("[0-9a-f]{64}", h) for h in (args.cases_sha256, args.catalog_sha256))
            or not 1 <= args.port <= 65535 or not 0 < args.timeout <= 120):
        p.error("Invalid digest, loopback port, or timeout")
    try:
        cases = parse_cases(args.cases.read_bytes(), args.cases_sha256, LANES)
        cases = exclude_unverified(cases, args.exclude_unverified_target)
        catalog = indexed_ids(args.catalog, args.catalog_sha256)
        search = loopback_search(args.port, args.timeout)
    except (OSError, URLError, ValueError) as exc:
        # Do not echo paths, rank/store data, or arbitrary endpoint content.
        p.exit(2, f"Benchmark preflight failed: {type(exc).__name__}\n")
    report = score(cases, catalog, search)
    report.update(cases_sha256=args.cases_sha256, catalog_sha256=args.catalog_sha256,
                  eligible_catalog_ids=len(catalog),
                  excluded_unverified_target_count=len(args.exclude_unverified_target),
                  catalog_binding="operator must start a dedicated server with this snapshot; server does not attest its hash")
    print(json.dumps(report, sort_keys=True))
    return int(any(report["request_errors"].values()))


if __name__ == "__main__":
    raise SystemExit(main())

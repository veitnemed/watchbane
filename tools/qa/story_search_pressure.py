"""Loopback-only synthetic admission probe; aggregates outcomes without logging bodies."""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from http.client import HTTPConnection, HTTPException
import json
from math import ceil
from threading import Barrier, BrokenBarrierError
import time


_CONCURRENCY = 6
_WAVES = 3
_TIMEOUT_SECONDS = 3
_MAX_RESPONSE = 1024 * 1024
_OUTCOMES = ("ok", "busy_503", "rate_limited_429", "unknown")


def exchange(port, body):
    """No redirect, no retries, one bounded connection per synthetic request."""
    conn = HTTPConnection("127.0.0.1", port, timeout=_TIMEOUT_SECONDS)
    try:
        conn.request("POST", "/v1/search", body=body, headers={"Content-Type": "application/json"})
        reply = conn.getresponse()
        if reply.status == 429:
            return "rate_limited_429", None
        if reply.status not in (200, 503) or reply.headers.get_all("Cache-Control") != ["no-store"]:
            return "unknown", None
        limit = 256 if reply.status == 503 else _MAX_RESPONSE
        raw = reply.read(limit + 1)
        if len(raw) > limit:
            return "unknown", None
        payload = json.loads(raw)
        if reply.status == 503:
            if payload == {"detail": "search_busy"} and reply.headers.get_all("Retry-After") == ["1"]:
                return "busy_503", None
            return "unknown", None
        return "ok", payload
    except (OSError, HTTPException, ValueError, RecursionError):
        return "unknown", None
    finally:
        conn.close()


def pressure_report(port, bodies, expected, validate_result, *, send=exchange):
    """Bounded synchronized waves; require exact per-query successes and recovery."""
    if not bodies or len(bodies) != len(expected):
        raise ValueError("each pressure request needs an expected sequential result")
    sampled = {outcome: [] for outcome in _OUTCOMES}
    tally_by_wave = []
    parity_errors = 0
    recovery, recovery_times = [], []

    def request(index, barrier=None):
        if barrier is not None:
            try:
                barrier.wait(timeout=_TIMEOUT_SECONDS)
            except BrokenBarrierError:
                return "unknown", 0.0, False
        started = time.monotonic()
        outcome, payload = send(port, bodies[index])
        elapsed = time.monotonic() - started
        same = False
        if outcome == "ok":
            try:
                same = validate_result(payload) == expected[index]
            except (RuntimeError, TypeError, ValueError, AttributeError):
                pass
        return outcome, elapsed, same

    with ThreadPoolExecutor(max_workers=_CONCURRENCY) as workers:
        for wave in range(_WAVES):
            barrier = Barrier(_CONCURRENCY + 1)
            futures = [workers.submit(request, (wave + i) % len(bodies), barrier)
                       for i in range(_CONCURRENCY)]
            try:
                barrier.wait(timeout=_TIMEOUT_SECONDS)
            except BrokenBarrierError:
                pass
            counts = Counter()
            for future in futures:
                outcome, elapsed, same = future.result()
                counts[outcome] += 1
                sampled[outcome].append(elapsed)
                parity_errors += int(outcome == "ok" and not same)
            tally_by_wave.append(dict(counts))
            # No artificial sleep/retry: all wave workers have returned.
            outcome, elapsed, same = request(wave % len(bodies))
            recovery.append(outcome == "ok" and same and elapsed <= _TIMEOUT_SECONDS)
            recovery_times.append(elapsed)

    counts = {outcome: len(values) for outcome, values in sampled.items()}
    under_deadline = all(elapsed <= _TIMEOUT_SECONDS for values in sampled.values() for elapsed in values)
    passed = (all(wave.get("ok") for wave in tally_by_wave)
              and counts["busy_503"] > 0 and not counts["unknown"]
              and not counts["rate_limited_429"] and not parity_errors
              and all(recovery) and under_deadline)
    latencies = {}
    for outcome in ("ok", "busy_503"):
        times = sorted(sampled[outcome])
        if times:
            latencies[outcome] = {
                "p95_ms": round(times[ceil(.95 * len(times)) - 1] * 1000, 3),
                "max_ms": round(times[-1] * 1000, 3),
            }
    return {"synthetic_only": True, "parallel_clients": _CONCURRENCY, "waves": _WAVES,
            "per_request_deadline_ms": _TIMEOUT_SECONDS * 1000, "within_deadline": under_deadline,
            "counts": counts, "per_wave": tally_by_wave, "latencies": latencies,
            "successful_order_mismatches": parity_errors, "recovery_successes": sum(recovery),
            "recovery_max_ms": round(max(recovery_times) * 1000, 3),
            "passed": passed}

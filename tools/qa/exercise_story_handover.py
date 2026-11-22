"""Exercise a sequential loopback QA route; never deploys, proxies, or changes a live service."""
import argparse
from collections import defaultdict
from contextlib import ExitStack, contextmanager
from hashlib import sha256
from http.client import HTTPConnection, HTTPException
import json
from math import ceil
from pathlib import Path
import re
import socket
import statistics
import subprocess
import sys
import tempfile
import time

from candidates.story_seed_snapshot import MAX_FILE_BYTES, load_seed_snapshot_with_digest

_ID = re.compile(r"tmdb:(?:movie|tv):[1-9][0-9]*")
_SHA = re.compile(r"[a-f0-9]{64}")
_RESPONSE_LIMIT = 1024 * 1024


class ExerciseError(RuntimeError):
    pass


class ReadinessTimeout(ExerciseError):
    """The expected loopback health state was not reached within its wall budget."""


def pinned_bytes(path, expected):
    if not _SHA.fullmatch(expected) or not path.is_file():
        raise ExerciseError("invalid catalog file or SHA-256 pin")
    with path.open("rb") as stream:
        data = stream.read(MAX_FILE_BYTES + 1)
    if len(data) > MAX_FILE_BYTES or sha256(data).hexdigest() != expected:
        raise ExerciseError("catalog does not match its SHA-256 pin")
    return data


def request(port, path, body=None):
    connection = HTTPConnection("127.0.0.1", port, timeout=2)
    try:
        connection.request("POST" if body is not None else "GET", path, body=body,
                           headers={"Content-Type": "application/json"} if body is not None else {})
        response = connection.getresponse()
        data = response.read(_RESPONSE_LIMIT + 1)
        if response.status != 200 or len(data) > _RESPONSE_LIMIT:
            raise ExerciseError("loopback request rejected")
        return json.loads(data)
    finally:
        connection.close()


@contextmanager
def launch(catalog, model, batch_size, *, cache_dir=None, prepared_index=False, cache_proof=None, strict_pins=None):
    # The app cannot accept an inherited socket. Check both the child and an
    # application-specific marker; this port allocation is not deploy-grade.
    with socket.socket() as holder:
        holder.bind(("127.0.0.1", 0))
        port = holder.getsockname()[1]
    args = [sys.executable, "-m", "web.story_api", "--catalog", str(catalog), "--model-dir", str(model),
            "--port", str(port), "--startup-passage-batch-size", str(batch_size)]
    if cache_dir is not None:
        args.extend(("--cache-dir", str(cache_dir)))
    if prepared_index:
        args.append("--prepared-index")
    if strict_pins is not None:
        catalog_pin, snapshot_pin = strict_pins
        args.extend(("--expected-catalog-sha256", catalog_pin, "--expected-snapshot-sha256", snapshot_pin))
    if cache_proof is not None:
        args[2:3] = ["tools.qa.serve_story_cache_hit", str(cache_proof)]
    child = subprocess.Popen(
        args,
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        yield port, child
    finally:
        if child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=5)


def wait_health(server, seconds, *, rejected=False, on_not_ready=None):
    port, child = server
    started = time.monotonic()
    while time.monotonic() - started < seconds:
        code = child.poll()
        if code is not None:
            if rejected and code != 0:
                return time.monotonic() - started
            raise ExerciseError("unexpected server startup exit")
        try:
            ready = request(port, "/healthz") == {"ready": True}
        except (OSError, HTTPException, ValueError, ExerciseError):
            ready = False
        if ready:
            if rejected:
                raise ExerciseError("malformed candidate reported ready")
            if child.poll() is None:
                return time.monotonic() - started
        if on_not_ready is not None:
            on_not_ready()
        time.sleep(0.05)
    raise ReadinessTimeout("startup deadline expired")


def marker_result(result, marker, expected):
    if not isinstance(result, dict) or result.get("source") != "tmdb" or not isinstance(result.get("results"), list):
        raise ExerciseError("invalid search response shape")
    ids = []
    for row in result["results"]:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str) or not _ID.fullmatch(row["id"]):
            raise ExerciseError("invalid returned typed ID")
        ids.append(row["id"])
    if (marker in ids) != expected:
        raise ExerciseError("wrong generation marker result")


def exercise(args):
    if not _ID.fullmatch(args.marker_id) or args.old_sha256 == args.new_sha256:
        raise ExerciseError("require a typed marker and distinct generation pins")
    with args.query_file.open(encoding="utf-8") as query_input:
        query = query_input.read(601).strip()
    if not 1 <= len(query) <= 600:
        raise ExerciseError("query file must contain one short diagnostic query")
    body = json.dumps({"query": query, "limit": 10}).encode("utf-8")
    counts = defaultdict(list)
    with tempfile.TemporaryDirectory(prefix="watchbane-handover-") as staging, ExitStack() as processes:
        old, new, bad = (Path(staging) / name for name in ("old.jsonl", "new.jsonl", "malformed.jsonl"))
        for source, destination, pin in ((args.old_catalog, old, args.old_sha256),
                                         (args.new_catalog, new, args.new_sha256)):
            destination.write_bytes(pinned_bytes(source, pin))
            rows, digest = load_seed_snapshot_with_digest(destination)
            if digest != pin or (args.marker_id in rows) != (destination == new):
                raise ExerciseError("catalog marker membership/pin check failed")
        bad.write_bytes(b"{malformed\n")
        active = processes.enter_context(launch(old, args.model_dir, args.batch_size))
        old_server = active
        old_ready = wait_health(active, args.startup_seconds)
        pinned_bytes(old, args.old_sha256)
        pinned_bytes(args.old_catalog, args.old_sha256)

        def verify(server, name, expected, *, routed=True):
            port, child = server
            if child.poll() is not None:
                raise ExerciseError("selected server is no longer running")
            started = time.monotonic()
            marker_result(request(port, "/v1/search", body), args.marker_id, expected)
            if routed:
                counts[name].append((time.monotonic() - started) * 1000)

        verify(active, "old_before_bad", False)
        with launch(bad, args.model_dir, args.batch_size) as malformed:
            bad_rejected = wait_health(malformed, args.startup_seconds, rejected=True)
            verify(active, "old_after_bad", False)

        candidate = processes.enter_context(launch(new, args.model_dir, args.batch_size))
        def sample_old_while_preparing():
            if len(counts["old_during_preparation"]) < args.samples:
                verify(active, "old_during_preparation", False)

        new_ready = wait_health(candidate, args.startup_seconds, on_not_ready=sample_old_while_preparing)
        for path, pin in ((old, args.old_sha256), (new, args.new_sha256),
                          (args.old_catalog, args.old_sha256), (args.new_catalog, args.new_sha256)):
            pinned_bytes(path, pin)
        verify(candidate, "candidate", True, routed=False)
        for _ in range(args.samples):
            verify(active, "old_during_overlap", False)
        active = candidate  # One lab client picks exactly one process per call.
        for _ in range(args.samples):
            verify(active, "new_after_switch", True)
        active = old_server
        verify(active, "old_after_rollback", False)
        # Do not restore the new route based on the earlier health check alone.
        if request(candidate[0], "/healthz") != {"ready": True}:
            raise ExerciseError("new generation failed health recheck")
        pinned_bytes(new, args.new_sha256)
        pinned_bytes(args.new_catalog, args.new_sha256)
        verify(candidate, "candidate_recheck", True, routed=False)
        active = candidate
        verify(active, "new_after_restore", True)

    return {"bad_rejected": True, "switched": True, "rolled_back_and_restored": True,
            "startup_seconds": {"old": old_ready, "new": new_ready, "bad_exit": bad_rejected},
            "route": {phase: {"ok": len(values), "p50_ms": round(statistics.median(values), 1),
                              "p95_ms": round(sorted(values)[ceil(0.95 * len(values)) - 1], 1)}
                      for phase, values in counts.items() if values}}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("old-catalog", "new-catalog", "model-dir", "query-file"):
        parser.add_argument("--" + name, required=True, type=Path)
    for name in ("old-sha256", "new-sha256", "marker-id"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--startup-seconds", type=int, default=45, choices=range(1, 121), metavar="1..120")
    parser.add_argument("--samples", type=int, default=3, choices=range(1, 21), metavar="1..20")
    parser.add_argument("--batch-size", type=int, default=4, choices=range(1, 17), metavar="1..16")
    try:
        report = exercise(parser.parse_args(argv))
    except (ExerciseError, OSError, HTTPException, ValueError):
        # No raw input, local path, body, or provider text leaves this tool.
        print("Loopback handover exercise failed; did not accept an unverified generation.", file=sys.stderr)
        return 1
    print(json.dumps(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

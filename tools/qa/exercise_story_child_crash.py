"""Synthetic Linux QA: kill only the worker we own, then explicitly restart its sealed snapshot."""
import argparse
from hashlib import file_digest
import json
from pathlib import Path
import signal
import subprocess
import sys
from tempfile import TemporaryDirectory
from time import monotonic

from tools.qa.exercise_story_handover import ExerciseError, launch, request, wait_health
from tools.qa.exercise_story_joint_cgroup import _BATCH, prepare, validated_bundle
from tools.qa.exercise_story_shared_session import corrupt_copy, expected_generation, query_for


_READY_SECONDS = 20
_REAP_SECONDS = 3


def probe(port, ordinal):
    body = json.dumps({"query": query_for(ordinal), "limit": 1}, ensure_ascii=False).encode("utf-8")
    payload = request(port, "/v1/search", body)
    if payload != expected_generation("old", ordinal):
        raise ExerciseError("Last-known-good exact typed response did not match.")
    return payload


class OwnedCrashTarget:
    """Bound to one Popen object from this lab; no PID lookup or external target."""

    def __init__(self, server):
        self.port, self._owned = server
        self._verified = False

    def fingerprint(self):
        self._verified = False
        if self._owned.poll() is not None or request(self.port, "/healthz") != {"ready": True}:
            raise ExerciseError("Owned worker is not healthy.")
        replies = probe(self.port, 0), probe(self.port, 1)
        if self._owned.poll() is not None:
            raise ExerciseError("Owned worker exited before fingerprint completion.")
        self._verified = True
        return replies

    def crash(self, child):
        if child is not self._owned or not self._verified or child.poll() is not None:
            raise ExerciseError("Refusing to kill an unowned or unverified worker.")
        self._verified = False
        child.kill()  # POSIX SIGKILL on this owned Popen object only.
        if child.wait(timeout=_REAP_SECONDS) != -signal.SIGKILL:
            raise ExerciseError("Owned worker did not exit via SIGKILL.")


def sealed_fingerprint(bundle):
    """Only the fixed, synthetic lab files in our own detached prepare directory."""
    paths = [bundle / "pins.json"]
    for name in ("old", "new"):
        folder = bundle / name
        candidates = list((folder / "cache/server_passage_snapshots_v1").glob("*.wbsvec"))
        if len(candidates) != 1:
            raise ExerciseError("Expected one sealed snapshot for each synthetic generation.")
        paths.extend((folder / "synthetic.jsonl", candidates[0]))
    records = []
    for path in paths:
        info = path.stat()
        with path.open("rb") as file:
            records.append((info.st_ino, info.st_mtime_ns, file_digest(file, "sha256").hexdigest()))
    return tuple(records)


def refuse_corrupt(invalid, model, pins):
    with launch(invalid / "synthetic.jsonl", model, _BATCH, cache_dir=invalid / "cache",
                prepared_index=True, strict_pins=pins["new"]) as bad:
        wait_health(bad, _READY_SECONDS, rejected=True)
        # A failed Uvicorn lifespan is distinct from a SIGKILL, bind error,
        # and successful (but non-serving) exit.
        if bad[1].poll() != 3:
            raise ExerciseError("Corrupt candidate did not fail via server startup verification.")


def observe_outage(port):
    try:
        request(port, "/healthz")
    except ConnectionRefusedError:
        return
    raise ExerciseError("Expected observed connection refusal after reaping the owned worker.")


def run(model):
    if not sys.platform.startswith("linux"):
        raise ValueError("This POSIX SIGKILL recovery lab is Linux-only.")
    with TemporaryDirectory(prefix="wb-crash-recovery-") as scratch:
        directory = Path(scratch)
        bundle = directory / "sealed"
        bundle.mkdir(mode=0o700)
        prepare(bundle, model)
        _, pins = validated_bundle(bundle)
        before = sealed_fingerprint(bundle)
        bad = corrupt_copy(bundle / "new", directory, 2)
        options = {"cache_dir": bundle / "old/cache", "prepared_index": True, "strict_pins": pins["old"]}
        catalog = bundle / "old/synthetic.jsonl"

        with launch(catalog, model, _BATCH, **options) as initial:
            started = wait_health(initial, _READY_SECONDS)
            owner = OwnedCrashTarget(initial)
            reference = owner.fingerprint()
            refuse_corrupt(bad, model, pins)
            if owner.fingerprint() != reference:
                raise ExerciseError("Failed candidate disturbed the known-good worker.")
            signal_start = monotonic()
            owner.crash(initial[1])
            reaped = monotonic()
            observe_outage(owner.port)
            outage = monotonic()

        with launch(catalog, model, _BATCH, port=owner.port, **options) as restarted:
            if restarted[0] != owner.port or restarted[1] is owner._owned:
                raise ExerciseError("Expected a fresh worker on the exact private loopback endpoint.")
            wait_health(restarted, _READY_SECONDS)
            ready = monotonic()
            movie = probe(owner.port, 0)
            first_exact = monotonic()
            tv = probe(owner.port, 1)
            both_exact = monotonic()
            if (movie, tv) != reference or restarted[1].poll() is not None:
                raise ExerciseError("Recovery did not preserve exact typed Movie/TV payloads.")
        if sealed_fingerprint(bundle) != before:
            raise ExerciseError("Crash rehearsal changed the sealed inputs.")
    return {"synthetic_only": True, "rows_per_generation": 2, "expected_sigkill": True,
            "owned_child_reaped": True, "same_private_port": True, "connection_refusal_observed": True,
            "corrupt_next_refused": True, "exact_movie_tv_pair": True, "sealed_files_unchanged": True,
            "initial_ready_seconds": round(started, 3),
            "kill_to_reaped_ms": round((reaped - signal_start) * 1000, 3),
            "kill_to_observed_refusal_ms": round((outage - signal_start) * 1000, 3),
            "kill_to_restart_ready_ms": round((ready - signal_start) * 1000, 3),
            "kill_to_first_exact_reply_ms": round((first_exact - signal_start) * 1000, 3),
            "kill_to_verified_movie_tv_pair_ms": round((both_exact - signal_start) * 1000, 3),
            "resource_limit_enforced": False, "automatic_routing": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
        epilog="Local controlled timings only, not a public availability or failover guarantee.")
    parser.add_argument("--model-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = run(args.model_dir)
    except (ExerciseError, OSError, ValueError, subprocess.TimeoutExpired):
        print("Owned worker crash recovery QA failed before exact local verification.", file=sys.stderr)
        return 1
    print(json.dumps(report), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

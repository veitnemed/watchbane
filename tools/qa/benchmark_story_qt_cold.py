"""Measure Python callback gaps during an isolated, offline Qt E5 search.

Run each invocation in a new process. Measures worker phases after Python/Qt dependencies are imported.
Success output contains timings and hashes, not data.
Python timer delivery is not evidence of frozen native repainting.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import socket
from statistics import quantiles
import sys
from tempfile import TemporaryDirectory
from time import perf_counter
from unittest.mock import patch


def summarize(start, end, ticks, phases, *, threshold_ms=75):
    """Summarize gaps, including the end boundary before a final callback."""
    points = [start, *ticks, end]
    gaps = [(a, b) for a, b in zip(points, points[1:])]
    values = [(b - a) * 1000 for a, b in gaps]
    return {
        "elapsed_ms": round((end - start) * 1000, 2),
        "callbacks": len(ticks),
        "p95_callback_interval_ms": round(quantiles(values, n=20, method="inclusive")[18], 2) if len(values) > 1 else None,
        "max_callback_interval_ms": round(max(values), 2),
        "phases": [
            {"name": name, "offset_ms": round((a - start) * 1000, 2),
             "duration_ms": round((b - a) * 1000, 2)}
            for name, a, b in sorted(phases, key=lambda phase: phase[1])
        ],
        "long_gaps": [
            {"offset_ms": round((a - start) * 1000, 2), "duration_ms": round((b - a) * 1000, 2),
             "overlaps": [
                 {"name": name, "overlap_ms": round((min(b, t) - max(a, s)) * 1000, 2)}
                 for name, s, t in phases if max(a, s) < min(b, t)
             ]}
            for a, b in gaps if (b - a) * 1000 > threshold_ms
        ],
    }


def _file_digest(path):
    with path.open("rb") as stream:
        from hashlib import file_digest
        return file_digest(stream, "sha256").hexdigest()


def run(catalog, model, query):
    from tools.qa.isolation import apply_isolated_data_dir

    with TemporaryDirectory(prefix="watchbane-qt-cold-") as folder:
        apply_isolated_data_dir(Path(folder))
        from PyQt6.QtCore import QEventLoop, QTimer, Qt
        from PyQt6.QtNetwork import QNetworkAccessManager
        from PyQt6.QtWidgets import QApplication
        import onnxruntime as ort
        import requests
        import tokenizers
        from candidates import story_semantic
        from candidates.story_vector_cache import CachedPassageEncoder
        from desktop.story.view import StoryWorker
        from storage.runtime import ensure_runtime_data_layout

        ensure_runtime_data_layout()
        phases, ticks, attempted_network = [], [], []
        outcome = {}

        def measure(name, function):
            def timed(*args, **kwargs):
                start = perf_counter()
                try:
                    return function(*args, **kwargs)
                finally:
                    phases.append((name, start, perf_counter()))
            return timed

        class TimedTokenizer:
            from_file = staticmethod(measure("tokenizer_load", tokenizers.Tokenizer.from_file))

        def no_network(*args, **kwargs):
            attempted_network.append(True)
            raise RuntimeError("network is disabled for this offline probe")

        with ExitStack() as stack:
            for owner, name in (
                (socket.socket, "connect"), (socket.socket, "connect_ex"),
                (socket, "getaddrinfo"), (requests.sessions.Session, "request"),
                *((QNetworkAccessManager, name) for name in ("get", "post", "put", "head", "deleteResource", "sendCustomRequest")),
            ):
                stack.enter_context(patch.object(owner, name, no_network))
            for owner, key, replacement in (
                (ort, "InferenceSession", measure("ort_session", ort.InferenceSession)),
                (tokenizers, "Tokenizer", TimedTokenizer),
                (story_semantic, "artifact_sha256", measure("artifact_verification", story_semantic.artifact_sha256)),
                (story_semantic.LocalE5, "__init__", measure("model_initialization", story_semantic.LocalE5.__init__)),
                (CachedPassageEncoder, "encode", measure("encoding_and_cache", CachedPassageEncoder.encode)),
            ):
                stack.enter_context(patch.object(owner, key, replacement))

            app = QApplication([])
            loop = QEventLoop()
            worker = StoryWorker(query, None, model_dir=str(model), seed_path=catalog)

            def completed(response, _records, count):
                outcome.update(response=response, count=count)

            worker.completed.connect(completed)
            worker.finished.connect(loop.quit)
            timer = QTimer()
            timer.setTimerType(Qt.TimerType.PreciseTimer)
            timer.timeout.connect(lambda: ticks.append(perf_counter()))
            start = perf_counter()
            timer.start(16)
            worker.start()
            loop.exec()
            end = perf_counter()
            timer.stop()
            worker.wait()
            response = outcome.get("response")
            if attempted_network or response is None or not response.backend.endswith("fp32"):
                raise RuntimeError("offline FP32 story search did not complete")
            if not response.hits:
                raise RuntimeError("choose a valid plot cue that yields results")
            ids = [item.document.key for item in response.hits]
            result = summarize(start, end, ticks, phases)
            result.update(
                platform=platform.system(), architecture=platform.machine(), qt_platform=app.platformName(),
                ort=ort.__version__, titles=outcome["count"], network_attempts=len(attempted_network),
                catalog_sha256=_file_digest(catalog), ranking_sha256=sha256(json.dumps(ids).encode()).hexdigest(),
                timer_ms=16, logical_cpu_affinity=len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None,
            )
            return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, required=True, help="Approved local JSONL")
    parser.add_argument("--model-dir", type=Path, required=True, help="Pinned local FP32 E5")
    parser.add_argument("--query", required=True, help="Non-personal test plot cue")
    args = parser.parse_args()
    try:
        print(json.dumps(run(args.catalog.resolve(), args.model_dir.resolve(), args.query)))
    except (OSError, RuntimeError, ValueError) as error:
        print(f"Probe failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

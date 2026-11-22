import socket
import sys

import pytest

from tools.qa import measure_story_x86_5k as lab
from tools.qa.measure_story_lexical_capacity import make_documents


def sample(phase, proof):
    return {
        "rows": 5000, "fixture": "synthetic_qa_only", "density": "low", "mode": "prepared",
        "cache_phase": phase, "proof_of_cache_hit": proof, "child_peak_rss_kib": 100,
        "ordered_typed_results": [[["movie", f"tmdb:movie:{2147482000 + i}"] for i in range(5)] for _ in range(7)],
        "catalog_sha256": "a" * 64, "passage_snapshot_id": "b" * 64,
        "passage_snapshot_sha256": "c" * 64,
        "process_ready_seconds": 1.0, "first_http_ms": 2.0, "warm_samples": 21,
        "warm_p50_ms": 1.0, "warm_p95_ms": 2.0,
    }


def test_private_pair_and_drift():
    cold, restart = sample("cold", False), sample("restart", True)
    cold["private_future_field"] = "must not be reported"
    report = lab.verified_pair(cold, restart)
    assert "private_future_field" not in report["cold"]
    assert report["ordered_typed_top5_probes"] == 7
    assert "ordered_typed_results" not in report["cold"]
    restart["ordered_typed_results"][0].reverse()
    with pytest.raises(RuntimeError, match="changed identity or ordered"):
        lab.verified_pair(cold, restart)


@pytest.mark.parametrize("failure", ["proof_of_cache_hit", "catalog_sha256", "passage_snapshot_sha256", "passage_snapshot_id"])
def test_nonmatching_snapshot_refused(failure):
    cold, restart = sample("cold", False), sample("restart", True)
    restart[failure] = False if failure == "proof_of_cache_hit" else "0" * 64
    with pytest.raises(RuntimeError):
        lab.verified_pair(cold, restart)


def test_5k_generation_does_not_enable_other_sizes_or_density():
    with pytest.raises(ValueError):
        next(make_documents(5000, "low"))
    with pytest.raises(ValueError):
        next(make_documents(5000, "high", x86_5k_lab=True))
    assert len(list(make_documents(5000, "low", x86_5k_lab=True))) == 5000
    with pytest.raises(ValueError):
        next(make_documents(5001, "low", x86_5k_lab=True))


def test_loopback_only_guard(monkeypatch):
    events = []
    monkeypatch.setattr(lab.sys, "addaudithook", events.append)
    exec(lab._OFFLINE_GUARD, {})
    guard, = events
    guard("socket.getaddrinfo", ("localhost",))
    with pytest.raises(OSError, match="non-loopback"):
        guard("socket.getaddrinfo", ("example.invalid",))
    with socket.socket() as sock:
        guard("socket.connect", (sock, ("127.0.0.1", 1)))
        with pytest.raises(OSError, match="non-loopback"):
            guard("socket.bind", (sock, ("0.0.0.0", 1)))


@pytest.mark.parametrize(("field", "value"), [
    ("warm_samples", 20), ("process_ready_seconds", float("nan")), ("warm_p95_ms", 0),
    ("proof_of_cache_hit", 1),
])
def test_invalid_measurement_is_not_accepted(field, value):
    cold, restart = sample("cold", False), sample("restart", True)
    restart[field] = value
    with pytest.raises(RuntimeError, match="invalid x86 5K phase"):
        lab.verified_pair(cold, restart)


@pytest.mark.skipif(sys.platform != "linux", reason="requires Linux CPU affinity")
def test_controller_uses_private_cache_and_restores_affinity_on_failure(monkeypatch):
    captured = []
    affinity = []
    monkeypatch.setattr(lab.platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(lab.os, "sched_getaffinity", lambda _: {1, 3, 4})
    monkeypatch.setattr(lab.os, "sched_setaffinity", lambda _, cpus: affinity.append(cpus))

    def fake(name, model, cache, env):
        captured.append((name, cache, env))
        assert cache.is_dir() and cache.stat().st_mode & 0o777 == 0o700
        assert (cache.parent / "sitecustomize.py").read_text() == lab._OFFLINE_GUARD
        assert "TMDB_API_KEY" not in env
        if name == "restart":
            raise RuntimeError("phase refused")
        return sample("cold", False)

    monkeypatch.setattr(lab, "_run_phase", fake)
    with pytest.raises(RuntimeError, match="phase refused"):
        lab.run(None)
    assert [row[0] for row in captured] == ["cold", "restart"]
    assert captured[0][1] == captured[1][1]
    assert not captured[0][1].exists()
    assert affinity == [{1, 3}, {1, 3, 4}]

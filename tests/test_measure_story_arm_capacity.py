import json
from pathlib import Path

import pytest

pytest.importorskip("numpy")

from tools.qa import measure_story_arm_capacity as capacity
from candidates.story_seed_snapshot import load_seed_snapshot


def test_fixture_loads_typed_synthetic_rows_identically(tmp_path):
    first = tmp_path / "first.jsonl"
    second = tmp_path / "second.jsonl"
    a, probes_a = capacity.fixture(first, 1000, "low")
    b, probes_b = capacity.fixture(second, 1000, "low")
    assert a == b and probes_a == probes_b and first.read_bytes() == second.read_bytes()
    assert len(a) == len(load_seed_snapshot(first)) == 1000
    assert ("movie", "tmdb:movie:2147482000") in a
    assert ("tv", "tmdb:tv:2147482000") in b
    assert len(probes_a) == len(set(probes_a)) == 7


def captures(tmp_path):
    def report(mode):
        first_five = [["movie" if i % 2 == 0 else "tv",
                       f"tmdb:{'movie' if i % 2 == 0 else 'tv'}:{2147482000 + i // 2}"]
                      for i in range(5)]
        return [{"cgroup_limits": {"cpu_quota_us": 200000, "cpu_period_us": 100000,
                                   "memory_limit_bytes": 2 * 1024**3, "swap_limit_bytes": 0}},
                {"cgroup_usage": {"peak_bytes": 1024, "oom": 0, "oom_kill": 0,
                                  "oom_group_kill": 0, "within_limit_without_oom": True}},
                {"capacity": {"fixture": "synthetic_qa_only", "rows": 1000, "density": "low",
                              "mode": mode, "catalog_sha256": "1" * 64,
                              "process_ready_seconds": 1., "first_http_ms": 10.,
                              "warm_samples": 21, "warm_p50_ms": 5., "warm_p95_ms": 7.,
                              "ordered_typed_results": [list(first_five) for _ in range(7)]}}]
    return (tmp_path / "baseline.jsonl", tmp_path / "prepared.jsonl",
            report("baseline"), report("prepared"))


def dump(path: Path, values):
    path.write_text("".join(json.dumps(value) + "\n" for value in values))


def test_compare_accepts_same_typed_top5(capsys, tmp_path):
    a, b, x, y = captures(tmp_path)
    dump(a, x)
    dump(b, y)
    capacity.compare(a, b)
    assert json.loads(capsys.readouterr().out)["paired_typed_top5"] == 7


@pytest.mark.parametrize("bad", ["rank", "oom", "wrong_type", "digest", "missing"])
def test_compare_rejects_misleading_reports(tmp_path, bad):
    a, b, x, y = captures(tmp_path)
    sample = y[-1]["capacity"]
    if bad == "rank":
        sample["ordered_typed_results"][0].reverse()
    elif bad == "oom":
        y[1]["cgroup_usage"]["oom_kill"] = 1
    elif bad == "wrong_type":
        sample["ordered_typed_results"][0][0] = ["tv", "tmdb:movie:2147482000"]
    elif bad == "digest":
        sample["catalog_sha256"] = "2" * 64
    elif bad == "missing":
        y.pop()
    dump(a, x)
    dump(b, y)
    with pytest.raises(ValueError):
        capacity.compare(a, b)


def restart_captures(tmp_path):
    a, b, x, y = captures(tmp_path)
    for report, phase in ((x, "cold"), (y, "restart")):
        report[-1]["capacity"].update(mode="prepared", density="high", cache_phase=phase,
                                      proof_of_cache_hit=phase == "restart",
                                      passage_snapshot_id="a" * 64, passage_snapshot_sha256="b" * 64)
    return a, b, x, y


def test_compare_restart_requires_real_witness_and_same_contents(tmp_path, capsys):
    a, b, x, y = restart_captures(tmp_path)
    dump(a, x)
    dump(b, y)
    capacity.compare_restart(a, b)
    assert json.loads(capsys.readouterr().out)["cache_hit_proven"] is True
    y[-1]["capacity"]["proof_of_cache_hit"] = False
    dump(b, y)
    with pytest.raises(ValueError, match="proof"):
        capacity.compare_restart(a, b)
    y[-1]["capacity"]["proof_of_cache_hit"] = True
    y[-1]["capacity"]["passage_snapshot_sha256"] = "c" * 64
    dump(b, y)
    with pytest.raises(ValueError, match="preserve"):
        capacity.compare_restart(a, b)


def test_witness_requires_consumed_cache_and_no_startup_reencoding(tmp_path):
    from types import SimpleNamespace
    from tools.qa.serve_story_cache_hit import guard

    class Cache:
        def load(self, identity):
            return None if identity is None else matrix

    class Model:
        def encode(self, texts):
            return texts

    matrix = object()
    marker = tmp_path / "proof"
    sample_id = SimpleNamespace(fingerprint=lambda: bytes.fromhex("ab" * 32))
    load, encode, finished = guard(marker, Model, Cache)
    with pytest.raises(RuntimeError, match="encoding during"):
        encode(Model(), ["startup"])
    with pytest.raises(RuntimeError, match="valid matching"):
        load(Cache(), None)
    assert load(Cache(), sample_id) is matrix
    with pytest.raises(RuntimeError, match="encoding during"):
        encode(Model(), ["startup even after cache hit"])
    with pytest.raises(RuntimeError, match="did not use"):
        finished(SimpleNamespace(vectors=object()))
    assert not marker.exists()
    finished(SimpleNamespace(vectors=matrix))
    assert marker.read_text() == "ab" * 32
    assert encode(Model(), ["request"]) == ["request"]


def test_compare_requires_pressure_if_requested(tmp_path, capsys):
    a, b, x, y = restart_captures(tmp_path)
    dump(a, x)
    dump(b, y)
    with pytest.raises(ValueError, match="pressure"):
        capacity.compare_restart(a, b, require_pressure=True)
    pressure = {"passed": True, "within_deadline": True, "successful_order_mismatches": 0,
                "recovery_successes": 3, "counts": {"ok": 3, "busy_503": 15,
                                                     "unknown": 0, "rate_limited_429": 0}}
    y[-1]["capacity"]["synthetic_pressure"] = pressure
    dump(b, y)
    capacity.compare_restart(a, b, require_pressure=True)
    assert json.loads(capsys.readouterr().out)["pressure_proven"] is True
    pressure["counts"]["rate_limited_429"] = 1
    dump(b, y)
    with pytest.raises(ValueError, match="pressure"):
        capacity.compare_restart(a, b, require_pressure=True)


def test_2k_pair_keeps_distinct_readiness_budgets_and_exact_top5(tmp_path, capsys):
    a, b, x, y = restart_captures(tmp_path)
    for report, budget in ((x, 340), (y, 30)):
        report[-1]["capacity"].update(rows=2000, readiness_budget_seconds=budget)
    dump(a, x)
    dump(b, y)
    capacity.compare_restart(a, b, rows=2000)
    assert json.loads(capsys.readouterr().out)["rows"] == 2000

    with pytest.raises(ValueError, match="unexpected workload"):
        capacity.compare_restart(a, b)  # default remains the existing 1K gate

    y[-1]["capacity"]["process_ready_seconds"] = 30.01
    dump(b, y)
    with pytest.raises(ValueError, match="readiness budget"):
        capacity.compare_restart(a, b, rows=2000)

    y[-1]["capacity"]["process_ready_seconds"] = 29.99
    y[-1]["capacity"]["ordered_typed_results"][0].reverse()
    dump(b, y)
    with pytest.raises(ValueError, match="typed Top-5"):
        capacity.compare_restart(a, b, rows=2000)


def test_2k_readiness_timeout_remains_distinct_from_resource_failure(monkeypatch, capsys, tmp_path):
    from types import SimpleNamespace
    from tools.qa.exercise_story_handover import ReadinessTimeout

    monkeypatch.setattr(capacity, "platform", SimpleNamespace(system=lambda: "Linux", machine=lambda: "aarch64"))
    monkeypatch.setattr(capacity, "sys", SimpleNamespace(version_info=(3, 12, 16)))
    monkeypatch.setattr(capacity, "os", SimpleNamespace(geteuid=lambda: 1001))
    monkeypatch.setattr(capacity, "read_limits", lambda _root: {"cpu_quota_us": 200000})
    monkeypatch.setattr(capacity, "read_usage", lambda _root: {"oom": 0})
    def measure(*args, **options):
        assert options["readiness_timeout"] == 30
        raise ReadinessTimeout("startup deadline expired")
    monkeypatch.setattr(capacity, "measure", measure)
    with pytest.raises(ReadinessTimeout):
        capacity.run(tmp_path, 2000, "high", "prepared", cache_dir=tmp_path, cache_phase="restart")
    _, failure, usage = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert failure == {"capacity_failure": "readiness_timeout", "cache_phase": "restart",
                       "rows": 2000, "readiness_budget_seconds": 30}
    assert usage == {"cgroup_usage": {"oom": 0}}

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

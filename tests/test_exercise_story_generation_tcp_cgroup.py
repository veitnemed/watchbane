from types import SimpleNamespace

import pytest

from tools.qa import exercise_story_generation_tcp_cgroup as gate


@pytest.fixture
def fake_native(tmp_path, monkeypatch):
    root = tmp_path / "sys"
    root.mkdir()
    proc = tmp_path / "proc"
    (proc / "self").mkdir(parents=True)
    (proc / "self/cgroup").write_text("0::/\n")
    values = {"cgroup.controllers": "memory cpu", "cpu.max": "200000 100000",
              "memory.max": str(2 * 1024**3), "memory.swap.max": "0",
              "memory.peak": str(1024**3), "memory.current": "512",
              "memory.events": "max 0\noom 0\noom_kill 0\noom_group_kill 0\n"}
    for name, data in values.items():
        (root / name).write_text(data)
    monkeypatch.setattr(gate, "platform", SimpleNamespace(system=lambda: "Linux", machine=lambda: "aarch64"))
    monkeypatch.setattr(gate, "sys", SimpleNamespace(version_info=(3, 12, 16)))
    monkeypatch.setattr(gate.os, "geteuid", lambda: 1001)
    return root, proc


def outcome():
    return dict.fromkeys(gate._CONTROLLED, True) | {
        "rows": [1000, 1000], "verified_model_sessions": 1, "forbidden_startup_encodes": 0,
        "actual_query_calls": 11, "unpaused": {"attempted": 4, "old_success": 2, "errors": 1, "busy": 1}}


def test_native_gate_keeps_passive_errors_separate_from_controlled_and_memory(fake_native, monkeypatch):
    root, proc = fake_native
    async def rehearsal(_bundle, _model, *, scale):
        assert scale == 1000
        return outcome()
    monkeypatch.setattr(gate, "rehearse", rehearsal)
    report = gate.run(root, root, rows=1000, root=root, proc=proc)
    assert report["passed"] and "unpaused" not in report["controlled_switch_and_metadata"]
    assert report["passive_unpaused_observation"]["errors"] == 1
    assert report["passive_samples_not_sla"] and report["cgroup_usage"]["peak_bytes"] == 1024**3
    assert report["memory_current_before_bytes"] == report["memory_current_after_bytes"] == 512


def test_runtime_oom_cannot_pass_after_successful_controlled_probe(fake_native, monkeypatch):
    root, proc = fake_native
    async def rehearsal(_bundle, _model, *, scale):
        (root / "memory.events").write_text("max 1\noom 1\noom_kill 1\n")
        return outcome()
    monkeypatch.setattr(gate, "rehearse", rehearsal)
    report = gate.run(root, root, rows=1000, root=root, proc=proc)
    assert report["controlled_switch_and_metadata"]["rollback"]
    assert report["cgroup_usage"]["oom_kill"] == 1
    assert report["resource_failure"] == "oom_event" and not report["passed"]


def test_limits_and_fresh_namespace_are_required_before_rehearsal(fake_native, monkeypatch):
    root, proc = fake_native
    async def not_called(*_args, **_kwargs):
        pytest.fail("accepted invalid cgroup")
    monkeypatch.setattr(gate, "rehearse", not_called)
    (root / "memory.swap.max").write_text("1")
    with pytest.raises(RuntimeError, match="no cgroup swap"):
        gate.run(root, root, rows=1000, root=root, proc=proc)
    (proc / "self/cgroup").write_text("0::/outside\n")
    with pytest.raises(ValueError, match="private"):
        gate.run(root, root, rows=1000, root=root, proc=proc)

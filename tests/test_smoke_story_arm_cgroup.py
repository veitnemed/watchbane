from pathlib import Path

import pytest

from tools.qa import smoke_story_arm_cgroup as lab


@pytest.fixture
def controls(tmp_path):
    values = {
        "cgroup.controllers": "cpu memory",
        "cpu.max": "200000 100000",
        "memory.max": str(2 * 1024**3),
        "memory.swap.max": "0",
        "memory.peak": "400000000",
        "memory.events": "oom 0\noom_kill 0\noom_group_kill 0\n",
    }
    for key, value in values.items():
        (tmp_path / key).write_text(value)
    return tmp_path


@pytest.mark.parametrize(("name", "bad"), [
    ("cpu.max", "max 100000"), ("cpu.max", "150000 100000"),
    ("memory.max", "max"), ("memory.swap.max", "100"),
])
def test_effective_controls_fail_closed(controls, name, bad):
    assert lab.read_limits(controls)["memory_limit_bytes"] == 2 * 1024**3
    (controls / name).write_text(bad)
    with pytest.raises(RuntimeError):
        lab.read_limits(controls)


@pytest.mark.parametrize(("name", "bad"), [
    ("memory.peak", str(2 * 1024**3 + 1)), ("memory.peak", "0"),
    ("memory.events", "oom 1\noom_kill 0"), ("memory.events", "oom 0\noom_kill 1"),
    ("memory.events", "oom 0\noom_kill 0\noom_group_kill 1"),
])
def test_peak_and_kernel_oom_events_are_observed(controls, name, bad):
    assert lab.read_usage(controls)["within_limit_without_oom"]
    (controls / name).write_text(bad)
    assert not lab.read_usage(controls)["within_limit_without_oom"]


def test_usage_is_reported_even_after_synthetic_probe_fails(controls, monkeypatch, capsys):
    monkeypatch.setattr(lab.platform, "system", lambda: "Linux")
    monkeypatch.setattr(lab.platform, "machine", lambda: "aarch64")
    monkeypatch.setattr(lab.sys, "version_info", (3, 12, 16))
    monkeypatch.setattr(lab.os, "geteuid", lambda: 65532)

    def unavailable(model_dir, *, require_native_arm):
        assert model_dir == Path("fixture") and require_native_arm
        raise RuntimeError("fixture service failure")

    monkeypatch.setattr(lab, "smoke", unavailable)
    with pytest.raises(RuntimeError, match="fixture service failure"):
        lab.run(Path("fixture"), root=controls)
    report = capsys.readouterr().out
    assert "cgroup_limits" in report and "cgroup_usage" in report
    assert "synthetic_loopback_probe" not in report


def test_limit_pressure_is_reported_separately_from_oom(controls):
    (controls / "memory.events").write_text("max 3\noom 0\noom_kill 0\n")
    usage = lab.read_usage(controls)
    assert usage["within_limit_without_oom"] and usage["memory_max_events"] == 3

import signal

import pytest

from tools.qa import exercise_story_child_crash as crash
from tools.qa import exercise_story_handover as handover


class Process:
    def __init__(self, kill_status=-signal.SIGKILL):
        self.status = None
        self.kill_status = kill_status
        self.signals = 0

    def poll(self):
        return self.status

    def kill(self):
        self.signals += 1
        self.status = self.kill_status

    def wait(self, *, timeout):
        assert timeout == 3
        return self.status


def fake_verified(monkeypatch):
    def request(_port, path, body=None):
        if path == "/healthz":
            return {"ready": True}
        return {}
    monkeypatch.setattr(crash, "request", request)
    monkeypatch.setattr(crash, "probe", lambda _port, ordinal: crash.expected_generation("old", ordinal))


def test_crash_refuses_foreign_or_unverified_process(monkeypatch):
    fake_verified(monkeypatch)
    owned, other = Process(), Process()
    target = crash.OwnedCrashTarget((12345, owned))
    with pytest.raises(crash.ExerciseError, match="unowned or unverified"):
        target.crash(owned)
    assert owned.signals == 0
    assert target.fingerprint() == tuple(crash.expected_generation("old", i) for i in range(2))
    with pytest.raises(crash.ExerciseError, match="unowned or unverified"):
        target.crash(other)
    assert other.signals == 0
    target.crash(owned)
    assert owned.signals == 1 and owned.poll() == -signal.SIGKILL
    with pytest.raises(crash.ExerciseError, match="unowned or unverified"):
        target.crash(owned)


def test_failed_fingerprint_revokes_prior_readiness(monkeypatch):
    fake_verified(monkeypatch)
    owned = Process()
    target = crash.OwnedCrashTarget((12345, owned))
    target.fingerprint()
    monkeypatch.setattr(crash, "probe", lambda *_: (_ for _ in ()).throw(crash.ExerciseError("bad marker")))
    with pytest.raises(crash.ExerciseError, match="bad marker"):
        target.fingerprint()
    with pytest.raises(crash.ExerciseError, match="unowned or unverified"):
        target.crash(owned)
    assert owned.signals == 0


def test_wrong_termination_status_or_still_live_endpoint_fails(monkeypatch):
    fake_verified(monkeypatch)
    owned = Process(kill_status=0)
    target = crash.OwnedCrashTarget((12345, owned))
    target.fingerprint()
    with pytest.raises(crash.ExerciseError, match="did not exit via SIGKILL"):
        target.crash(owned)
    with pytest.raises(crash.ExerciseError, match="Expected observed connection refusal"):
        crash.observe_outage(12345)
    def refused(*_args, **_kwargs):
        raise ConnectionRefusedError
    monkeypatch.setattr(crash, "request", refused)
    assert crash.observe_outage(12345) is None


@pytest.mark.parametrize("invalid", [0, -1, 65536, True, "12345"])
def test_explicit_port_invalid_before_spawning(monkeypatch, invalid):
    monkeypatch.setattr(handover.subprocess, "Popen", lambda *_a, **_k: pytest.fail("started a process"))
    with pytest.raises(ValueError, match="explicit IPv4 loopback port"):
        with handover.launch("catalog", "model", 4, port=invalid):
            pytest.fail("unexpected successful launch")


def test_corrupt_candidate_does_not_count_as_refused_on_unrelated_signal(monkeypatch, tmp_path):
    from contextlib import contextmanager
    bad = Process()
    bad.status = -signal.SIGKILL

    @contextmanager
    def unowned_bad_fixture(*_args, **_kwargs):
        yield 23991, bad

    monkeypatch.setattr(crash, "launch", unowned_bad_fixture)
    with pytest.raises(crash.ExerciseError, match="did not fail via server startup"):
        crash.refuse_corrupt(tmp_path, tmp_path, {"new": ["a" * 64, "b" * 64]})
    assert bad.signals == 0


def test_same_explicit_port_reused_without_another_allocator(monkeypatch):
    spawned = []
    def fake_spawn(argv, **_kwargs):
        spawned.append(argv)
        done = Process()
        done.status = 0
        return done

    monkeypatch.setattr(handover.subprocess, "Popen", fake_spawn)
    monkeypatch.setattr(handover.socket, "socket", lambda *_a: pytest.fail("allocated another port"))
    with handover.launch("catalog", "model", 4, port=23456) as endpoint:
        assert endpoint[0] == 23456
    assert spawned[0][spawned[0].index("--port") + 1] == "23456"

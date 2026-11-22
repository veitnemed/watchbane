from contextlib import contextmanager
from hashlib import sha256
import json
import os
from types import SimpleNamespace

import pytest

from tools.qa import exercise_story_joint_cgroup as joint
from tools.qa.exercise_story_handover import ReadinessTimeout

pytestmark = pytest.mark.skipif(os.name != "posix", reason="private POSIX QA bundle")


@pytest.fixture
def bundle(tmp_path):
    work = tmp_path / "bundle"
    work.mkdir(mode=0o700)
    (work / "pins.json").write_text(json.dumps({
        name: [sha256(joint.fixture_bytes(name)).hexdigest(), "c" * 64] for name in ("old", "new")
    }))
    return work


@pytest.fixture
def dry_loopback(monkeypatch):
    state = {"broken_tv": False, "new_timeout": False, "already_ready": False, "requests": []}

    class FakeProcess:
        def __init__(self, pid):
            self.pid = pid
        def poll(self):
            return None

    @contextmanager
    def launch(catalog, _model, batch, **options):
        assert batch == 4 and options["prepared_index"] is True
        generation = catalog.parent.name
        assert options["strict_pins"] == [sha256(joint.fixture_bytes(generation)).hexdigest(), "c" * 64]
        yield (100 if generation == "old" else 101, FakeProcess(200 if generation == "old" else 201))

    def wait(server, seconds, *, on_not_ready=None):
        assert seconds == 30
        if server[0] == 101:
            assert on_not_ready is not None
            on_not_ready()
            on_not_ready()
            if state["new_timeout"]:
                raise ReadinessTimeout("fixture")
        return 1.0

    def request(port, route, raw=None):
        if route == "/healthz":
            assert port == 101
            return {"ready": state["already_ready"]}
        assert route == "/v1/search"
        query = json.loads(raw)["query"]
        generation = "old" if port == 100 else "new"
        index = int(query.startswith("сериал"))
        state["requests"].append((generation, index))
        fixture = joint.fixture(generation)[index]
        row = {key: value for key, value in fixture.items() if key != "tmdb_id"}
        row.update(id=f"tmdb:{fixture['media_type']}:{fixture['tmdb_id']}", evidence=fixture["overview"])
        if index == 1 and state["broken_tv"] and generation == "new":
            row["title"] = "unexpected TV mutation"
        return {"source": "tmdb", "results": [row]}

    monkeypatch.setattr(joint, "launch", launch)
    monkeypatch.setattr(joint, "wait_health", wait)
    monkeypatch.setattr(joint, "request", request)
    return state


def test_uncapped_handover_requires_valid_payload_and_old_serves_before_candidate(bundle, dry_loopback):
    report = joint.exercise(bundle, bundle, capped=False)
    assert report["passed"] and report["old_while_new_unready"] == 2
    assert not report["shared_cgroup_enforced"]
    assert dry_loopback["requests"][-4:] == [("new", 0), ("new", 1), ("old", 0), ("old", 1)]
    dry_loopback["broken_tv"] = True
    report = joint.exercise(bundle, bundle, capped=False)
    assert not report["passed"] and report["failure_phase"] == "verified_overlap"


def test_candidate_timeout_reports_old_still_serving(bundle, dry_loopback):
    dry_loopback["new_timeout"] = True
    report = joint.exercise(bundle, bundle, capped=False)
    assert not report["passed"]
    assert report["old_while_new_unready"] == 2
    assert report["failure"] == "readiness_timeout" and report["failure_phase"] == "stage_new"


def test_native_gate_checks_same_live_group_and_never_passes_after_oom(bundle, dry_loopback, tmp_path, monkeypatch):
    import sys
    platform = SimpleNamespace(system=lambda: "Linux", machine=lambda: "aarch64")
    monkeypatch.setattr(joint, "platform", platform)
    monkeypatch.setattr(joint, "sys", SimpleNamespace(version_info=(3, 12, 16), stderr=sys.stderr))
    monkeypatch.setattr(joint.os, "geteuid", lambda: 1000)
    bundle.chmod(0o700)
    monkeypatch.setattr(joint, "private_directory", lambda p: p)
    monkeypatch.setattr(joint, "read_limits", lambda _root: {"cpu": 2})
    normal = {"oom": 0, "oom_kill": 0, "oom_group_kill": 0, "memory_max_events": 0,
              "within_limit_without_oom": True}
    observations = iter((normal, normal, normal | {"oom": 1, "within_limit_without_oom": False}))
    monkeypatch.setattr(joint, "read_usage", lambda _root: next(observations))
    (tmp_path / "memory.current").write_text("1024")
    for pid in ("self", "200", "201"):
        entry = tmp_path / pid
        entry.mkdir()
        (entry / "cgroup").write_text("0::/\n")
    report = joint.exercise(bundle, bundle, capped=True, root=tmp_path, proc=tmp_path)
    assert report["both_children_same_cgroup"] and report["switched_and_rolled_back"]
    assert not report["passed"] and report["resource_failure"] == "oom_event"


def test_only_health_without_verified_old_pre_readiness_is_rejected(bundle, dry_loopback):
    dry_loopback["already_ready"] = True
    report = joint.exercise(bundle, bundle, capped=False)
    assert not report["passed"] and report["old_while_new_unready"] == 0
    assert report["failure_phase"] == "stage_new"


def test_manifest_cannot_substitute_old_catalog_for_new(bundle):
    metadata = bundle / "pins.json"
    pins = json.loads(metadata.read_text())
    pins["new"] = pins["old"]
    metadata.write_text(json.dumps(pins))
    with pytest.raises(ValueError, match="bundle pins"):
        joint.validated_bundle(bundle)

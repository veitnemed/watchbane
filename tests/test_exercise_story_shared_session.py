import asyncio
from hashlib import sha256
import os
import socket

import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("fastapi")

from candidates import story_semantic
from tools.qa import exercise_story_joint_cgroup as joint
from tools.qa import exercise_story_shared_session as shared
from web import story_api


pytestmark = pytest.mark.skipif(os.name != "posix", reason="POSIX private fixture prebuild")


@pytest.fixture
def detached_bundle(tmp_path, monkeypatch):
    model_dir = tmp_path / "model"
    (model_dir / "onnx").mkdir(parents=True)
    (model_dir / "onnx/model.onnx").write_bytes(b"fixture only; actual QA checks admitted weights")
    bundle = tmp_path / "bundle"
    bundle.mkdir(mode=0o700)
    models = []

    class FakeLocalE5:
        variant, cache_identity = "fp32", "pinned fixture runtime"

        def __init__(self, directory):
            assert directory == model_dir
            models.append(self)
            self.calls = []

        def encode(self, texts, prefix="passage: ", **_kwargs):
            self.calls.append((prefix, len(texts)))
            return np.ones((len(texts), 384), dtype=np.float32)

    monkeypatch.setattr(story_semantic, "LocalE5", FakeLocalE5)
    monkeypatch.setattr(story_api, "LocalE5", FakeLocalE5)
    assert joint.prepare(bundle, model_dir)["rows_per_generation"] == 2
    models.clear()
    return bundle, model_dir, models, FakeLocalE5


def test_shared_rehearsal_uses_only_one_engine_model_and_no_network(detached_bundle, monkeypatch):
    bundle, model_dir, models, factory = detached_bundle
    _, pins = joint.validated_bundle(bundle)
    before = {path:(sha256(path.read_bytes()).hexdigest(), path.stat().st_ino)
              for path in bundle.rglob("*") if path.is_file()}

    def forbidden(*_args, **_kwargs):
        raise AssertionError("ASGI rehearsal attempted a socket action")

    for method in ("bind", "listen", "connect", "connect_ex"):
        monkeypatch.setattr(socket.socket, method, forbidden)

    report = {}
    samples = iter((44, 55))
    asyncio.run(shared.rehearse(bundle, model_dir, pins, 2, report, model_factory=factory,
                                 sample_memory=lambda: next(samples)))
    assert len(models) == report["verified_model_sessions"] == 1
    assert report["both_verified_indices_live_one_model_session"]
    assert report["old_verified_during_controlled_staging"] and report["inflight_old_request_preserved"]
    assert report["tampered_candidate_refused_and_old_unchanged"]
    assert report["changed_marker_and_unchanged_tv_rollback"]
    assert report["forbidden_startup_encodes"] == 0 and report["actual_query_calls"] == 11
    assert report["old_only_memory_current_bytes"] == 44 and report["dual_indices_memory_current_bytes"] == 55
    assert before == {path:(sha256(path.read_bytes()).hexdigest(), path.stat().st_ino)
                      for path in bundle.rglob("*") if path.is_file()}


def test_wrong_pinned_candidate_never_materializes(detached_bundle):
    bundle, model_dir, _, factory = detached_bundle
    _, pins = joint.validated_bundle(bundle)
    encoder = shared.SharedProbeEncoder(factory(model_dir))
    catalog, digest = pins["new"]
    with pytest.raises(ValueError, match="exact byte verification"):
        shared.build(bundle / "new", (catalog, "0" * 64), 2, encoder)
    assert not encoder.model.calls

import asyncio
import os

import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("fastapi")
pytest.importorskip("uvicorn")

from candidates import story_semantic
from tools.qa import exercise_story_generation_retention as retention
from web import story_api


@pytest.mark.skipif(os.name != "posix", reason="Private POSIX synthetic prebuild")
def test_repeat_activation_drains_before_next_stage_and_reloads_from_disk(tmp_path, monkeypatch):
    bundle, model = tmp_path / "bundle", tmp_path / "model"
    bundle.mkdir(mode=0o700)
    (model / "onnx").mkdir(parents=True)
    (model / "onnx/model.onnx").write_bytes(b"synthetic fixture")
    built = 0

    class FixtureE5:
        variant, cache_identity = "fp32", "generation-retention-fixture"

        def __init__(self, path):
            nonlocal built
            assert path == model
            built += 1

        def encode(self, texts, **kwargs):
            return np.ones((len(texts), 384), dtype=np.float32)

    monkeypatch.setattr(story_semantic, "LocalE5", FixtureE5)
    monkeypatch.setattr(story_api, "LocalE5", FixtureE5)
    assert retention.prepare(bundle, model) == {"synthetic_prebuilt": [2, 3, 4], "reused_from_prior": [1, 2]}
    built = 0
    before = retention._artifacts(bundle)
    try:
        report = asyncio.run(retention.rehearse(bundle, model, model_factory=FixtureE5))
    except PermissionError:
        pytest.skip("Private loopback socket not permitted by execution environment")
    assert built == report["verified_model_sessions"] == 1
    assert report["observed_peak_live_generation_refs"] == 2
    assert report["premature_c_refused"] and report["corrupted_c_refused"]
    assert report["stale_c_refused_before_activation_and_after_rollback"]
    assert report["old_a_captured_then_drained_before_c"] and report["old_b_payload_coherent_after_c"]
    assert report["rollback_c_to_b"] and report["sealed_a_reload_while_b_active_ms"] >= 0
    assert report["query_encodes"] == 14
    assert report["artifacts_unchanged"] and retention._artifacts(bundle) == before

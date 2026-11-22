import asyncio
from hashlib import sha256
import os

import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("fastapi")
pytest.importorskip("uvicorn")

from candidates import story_semantic
from tools.qa import exercise_story_generation_tcp as tcp
from web import story_api


@pytest.mark.skipif(os.name != "posix", reason="Private POSIX synthetic prebuild")
def test_exact_generation_bundles_and_same_listener(tmp_path, monkeypatch):
    bundle, model = tmp_path / "bundle", tmp_path / "model"
    bundle.mkdir(mode=0o700)
    (model / "onnx").mkdir(parents=True)
    (model / "onnx/model.onnx").write_bytes(b"synthetic fixture")
    calls = []

    class FixtureE5:
        variant, cache_identity = "fp32", "generation-tcp-fixture"

        def __init__(self, path):
            assert path == model
            calls.append(self)

        def encode(self, texts, **kwargs):
            return np.ones((len(texts), 384), dtype=np.float32)

    monkeypatch.setattr(story_semantic, "LocalE5", FixtureE5)
    monkeypatch.setattr(story_api, "LocalE5", FixtureE5)
    assert tcp.prepare(bundle, model)["rows"] == [2, 3]
    calls.clear()
    before = {file: (sha256(file.read_bytes()).digest(), file.stat().st_ino)
              for file in bundle.rglob("*") if file.is_file()}
    try:
        result = asyncio.run(tcp.rehearse(bundle, model, model_factory=FixtureE5))
    except PermissionError:
        pytest.skip("Private loopback socket not permitted by execution environment")
    assert len(calls) == result["verified_model_sessions"] == 1
    assert result["strict_artwork_index_outcome"] and result["one_tcp_listener"] and result["inflight_busy"]
    assert result["controlled_staging_old_ready"] and result["stale_capture_old"] and result["rollback"]
    assert result["corruption_refused"] and result["forbidden_startup_encodes"] == 0
    assert result["actual_query_calls"] == 12
    assert result["unpaused_stage_and_old_reply_total_ms"] >= 0
    assert before == {file: (sha256(file.read_bytes()).digest(), file.stat().st_ino)
                      for file in bundle.rglob("*") if file.is_file()}

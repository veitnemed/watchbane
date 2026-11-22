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
@pytest.mark.parametrize("scale,counts", [(2, [2, 3]), (1000, [1000, 1000])])
def test_exact_generation_bundles_and_same_listener(tmp_path, monkeypatch, scale, counts):
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
    prepared = tcp.prepare(bundle, model, scale=scale)
    assert prepared["rows"] == counts
    if scale == 1000:
        assert (prepared["reused_rows"], prepared["encoded_rows"]) == (998, 2)
        assert [sum(row["media_type"] == "movie" for row in tcp.rows(name, scale))
                for name in ("old", "new")] == [500, 501]
    with pytest.raises(ValueError, match="exact synthetic"):
        tcp.read_pins(bundle, scale=1000 if scale == 2 else 2)
    calls.clear()
    before = {file: (sha256(file.read_bytes()).digest(), file.stat().st_ino)
              for file in bundle.rglob("*") if file.is_file()}
    try:
        result = asyncio.run(tcp.rehearse(bundle, model, scale=scale, model_factory=FixtureE5))
    except PermissionError:
        pytest.skip("Private loopback socket not permitted by execution environment")
    assert len(calls) == result["verified_model_sessions"] == 1
    assert result["strict_artwork_index_outcome"] and result["one_tcp_listener"] and result["inflight_busy"]
    assert result["controlled_staging_old_ready"] and result["stale_capture_old"] and result["rollback"]
    assert result["corruption_refused"] and result["forbidden_startup_encodes"] == 0
    samples = result["unpaused"]
    assert 0 <= samples["old_success_while_candidate_still_building"] <= samples["old_success"]
    assert samples["attempted"] == samples["old_success"] + samples["busy"] + samples["errors"] <= 16
    assert result["actual_query_calls"] == 11 + samples["old_success"]
    assert samples["observation_ms"] >= 0
    assert before == {file: (sha256(file.read_bytes()).digest(), file.stat().st_ino)
                      for file in bundle.rglob("*") if file.is_file()}

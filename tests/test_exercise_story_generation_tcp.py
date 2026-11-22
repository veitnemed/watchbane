import asyncio
from hashlib import sha256
from threading import Event
import os

import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("fastapi")
pytest.importorskip("uvicorn")

from candidates import story_semantic
from tools.qa import exercise_story_generation_tcp as tcp
from web import story_api


@pytest.mark.skipif(os.name != "posix", reason="Private POSIX synthetic prebuild")
@pytest.mark.parametrize("scale,counts,lost", [
    (2, [2, 3], None), (1000, [1000, 1000], None),
    (2, [2, 3], "after"), (2, [2, 3], "before"),
], ids=("small", "1k", "post-encode-timeout", "pre-encode-transport"))
def test_exact_generation_bundles_and_same_listener(tmp_path, monkeypatch, scale, counts, lost):
    if lost:
        original_post = tcp.post
        original_build = tcp.build
        seen = Event()

        def build(*args, **kwargs):
            result = original_build(*args, **kwargs)
            if args[2] == "new" and args[0] == bundle / "new" and kwargs.get("barrier") is None:
                assert seen.wait(3)
            return result

        def post(*args, **kwargs):
            if lost == "before" and kwargs.get("expected_status", 200) is None:
                seen.set()
                raise ConnectionRefusedError("Synthetic transport failure before sending")
            result = original_post(*args, **kwargs)
            if kwargs.get("expected_status", 200) is None:
                tcp.verify(result, "old", 0, scale=scale)
                seen.set()
                raise TimeoutError("Synthetic loss after exact underlying HTTP success")
            return result

        monkeypatch.setattr(tcp, "build", build)
        monkeypatch.setattr(tcp, "post", post)
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
    assert result["actual_query_calls"] == 11 + samples["encoded_attempts"]
    assert samples["errors"] == samples["deadline"] + samples["transport_errors"]
    assert samples["encoded_attempts"] == samples["old_success"] + samples["encoded_without_observed_success"]
    if lost == "after":
        assert samples["attempted"] == samples["deadline"] == samples["encoded_without_observed_success"] == 1
        assert samples["old_success"] == samples["transport_errors"] == 0
    elif lost == "before":
        assert samples["attempted"] == samples["transport_errors"] == 1
        assert samples["encoded_attempts"] == samples["deadline"] == samples["old_success"] == 0
    assert samples["observation_ms"] >= 0
    assert before == {file: (sha256(file.read_bytes()).digest(), file.stat().st_ino)
                      for file in bundle.rglob("*") if file.is_file()}


@pytest.mark.parametrize("outcomes,calls", [
    ({1: "deadline"}, [1, 1]),
    ({1: "deadline"}, [2]),
    ({1: "busy"}, [1]),
    ({1: "success"}, []),
])
def test_reconciliation_refuses_impossible_ledgers(outcomes, calls):
    from types import SimpleNamespace

    encoder = SimpleNamespace(sample_calls=calls, controlled_calls=11, query_calls=11 + len(calls))
    with pytest.raises(ValueError, match="query encode accounting"):
        tcp.reconcile_unpaused({}, outcomes, encoder)


def test_sampler_does_not_count_malformed_http_as_transport(monkeypatch):
    def broken(*args, **kwargs):
        raise ValueError("Invalid negotiated contract")

    monkeypatch.setattr(tcp, "post", broken)
    with pytest.raises(ValueError, match="Invalid negotiated contract"):
        asyncio.run(tcp.sample_unpaused(0, Event(), scale=2))

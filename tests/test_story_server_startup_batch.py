"""Startup routing and cache boundary checks, not model parity measurements."""
from collections import OrderedDict
import json
from threading import RLock
from types import SimpleNamespace

import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient

from candidates.story_semantic import LocalE5, validate_e5_batch_size
from web import story_api


def _catalog(path, overview, identifier=1):
    path.write_text(json.dumps({"media_type": "movie", "tmdb_id": identifier, "title": "Тайтл",
                                "overview": overview, "year": 2020, "language": "ru-RU"}) + "\n",
                    encoding="utf-8")


def test_encode_dispatches_no_more_than_configured_batch():
    calls = []
    def tokenize(texts):
        calls.append(len(texts))
        item = SimpleNamespace(ids=[1, 2], attention_mask=[1, 1], type_ids=[0, 0])
        return [item] * len(texts)
    encoder = LocalE5.__new__(LocalE5)
    encoder.np, encoder.cache, encoder.lock = np, OrderedDict(), RLock()
    encoder.tokenizer = SimpleNamespace(encode_batch=tokenize)
    encoder.session = SimpleNamespace(get_inputs=lambda: [SimpleNamespace(name="input_ids")],
                                      run=lambda _, d: [np.ones((*d["input_ids"].shape, 384), dtype=np.float32)])
    assert encoder.encode([str(i) for i in range(9)], batch_size=4).shape == (9, 384)
    assert calls == [4, 4, 1]
    calls.clear()
    encoder.encode([str(i) for i in range(9, 27)])
    assert calls == [16, 2]


@pytest.mark.parametrize("value", [0, 17, True, 2.0])
def test_batch_rejects_invalid_values(value):
    with pytest.raises(ValueError):
        validate_e5_batch_size(value)
    with pytest.raises(ValueError):
        story_api.create_app(None, None, startup_batch_size=value)


def test_http_startup_size_only_and_cache_incompatible_with_default(tmp_path, monkeypatch):
    calls = []
    class Encoder:
        variant, cache_identity = "fixture", "verified fixture"
        def __init__(self, _path):
            pass
        def encode(self, texts, prefix="passage: ", **options):
            calls.append((prefix, options.copy()))
            return np.ones((len(texts), 384), dtype=np.float32)
    monkeypatch.setattr(story_api, "LocalE5", Encoder)
    current, old, cache = tmp_path / "want.jsonl", tmp_path / "old.jsonl", tmp_path / "cache"
    _catalog(current, "Врач помогает раненому.")
    _catalog(old, "Врач помогает раненому.")
    # Make current and previous exact digests differ while keeping the passage.
    old.write_bytes(old.read_bytes().replace(b'"year": 2020', b'"year": 2021'))
    story_api.build_engine(old, tmp_path, cache_dir=cache)
    with TestClient(story_api.create_app(current, tmp_path, startup_batch_size=4)) as client:
        assert client.post("/v1/search", json={"query": "врач"}).status_code == 200
    assert calls[-3:] == [("passage: ", {"batch_size": 4}), ("query: ", {}), ("passage: ", {})]
    calls.clear()
    story_api.build_engine(current, tmp_path, cache_dir=cache, previous_catalog=old, startup_batch_size=4)
    # Default-size old snapshot is incompatible even though the row is identical.
    assert calls == [("passage: ", {"batch_size": 4})]
    assert len(list(cache.rglob("*.wbsvec"))) == 2
    calls.clear()
    story_api.build_engine(current, tmp_path, cache_dir=cache, startup_batch_size=4)
    assert calls == []
    story_api.build_engine(current, tmp_path, cache_dir=cache, startup_batch_size=16)
    assert calls == [("passage: ", {})]
    assert len(list(cache.rglob("*.wbsvec"))) == 3

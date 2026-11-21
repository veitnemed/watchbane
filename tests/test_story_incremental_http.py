"""Server only: explicitly reuse an already verified prior catalog generation."""
import json

import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient

from web import story_api


def _write(path, entries):
    path.write_text("".join(json.dumps({
        "media_type": "movie", "year": 2023, "tmdb_id": key, "title": f"Film {key}",
        "overview": overview, "language": "ru-RU",
    }) + "\n" for key, overview in entries), encoding="utf-8")


@pytest.fixture
def encoder(monkeypatch):
    class Fake:
        cache_identity = "verified pinned fixture"
        variant = "fixture"
        batches = []
        loads = 0

        def __init__(self, _path):
            Fake.loads += 1

        def encode(self, texts, prefix="passage: ", **_kwargs):
            Fake.batches.append((tuple(texts), prefix))
            return np.ones((len(texts), 384), dtype=np.float32)
    monkeypatch.setattr(story_api, "LocalE5", Fake)
    return Fake


def test_previous_catalog_reuses_passages_and_exact_hit_does_not_open_previous(tmp_path, monkeypatch, encoder):
    previous, current, cache = (tmp_path / name for name in ("previous.jsonl", "current.jsonl", "cache"))
    kept = "Врач помогает раненому."
    changed = "Капитан покидает корабль."
    _write(previous, [(1, kept), (2, "Капитан строит корабль.")])
    _write(current, [(2, changed), (1, kept)])
    old_bytes = previous.read_bytes()
    story_api.build_engine(previous, tmp_path, cache_dir=cache)
    assert len(list(cache.rglob("*.wbsvec"))) == 1
    app = story_api.create_app(current, tmp_path, cache_dir=cache, prepared_index=True, previous_catalog=previous)
    with TestClient(app) as client:
        response = client.post("/v1/search", headers={"Watchbane-Search-Outcome": "1"}, json={"query": "врач"})
        assert response.status_code == 200 and response.json()["outcome"] is not None
    assert encoder.batches[1] == ((changed,), "passage: ")
    assert len(list(cache.rglob("*.wbsvec"))) == 2 and previous.read_bytes() == old_bytes

    original = story_api.load_seed_snapshot_with_digest
    def current_only(path):
        assert path == current, "do not open previous on an exact current hit"
        return original(path)
    monkeypatch.setattr(story_api, "load_seed_snapshot_with_digest", current_only)
    encoder.batches.clear()
    story_api.build_engine(current, tmp_path, cache_dir=cache, previous_catalog=previous)
    assert not encoder.batches and encoder.loads == 3


@pytest.mark.parametrize("valid_previous", [False, True])
def test_missing_previous_snapshot_or_cache_rebuilds_current(tmp_path, encoder, valid_previous):
    previous, current, cache = (tmp_path / name for name in ("old.jsonl", "new.jsonl", "cache"))
    if valid_previous:
        _write(previous, [(1, "Врач помогает раненому.")])
    else:
        previous.write_text("invalid json", encoding="utf-8")
    _write(current, [(1, "Врач помогает раненому.")])
    story_api.build_engine(current, tmp_path, cache_dir=cache, previous_catalog=previous)
    assert encoder.batches == [(("Врач помогает раненому.",), "passage: ")]
    assert len(list(cache.rglob("*.wbsvec"))) == 1


def test_previous_catalog_requires_explicit_cache(tmp_path):
    with pytest.raises(ValueError, match="explicit cache"):
        story_api.create_app(tmp_path, tmp_path, previous_catalog=tmp_path)
    with pytest.raises(SystemExit) as error:
        story_api.main(["--catalog", str(tmp_path), "--model-dir", str(tmp_path),
                        "--previous-catalog", str(tmp_path)])
    assert error.value.code == 2

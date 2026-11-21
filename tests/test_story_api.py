from threading import Event, Thread

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient

from candidates.story_search import StoryDocument, StoryHit, StoryResponse
from web.story_api import build_engine, create_app


class Engine:
    def __init__(self):
        self.calls = []

    def search(self, query, *, limit):
        self.calls.append((query, limit))
        doc = StoryDocument("tmdb:movie:27", "Пример", "Пилот возвращается домой.", "movie", "TMDb", year=2001)
        return StoryResponse((StoryHit(doc, 0.1, doc.overview),))


def test_post_returns_typed_id_russian_description_and_builds_once(tmp_path):
    catalog, model = tmp_path / "catalog", tmp_path / "model"
    builds, engine = [], Engine()

    def factory(*args):
        builds.append(args)
        return engine

    with TestClient(create_app(catalog, model, engine_factory=factory)) as client:
        assert client.get("/healthz").json() == {"ready": True}
        for _ in range(2):
            reply = client.post("/v1/search", json={"query": " пилот ", "limit": 2})
            assert reply.status_code == 200
            assert reply.headers["cache-control"] == "no-store"
            assert reply.json() == {"source": "tmdb", "results": [{
                "id": "tmdb:movie:27", "media_type": "movie", "title": "Пример", "year": 2001,
                "overview": "Пилот возвращается домой.", "evidence": "Пилот возвращается домой.", "language": "ru-RU",
            }]}
    assert builds == [(catalog, model)]
    assert engine.calls == [("пилот", 2)] * 2


def test_invalid_bodies_never_echo_or_reach_engine(tmp_path):
    engine = Engine()
    with TestClient(create_app(tmp_path, tmp_path, engine_factory=lambda *_: engine)) as client:
        for kwargs, status in (
            ({"content": "private-text"}, 415),
            ({"json": {"query": "private-text", "limit": True}}, 400),
            ({"json": {"query": "private-text", "extra": "secret"}}, 400),
            ({"json": {"query": "x" * 601}}, 400),
            ({"content": b'{"query":"\\ud800"}', "headers": {"content-type": "application/json"}}, 400),
            ({"content": b"x" * 8193, "headers": {"content-type": "application/json"}}, 413),
        ):
            response = client.post("/v1/search", **kwargs)
            assert response.status_code == status
            assert response.headers["cache-control"] == "no-store"
            assert "private-text" not in response.text and "secret" not in response.text
    assert engine.calls == []


def test_build_uses_ru_snapshot_only_and_fails_before_model_on_empty(tmp_path, monkeypatch):
    import json
    import web.story_api as api

    catalog = tmp_path / "catalog.jsonl"
    base = {"media_type": "movie", "title": "История", "overview": "Геолог спускается в пещеру."}
    en = base | {"tmdb_id": 4, "language": "en-US"}
    ru = base | {"tmdb_id": 4, "media_type": "tv", "language": "ru-RU"}
    catalog.write_text(json.dumps(en) + "\n", encoding="utf-8")
    loads = []
    monkeypatch.setattr(api, "LocalE5", lambda path: loads.append(path) or "verified engine")
    monkeypatch.setattr(api, "SemanticStorySearch", lambda docs, model: (docs, model))
    with pytest.raises(ValueError, match="no eligible Russian"):
        build_engine(catalog, tmp_path)
    assert not loads

    catalog.write_text(json.dumps(en) + "\n" + json.dumps(ru) + "\n", encoding="utf-8")
    documents, model = build_engine(catalog, tmp_path)
    assert model == "verified engine" and loads == [tmp_path]
    assert [doc.key for doc in documents] == ["tmdb:tv:4"]


def test_busy_and_engine_error_are_safe(tmp_path, caplog):
    entered, release = Event(), Event()
    def broken_search(query, *, limit):
        entered.set()
        assert release.wait(5)
        raise RuntimeError(query)
    engine = Engine()
    engine.search = broken_search
    responses = []
    with TestClient(create_app(tmp_path, tmp_path, engine_factory=lambda *_: engine)) as client:
        first = Thread(target=lambda: responses.append(client.post("/v1/search", json={"query": "private-query"})))
        first.start()
        try:
            assert entered.wait(5)
            busy = client.post("/v1/search", json={"query": "другой запрос"})
            assert busy.status_code == 503
            assert busy.headers["cache-control"] == "no-store"
            assert busy.json() == {"detail": "search_busy"}
        finally:
            release.set()
            first.join(5)
        assert not first.is_alive()
    assert responses[0].headers["cache-control"] == "no-store"
    assert responses[0].json() == {"detail": "search_unavailable"}
    assert "private-query" not in caplog.text


def test_optional_passage_cache_restart_replacement_and_failed_write(tmp_path, monkeypatch):
    import json
    import os

    np = pytest.importorskip("numpy")
    import web.story_api as api

    catalog, cache = tmp_path / "catalog.jsonl", tmp_path / "cache"
    overview = "Альпинист возвращается домой и встречает проводника."
    def write(title):
        row = {"media_type": "movie", "title": title, "overview": overview,
               "tmdb_id": 42, "language": "ru-RU", "year": 2024}
        catalog.write_text(json.dumps(row) + "\n", encoding="utf-8")
    write("Один")

    models = []
    class DeterministicEncoder:
        cache_identity, variant = "verified fixture model", "fixture"
        def __init__(self, path):
            self.calls = []
            models.append(self)
        def encode(self, texts, prefix="passage: ", **_kwargs):
            self.calls.append((tuple(texts), prefix))
            matrix = np.zeros((len(texts), 384), dtype=np.float32)
            matrix[:, 0] = 1
            return matrix

    monkeypatch.setattr(api, "LocalE5", DeterministicEncoder)
    def run(directory=None, title="Один"):
        with TestClient(api.create_app(catalog, tmp_path, cache_dir=directory)) as client:
            result = client.post("/v1/search", json={"query": "альпинист возвращается"}).json()
            assert result["results"][0]["id"] == "tmdb:movie:42"
            assert result["results"][0]["title"] == title
        return models[-1].calls

    calls = run()
    assert calls[0] == ((overview,), "passage: ") and not cache.exists()
    assert run(cache) == calls
    generated = list(cache.rglob("*.wbsvec"))
    assert len(generated) == 1
    verified = generated[0].read_bytes()
    assert run(cache) == calls[1:]  # New LocalE5, no initial passage re-encoding.
    assert any(prefix == "query: " for _, prefix in calls[1:])
    assert any(prefix == "passage: " for _, prefix in calls[1:])  # Evidence still delegates.
    assert generated[0].read_bytes() == verified

    generated[0].write_bytes(verified[:-1])
    assert run(cache) == calls
    assert generated[0].read_bytes() == verified

    # Same passage and typed ID, same file size and mtime, but new catalog bytes.
    original = catalog.stat()
    write("Иной")
    os.utime(catalog, ns=(original.st_atime_ns, original.st_mtime_ns))
    assert catalog.stat().st_size == original.st_size
    assert run(cache, "Иной") == calls
    assert len(list(cache.rglob("*.wbsvec"))) == 2

    unwritable = tmp_path / "not-a-directory"
    unwritable.write_text("leave me alone", encoding="utf-8")
    assert run(unwritable, "Иной") == calls
    assert unwritable.read_text(encoding="utf-8") == "leave me alone"
    assert len(models) == 6

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

"""Synthetic QA only: no provider source, existing profile or downloadable assets."""
from dataclasses import replace
from hashlib import sha256
import json

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("numpy")

from tools.qa.story_multilingual_loopback import NonAdultReview, create_mixed_qa_app, project_mixed_documents
from web.story_api import _load_documents, create_app
from web.story_catalog_multilingual import FORMAT

_RUSSIAN = "Кондитер наследует пекарню и учится печь хлеб."
_ENGLISH = "An astronaut is stranded on Mars and grows potatoes to survive alone."
_QUERY = "Астронавт застрял на Марсе."


def _write(path, *rows):
    payload = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows).encode()
    path.write_bytes(payload)
    return sha256(payload).hexdigest()


def _row(kind, identifier, title, synopsis, locale="en-US"):
    return {
        "id": f"tmdb:{kind}:{identifier}", "media_type": kind, "tmdb_id": identifier,
        "title": title, "overview": synopsis, "year": 2016, "synopsis_locale": locale,
        "original_language": "en",
        "evidence": {"source": "provider_translation_record", "provider_locale": locale,
                     "synopsis_sha256": sha256(synopsis.encode()).hexdigest()},
    }


@pytest.fixture
def snapshots(tmp_path):
    baseline = tmp_path / "russian.jsonl"
    operator = tmp_path / "extra.jsonl"
    _write(baseline, {"media_type": "movie", "tmdb_id": 7, "title": "Фикстура: пекарня",
                      "overview": _RUSSIAN, "language": "ru-RU"},
                     {"media_type": "movie", "tmdb_id": 8, "title": "Заблокированная фикстура",
                      "overview": "Графический секс.", "language": "ru-RU"})
    english = _row("tv", 7, "Fixture: astronaut", _ENGLISH)
    pin = _write(operator, {"format": FORMAT}, english,
                 _row("movie", 7, "Ignored change", "Replacement description."),
                 _row("movie", 8, "Ignored alternative", "Alternate description."),
                 _row("movie", 9, "Ignored unreviewed", "Unreviewed description."),
                 _row("tv", 10, "Неявное расширение", "Не добавлять.", "ru-RU"))
    review = NonAdultReview(pin, english["id"], "en-US", english["evidence"]["synopsis_sha256"], True)
    return baseline, operator, pin, review


def test_adds_only_independently_reviewed_typed_english_and_never_replaces_ru(snapshots):
    baseline, operator, pin, review = snapshots
    old, old_digest = _load_documents(baseline)
    mixed, locales, digest = project_mixed_documents(baseline, operator, pin, [review])
    assert digest != old_digest and mixed[:len(old)] == tuple(old)
    assert [doc.key for doc in mixed] == ["tmdb:movie:7", "tmdb:tv:7"]
    assert mixed[0].overview == _RUSSIAN and mixed[1].overview == _ENGLISH
    assert locales == {"tmdb:movie:7": "ru-RU", "tmdb:tv:7": "en-US"}


def test_review_rejects_missing_different_or_blocked_candidates(snapshots):
    baseline, operator, pin, review = snapshots
    for altered in (
        [],
        [replace(review, reviewed_non_adult=False)],
        [replace(review, operator_sha256="a" * 64)],
        [replace(review, synopsis_locale="en-GB")],
        [replace(review, synopsis_sha256="c" * 64)],
        [replace(review, key="tmdb:movie:7")],
        [replace(review, key="tmdb:movie:8")],
        [review, review],
    ):
        with pytest.raises(ValueError):
            project_mixed_documents(baseline, operator, pin, altered)
    blocked = _row("tv", 7, "Blocked", "Graphic sex.")
    pin = _write(operator, {"format": FORMAT}, blocked)
    with pytest.raises(ValueError, match="text safety"):
        project_mixed_documents(baseline, operator, pin, [
            replace(review, operator_sha256=pin, synopsis_sha256=blocked["evidence"]["synopsis_sha256"]),
        ])


def test_legacy_unchanged_qa_explicit_language_and_distinct_cache(tmp_path, snapshots, monkeypatch):
    np = pytest.importorskip("numpy")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient
    from web import story_api

    class FakeE5:
        variant = "synthetic"
        cache_identity = "fixture-cache-id"
        startups = []

        def __init__(self, path):
            pass

        def encode(self, texts, prefix="passage: ", **kwargs):
            if prefix == "passage: " and ("batch_size" in kwargs or len(texts) > 1):
                self.startups.append(tuple(texts))
            result = np.zeros((len(texts), 384), dtype=np.float32)
            for i, item in enumerate(texts):
                result[i, 1 if item == _ENGLISH or prefix == "query: " else 0] = 1
            return result

    monkeypatch.setattr(story_api, "LocalE5", FakeE5)
    baseline, operator, pin, review = snapshots
    cache = tmp_path / "cache"
    with TestClient(create_app(baseline, tmp_path, cache_dir=cache)) as legacy:
        reply = legacy.post("/v1/search", json={"query": _QUERY})
        assert reply.status_code == 200
        assert reply.json()["results"][0]["language"] == "ru-RU"
        assert reply.json()["results"][0]["id"] == "tmdb:movie:7"
        assert legacy.post("/qa/v1/search", json={"query": _QUERY}).status_code == 404
    old_files = {file: file.read_bytes() for file in cache.rglob("*.wbsvec")}

    def mixed():
        return create_mixed_qa_app(baseline=baseline, operator_catalog=operator,
                                  operator_sha256=pin, reviews=[review], model_dir=tmp_path,
                                  cache_dir=cache, encoder_factory=FakeE5)

    for _ in range(2):
        with TestClient(mixed(), client=("127.0.0.1", 9696)) as client:
            reply = client.post("/qa/v1/search", json={"query": _QUERY})
            assert reply.status_code == 200 and reply.headers["cache-control"] == "no-store"
            assert client.post("/v1/search", json={"query": _QUERY}).status_code == 404
            assert reply.json()["mode"] == "operator_multilingual_qa"
            assert [(r["id"], r["language"]) for r in reply.json()["results"]] == [
                ("tmdb:tv:7", "en-US"), ("tmdb:movie:7", "ru-RU"),
            ]
    assert FakeE5.startups == [(_RUSSIAN, _ENGLISH)]
    new_files = {file: file.read_bytes() for file in cache.rglob("*.wbsvec")}
    mixed_files = set(new_files) - set(old_files)
    assert len(old_files) == len(mixed_files) == 1
    assert all(new_files[path] == previous for path, previous in old_files.items())
    assert all("mixed_qa_v1" in path.parts for path in mixed_files)
    with TestClient(mixed(), client=("192.0.2.1", 9696)) as nonloopback:
        reply = nonloopback.post("/qa/v1/search", json={"query": _QUERY})
        assert reply.status_code == 403 and reply.headers["cache-control"] == "no-store"


def _install_locale_probe_adapter(app, requests):
    """Test-only wire bridge; real inference and all card data stay in the lab app."""
    from fastapi import Request
    from fastapi.responses import JSONResponse

    @app.middleware("http")
    async def adapt(request: Request, call_next):
        versions = request.headers.getlist("Watchbane-Search-Locale")
        requests.append((request.method, request.scope["path"], versions))
        if request.method != "POST" or request.scope["path"] != "/v1/search":
            return await call_next(request)
        if versions != ["1"]:
            return await call_next(request)  # The actual lab app has no legacy route.
        request.scope.update(path="/qa/v1/search", raw_path=b"/qa/v1/search")
        response = await call_next(request)
        if response.status_code != 200:
            return response
        encoded = b"".join([part async for part in response.body_iterator])
        result = json.loads(encoded)
        assert result.pop("mode") == "operator_multilingual_qa"
        # The QA route doesn't serialize year/evidence. Supply only the
        # protocol's explicit absent values, never derived result fields.
        for row in result["results"]:
            row.update(year=None, evidence="")
        return JSONResponse(result, headers={"Watchbane-Search-Locale": "1", "Cache-Control": "no-store"})


def test_fp32_http_mixed_lane_optional(snapshots, tmp_path):
    """Run with explicit WATCHBANE_QA_MODEL_DIR pointing to pinned local weights."""
    import os
    from pathlib import Path

    source = os.environ.get("WATCHBANE_QA_MODEL_DIR")
    if not source:
        pytest.skip("Pinned local FP32 model is needed")
    model = Path(source)
    if not (model / "onnx/model.onnx").is_file():
        pytest.fail("Expected portable FP32 ONNX weights")

    from contextlib import contextmanager
    from http.client import HTTPConnection
    import socket
    from threading import Thread
    import time

    uvicorn = pytest.importorskip("uvicorn")
    pytest.importorskip("onnxruntime")
    baseline, operator, pin, review = snapshots
    cache = tmp_path / "fp32cache"

    @contextmanager
    def run(app):
        server = uvicorn.Server(uvicorn.Config(app, proxy_headers=False, access_log=False, log_level="error"))
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            thread = Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
            thread.start()
            try:
                deadline = time.monotonic() + 30
                while not server.started and thread.is_alive() and time.monotonic() < deadline:
                    time.sleep(.01)
                assert server.started, "Local smoke server did not start"
                yield listener.getsockname()[1]
            finally:
                server.should_exit = True
                thread.join(10)
                assert not thread.is_alive(), "Local smoke server did not stop"

    def search(port, route, status=200):
        conn = HTTPConnection("127.0.0.1", port, timeout=5)
        try:
            conn.request("POST", route, body=json.dumps({"query": _QUERY, "limit": 5}),
                         headers={"Content-Type": "application/json"})
            response = conn.getresponse()
            assert response.status == status
            return json.loads(response.read())
        finally:
            conn.close()

    with run(create_app(baseline, model, cache_dir=cache)) as port:
        old = search(port, "/v1/search")
        assert [(x["id"], x["language"]) for x in old["results"]] == [("tmdb:movie:7", "ru-RU")]
    old_files = {path: path.read_bytes() for path in cache.rglob("*.wbsvec")}
    from desktop.story.online_client import OnlineStoryError, search_online

    for _ in range(2):
        lab = create_mixed_qa_app(baseline=baseline, operator_catalog=operator,
                                  operator_sha256=pin, reviews=[review], model_dir=model, cache_dir=cache)
        transport_requests = []
        _install_locale_probe_adapter(lab, transport_requests)
        with run(lab) as port:
            result = search(port, "/qa/v1/search")
            search(port, "/v1/search", status=404)
            existing = [("POST", "/qa/v1/search", []), ("POST", "/v1/search", [])]
            assert transport_requests == existing
            with pytest.raises(OnlineStoryError, match="not authorized"):
                search_online(_QUERY, port=port, consent=False, with_locale=True)
            assert transport_requests == existing  # no new HTTP exchange at all
            assert [(x["id"], x["language"]) for x in result["results"]][:2] == [
                ("tmdb:tv:7", "en-US"), ("tmdb:movie:7", "ru-RU"),
            ]
            adapted = search_online(_QUERY, port=port, consent=True, with_locale=True)
            assert transport_requests == existing + [("POST", "/v1/search", ["1"])]
            assert [(r.id, r.media_type, r.synopsis_locale, r.title, r.overview) for r in adapted] == [
                (row["id"], row["media_type"], row["language"], row["title"], row["overview"])
                for row in result["results"]
            ]
            assert all(r.year is None and r.evidence == "" for r in adapted)
    actual_files = {path: path.read_bytes() for path in cache.rglob("*.wbsvec")}
    assert len(old_files) == 1 and len(actual_files) == 2
    assert all(actual_files[path] == raw for path, raw in old_files.items())
    with run(create_app(baseline, model, cache_dir=cache)) as port:
        assert search(port, "/v1/search") == old

import json

import pytest

from candidates.story_search import StoryHit, StoryResponse
from desktop.story import online_client as client

from test_story_online_client import Response, hit, transport


HEADER = "Watchbane-Search-Artwork"
OUTCOME = "Watchbane-Search-Outcome"


def test_server_metadata_is_opt_in_sparse_typed_and_ranking_independent(tmp_path, monkeypatch):
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient
    from web import story_api

    catalog = tmp_path / "seed.jsonl"
    base = {"title": "Fixture", "overview": "Test plot", "year": 2020, "language": "ru-RU"}
    rows = [
        base | {"media_type": "movie", "tmdb_id": 7, "poster_path": "/movie-A.webp"},
        base | {"media_type": "tv", "tmdb_id": 7, "poster_path": "/tv-B.jpg"},
        base | {"media_type": "tv", "tmdb_id": 8, "poster_path": "//site.invalid/private.jpg"},
        base | {"media_type": "movie", "tmdb_id": 9},
    ]
    catalog.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    calls = []

    class Engine:
        def __init__(self, documents, _encoder):
            self.documents = documents

        def search(self, _query, *, limit):
            return StoryResponse(tuple(StoryHit(doc, 1.0, "") for doc in self.documents[:limit]))

    read = story_api.load_seed_snapshot_with_digest

    def tracked_read(path):
        calls.append(path)
        return read(path)

    monkeypatch.setattr(story_api, "load_seed_snapshot_with_digest", tracked_read)
    monkeypatch.setattr(story_api, "SemanticStorySearch", Engine)
    monkeypatch.setattr(story_api, "LocalE5", lambda _: object())

    with TestClient(story_api.create_app(catalog, tmp_path, artwork_metadata=True)) as api:
        query = {"query": "Fixture"}
        old = api.post("/v1/search", json=query)
        outcome = api.post("/v1/search", json=query, headers={OUTCOME: "1"})
        artwork = api.post("/v1/search", json=query, headers={HEADER: "1"})
        both = api.post("/v1/search", json=query, headers={OUTCOME: "1", HEADER: "1"})
        expected = {"tmdb:movie:7": "/movie-A.webp", "tmdb:tv:7": "/tv-B.jpg"}
        assert set(old.json()) == {"source", "results"}
        assert outcome.json() == old.json() | {"outcome": {"state": "candidates", "reason": "possible_local_results"}}
        assert artwork.json() == old.json() | {"artwork": expected}
        assert both.json() == outcome.json() | {"artwork": expected}
        assert HEADER not in old.headers and HEADER not in outcome.headers
        assert both.headers[HEADER] == artwork.headers[HEADER] == "1"
        assert both.headers["cache-control"] == "no-store"
        for invalid in ({HEADER: "2"}, [(HEADER, "1"), (HEADER, "1")]):
            response = api.post("/v1/search", json=query, headers=invalid)
            assert response.status_code == 400 and HEADER not in response.headers
        assert calls == [catalog]  # no second filesystem read to obtain artwork
    with TestClient(story_api.create_app(catalog, tmp_path)) as configured_default:
        assert configured_default.post("/v1/search", json=query, headers={HEADER: "1"}).json()["artwork"] == {}


def test_client_handoff_keeps_typed_paths_and_missing_is_none(transport):
    connection, calls, _ = transport
    raw = json.dumps({"source": "tmdb", "results": [hit(), hit("tv")],
                      "artwork": {"tmdb:tv:27": "/tv-only.jpg"}}).encode()
    connection.reply = Response(raw, **{HEADER: "1"})
    results = client.search_online("plot", consent=True, with_artwork=True)
    assert [r.poster_path for r in results] == [None, "/tv-only.jpg"]
    assert [r.id for r in results] == ["tmdb:movie:27", "tmdb:tv:27"]
    assert calls[2][3][HEADER] == "1"
    assert [call[0] for call in calls] == ["create", "connect", "POST", "close"]


@pytest.mark.parametrize("path", [None, "/x.jpeg", "/x/evil.jpg", "//host.jpg", "https://host/x.jpg", "/x.jpg?z",
                                 "/x%2Ey.jpg", "/x\\name.jpg", "/x.jpg\n", "/а.jpg", "/" + "x" * 129 + ".jpg"])
def test_client_rejects_invalid_provider_path_without_retransmission(transport, path):
    connection, calls, _ = transport
    raw = json.dumps({"source": "tmdb", "results": [hit()], "artwork": {"tmdb:movie:27": path}}).encode()
    connection.reply = Response(raw, **{HEADER: "1"})
    with pytest.raises(client.OnlineStoryError, match="Invalid response"):
        client.search_online("plot", consent=True, with_artwork=True)
    assert [call[0] for call in calls].count("POST") == 1


@pytest.mark.parametrize("scenario", ["unexpected-id", "missing-echo", "legacy-client", "missing-map"])
def test_client_requires_exact_negotiated_shape(transport, scenario):
    connection, _, _ = transport
    with_artwork = scenario != "legacy-client"
    headers = {} if scenario == "missing-echo" else {HEADER: "1"}
    body = {"source": "tmdb", "results": [hit()]}
    if scenario != "missing-map":
        body["artwork"] = {"tmdb:tv:27" if scenario == "unexpected-id" else "tmdb:movie:27": "/valid.jpg"}
    connection.reply = Response(json.dumps(body).encode(), **headers)
    with pytest.raises(client.OnlineStoryError, match="Invalid response"):
        client.search_online("plot", consent=True, with_artwork=with_artwork)

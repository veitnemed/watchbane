"""Negotiated counts describe one running index, never the complete TMDb."""
import json

import pytest

from candidates.story_search import StoryDocument, StoryHit, StoryResponse
from desktop.story import online_client as client


_HEADER = "Watchbane-Search-Index"
_HIT = {"id": "tmdb:movie:27", "media_type": "movie", "title": "Пример", "year": 2001,
        "overview": "Пилот возвращается домой.", "evidence": "Пилот возвращается домой.", "language": "ru-RU"}
_INDEX = {"total": 3, "movies": 2, "tv": 1}


def test_index_negotiation_uses_engine_not_results_and_preserves_legacy(tmp_path):
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient
    from web.story_api import create_app

    class Engine:
        documents = (StoryDocument("tmdb:movie:27", "Пример", "Пилот возвращается домой.", "movie", "TMDb", year=2001),
                     StoryDocument("tmdb:tv:27", "Тёзка", "Семья ищет новый дом.", "tv", "TMDb"),
                     StoryDocument("tmdb:movie:28", "Вторая", "Группа учёных исследует пещеру.", "movie", "TMDb"))

        def search(self, query, *, limit):
            doc = self.documents[0]
            return StoryResponse(()) if query == "не найдено" else StoryResponse((StoryHit(doc, .1, doc.overview),))

    request = {"query": "Пилот", "limit": 1}
    with TestClient(create_app(tmp_path, tmp_path, engine_factory=lambda *_: Engine())) as legacy:
        no_index = legacy.post("/v1/search", json=request)
        disabled = legacy.post("/v1/search", json=request, headers={_HEADER: "1"})
    assert disabled.status_code == 503 and _HEADER not in disabled.headers
    expected = {"source": "tmdb", "results": [_HIT]}
    assert no_index.json() == expected and _HEADER not in no_index.headers

    with TestClient(create_app(tmp_path, tmp_path, engine_factory=lambda *_: Engine(),
                               index_metadata=True)) as server:
        assert server.post("/v1/search", json=request).json() == expected
        response = server.post("/v1/search", json=request, headers={_HEADER: "1"})
        assert response.json() == expected | {"index": _INDEX}
        assert response.headers[_HEADER] == "1" and _HEADER in response.headers["Vary"]
        assert response.headers["cache-control"] == "no-store"
        combined = server.post("/v1/search", json={"query": "не найдено"}, headers={
            _HEADER: "1", "Watchbane-Search-Artwork": "1", "Watchbane-Search-Outcome": "1",
        })
        assert combined.json() == {"source": "tmdb", "results": [], "artwork": {}, "index": _INDEX,
                                   "outcome": {"state": "clarification", "reason": "no_candidates"}}
        for headers in ({_HEADER: "2"}, [(_HEADER, "1"), (_HEADER, "1")]):
            assert server.post("/v1/search", json=request, headers=headers).status_code == 400


@pytest.mark.parametrize("invalid", [
    {}, {"total": 0, "movies": 0, "tv": 0}, {"total": True, "movies": 1, "tv": 0},
    {"total": 2, "movies": 1, "tv": 0}, {"total": 1, "movies": -1, "tv": 2},
    {"total": 20001, "movies": 20001, "tv": 0}, {"total": 1, "movies": 0, "tv": 1},
    {"total": "1", "movies": 1, "tv": 0}, {"total": 1, "movies": 1, "tv": 0.0},
    {"total": 1, "movies": 1, "tv": 0, "whole_tmdb": True},
])
def test_invalid_counts_fail_closed(invalid):
    raw = json.dumps({"source": "tmdb", "results": [_HIT], "index": invalid}).encode()
    with pytest.raises(client.OnlineStoryError, match="Invalid response"):
        client._parse(raw, 5, with_index=True)


def test_valid_counts_cannot_leak_into_legacy_client():
    raw = json.dumps({"source": "tmdb", "results": [_HIT], "index": _INDEX}).encode()
    result = client._parse(raw, 5, with_index=True)
    assert result.index == client.OnlineStoryIndex(3, 2, 1)
    assert len(result.result) == 1
    with pytest.raises(client.OnlineStoryError, match="Invalid response"):
        client._parse(raw, 5)

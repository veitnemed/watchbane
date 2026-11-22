import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient

from candidates.story_search import StoryDocument, StoryResponse
from candidates.story_semantic import SemanticStorySearch
from web.story_api import create_app


HEADER = "Watchbane-Search-Outcome"


class Encoder:
    variant = "synthetic"

    def encode(self, texts, **kwargs):
        import numpy as np

        return np.ones((len(texts), 2), dtype=np.float32)


def test_negotiated_hits_keep_exact_legacy_order_and_payload(tmp_path):
    documents = (
        StoryDocument("tmdb:movie:22", "Кино", "Геолог изучает пещеру.", "movie", "TMDb"),
        StoryDocument("tmdb:movie:12", "Дорога", "Команда идёт через тайгу.", "movie", "TMDb"),
    )
    engine = SemanticStorySearch(documents, Encoder())
    with TestClient(create_app(tmp_path, tmp_path, engine_factory=lambda *_: engine)) as client:
        legacy = client.post("/v1/search", json={"query": "геолог"})
        opt_in = client.post("/v1/search", json={"query": "геолог"}, headers={HEADER: "1"})
    assert legacy.status_code == opt_in.status_code == 200
    assert HEADER not in legacy.headers and opt_in.headers[HEADER] == "1"
    assert set(legacy.json()) == {"source", "results"} and len(legacy.json()["results"]) == 2
    assert opt_in.json() == legacy.json() | {
        "outcome": {"state": "candidates", "reason": "possible_local_results"}
    }
    for response in (legacy, opt_in):
        assert response.headers["Vary"] == f"{HEADER}, Watchbane-Search-Artwork"
        assert response.headers["Cache-Control"] == "no-store"


@pytest.mark.parametrize(("query", "state", "reason"), [
    ("как настроить роутер", "scope_refusal", "explicit_non_film_request"),
    ("фильм без войны", "clarification", "unsupported_exclusion"),
    ("и в", "clarification", "need_plot_detail"),
    ("сериал про геолога", "clarification", "no_eligible_catalog_entries"),
])
def test_real_query_routes_return_codes_only_when_negotiated(tmp_path, query, state, reason):
    movie = StoryDocument("tmdb:movie:22", "Кино", "Геолог изучает пещеру.", "movie", "TMDb")
    engine = SemanticStorySearch((movie,), Encoder())
    with TestClient(create_app(tmp_path, tmp_path, engine_factory=lambda *_: engine)) as client:
        legacy = client.post("/v1/search", json={"query": query})
        opted = client.post("/v1/search", json={"query": query}, headers={HEADER: "1"})
    assert legacy.json() == {"source": "tmdb", "results": []}
    assert opted.json() == legacy.json() | {"outcome": {"state": state, "reason": reason}}
    if reason != "no_eligible_catalog_entries":
        assert engine.search(query).reason is None  # local desktop unchanged


def test_unknown_version_and_unknown_engine_reason_never_echo_private_text(tmp_path):
    class Engine:
        def search(self, query, *, limit):
            return StoryResponse((), notice=query, reason=query)

    with TestClient(create_app(tmp_path, tmp_path, engine_factory=lambda *_: Engine())) as client:
        for bad_headers in ({HEADER: "2"}, [(HEADER, "1"), (HEADER, "1")]):
            invalid = client.post("/v1/search", json={"query": "private"}, headers=bad_headers)
            assert invalid.status_code == 400
            assert invalid.json() == {"detail": "unsupported_search_outcome_version"}
            assert HEADER not in invalid.headers
            assert invalid.headers["cache-control"] == "no-store"
            assert invalid.headers["vary"] == f"{HEADER}, Watchbane-Search-Artwork"
        empty = client.post("/v1/search", json={"query": "private"}, headers={HEADER: "1"})
        assert empty.json()["outcome"] == {"state": "clarification", "reason": "no_candidates"}
        assert "private" not in empty.text


def test_opt_in_engine_error_is_not_a_clarification(tmp_path):
    class Engine:
        def search(self, query, *, limit):
            raise RuntimeError(query)

    with TestClient(create_app(tmp_path, tmp_path, engine_factory=lambda *_: Engine())) as client:
        failure = client.post("/v1/search", json={"query": "unlogged"}, headers={HEADER: "1"})
    assert failure.status_code == 503
    assert failure.json() == {"detail": "search_unavailable"}
    assert HEADER not in failure.headers
    assert failure.headers["cache-control"] == "no-store"

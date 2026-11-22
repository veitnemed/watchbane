"""Exact RRF integration edge cases for both production retrieval strategies."""
import pytest

np = pytest.importorskip("numpy")

from candidates.story_lexical import LexicalIndex
from candidates.story_search import StoryDocument
from candidates.story_semantic import SemanticStorySearch
from web.story_retrieval_index import PreparedRetrievalIndex


class ControlledEncoder:
    variant = "fixture"

    def __init__(self, scores):
        self.scores = scores

    def encode(self, texts, prefix="passage: ", **_kwargs):
        if prefix == "query: ":
            return np.ones((len(texts), 1), dtype=np.float32)
        return np.array([[self.scores[text]] for text in texts], dtype=np.float32)


def _doc(kind, identifier, year, overview):
    key = f"tmdb:{kind}:{identifier}"
    return StoryDocument(key, key, overview, kind, "fixture", year=year)


@pytest.fixture(params=(None, PreparedRetrievalIndex), ids=("legacy", "prepared"))
def make_engine(request):
    def make(rows):
        documents, scores = zip(*rows)
        return SemanticStorySearch(documents, ControlledEncoder({
            doc.overview: score for doc, score in rows
        }), retrieval_factory=request.param)
    return make


def test_rrf_lexical_first_at_dense_rank_40_remains_fifth(make_engine):
    query = "туман"
    leaders = [(_doc("movie", 100 + i, 1984, f"Рыжий пёс грызёт кость {i}."), 100 - i)
               for i in range(39)]
    tied_movie = _doc("movie", 900, 1984, "Рыжий пёс спит.")
    lexical_tv = _doc("tv", 900, 1984, "Туман.")
    rows = [(lexical_tv, 1), *reversed(leaders), (tied_movie, 1)]
    engine = make_engine(rows)
    lexical = LexicalIndex(engine.documents).scores(query)
    assert lexical[0] > 0 and all(score == 0 for score in lexical[1:])

    # Exact ties at dense positions 39/40 resolve by typed ID, not row order.
    # Since the TV result is outside the dense top 40, lexical recall is its
    # only route into the union, but its full dense rank still contributes.
    result = engine.search(query, limit=5, repair_typos=False, evidence=False)
    assert [hit.document.key for hit in result.hits] == [
        *(doc.key for doc, _ in leaders[:4]), lexical_tv.key,
    ]
    score_at_40 = 1 / (60 + 40) + 0.35 / 60
    assert result.hits[4].score == score_at_40
    # With the opposite-channel rank dropped, it would be below dense fifth.
    assert 0.35 / 60 < 1 / (60 + 4) < score_at_40 < 1 / (60 + 3)


def test_metadata_restricts_ranks_before_candidate_truncation(make_engine):
    query = "фильм 1984 про туман"
    global_leaders = [
        (_doc("tv", 100 + i, 1984, f"Туман густеет {i}."), 100 + i) if i % 2 else
        (_doc("movie", 100 + i, 1985, f"Туман густеет {i}."), 100 + i)
        for i in range(45)
    ]
    eligible = [(_doc("movie", i, 1984, f"Рыжий пёс грызёт кость {i}."), 1) for i in (3, 2, 1)]
    hidden = _doc("movie", 99, 1984, "Туман окружает долину.")
    engine = make_engine([*global_leaders, *eligible, (hidden, 999)])
    lexical = LexicalIndex(engine.documents).scores(query)
    assert all(lexical[45 + i] == 0 for i in range(3))
    result = engine.search(query, excluded={hidden.key}, limit=5, repair_typos=False, evidence=False)
    assert [hit.document.key for hit in result.hits] == ["tmdb:movie:1", "tmdb:movie:2", "tmdb:movie:3"]
    assert [hit.score for hit in result.hits] == [1 / (60 + rank) for rank in range(3)]
    assert not engine.search(query, excluded={doc.key for doc, _ in eligible} | {hidden.key},
                             repair_typos=False).hits


def test_prepared_deep_lexical_tie_cannot_change_fifth_http_result(tmp_path, monkeypatch):
    """The sixth candidate must not replace the fifth via a deep lexical rank swap."""
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from dataclasses import replace
    import json

    from fastapi.testclient import TestClient

    from tools.qa.measure_story_lexical_capacity import make_documents
    from web import story_api

    if sum((1., 2.**-53, 2.**-53)) == 1.:
        pytest.skip("The frozen near-tie reproduces on runtimes with compensated float sum")

    docs = tuple(replace(doc, key=f"tmdb:movie:{10000 + i}")
                 for i, doc in enumerate(make_documents(2000, "low")))
    query = docs[0].overview
    scores = LexicalIndex(docs).scores(query)
    ranks = sorted(range(len(docs)), key=lambda i: (-scores[i], docs[i].key))
    assert ranks[188:190] == [803, 853]
    # At dense rank 4, row 803's rank 188 narrowly beats the competitor
    # (dense 5, lexical 152); swapping to rank 189 puts it behind.
    assert 1 / 64 + .35 / 249 < 1 / 65 + .35 / 212 < 1 / 64 + .35 / 248
    heads = (*ranks[:4], 803, ranks[152])
    dense = {docs[row].overview: rank for rank, row in enumerate(ranks)}
    dense.update({docs[row].overview: len(docs) + 5 - rank for rank, row in enumerate(heads)})

    class BoundaryEncoder(ControlledEncoder):
        def __init__(self, _directory):
            super().__init__({doc.overview: dense.get(doc.overview, 0.) for doc in docs})

    monkeypatch.setattr(story_api, "LocalE5", BoundaryEncoder)
    catalog = tmp_path / "seed.jsonl"
    catalog.write_text("".join(json.dumps({"media_type": doc.media_type, "tmdb_id": 10000 + i,
                                           "title": doc.title, "overview": doc.overview,
                                           "year": 2020, "language": "ru-RU"}) + "\n"
                               for i, doc in enumerate(docs)), encoding="utf-8")

    def ids(prepared):
        with TestClient(story_api.create_app(catalog, tmp_path, prepared_index=prepared)) as client:
            response = client.post("/v1/search", json={"query": query, "limit": 5})
            assert response.status_code == 200
            return [card["id"] for card in response.json()["results"]]

    expected = [docs[i].key for i in heads[:5]]
    assert ids(False) == expected
    assert ids(True) == expected

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

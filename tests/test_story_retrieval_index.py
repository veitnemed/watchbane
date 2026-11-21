import pytest

np = pytest.importorskip("numpy")

from candidates.story_lexical import LexicalIndex
from candidates.story_search import StoryDocument
from web.story_retrieval_index import PreparedRetrievalIndex


def _docs(rows):
    return [StoryDocument(key, key, text, "tv" if ":tv:" in key else "movie", "fixture")
            for key, text in rows]


@pytest.mark.parametrize("mask", [None, [False, True, True, False, True], [False] * 5])
@pytest.mark.parametrize("query", ["побег из тюрьмы", "врач", "无匹配", ""])
def test_candidate_orders_match_brute_force_and_retain_cross_channel_ranks(mask, query):
    docs = _docs([
        ("tmdb:tv:7", "Врач помогает пленнику готовить побег из тюрьмы."),
        ("tmdb:movie:7", "Врач помогает пленнику готовить побег из тюрьмы."),
        ("tmdb:tv:5", "Экспедиция исследует подземелье."),
        ("tmdb:movie:2", "Садовник ищет работу."),
        ("tmdb:movie:3", "Врач возвращается после побега."),
    ])
    vectors = np.array([[1, 2], [1, 2], [2, 1], [0, 0], [1, 1]], dtype=np.float32)
    vector = np.array([1, 1], dtype=np.float32)
    index = PreparedRetrievalIndex(docs, vectors)
    expected_scores = LexicalIndex(docs).scores(query)
    np.testing.assert_allclose(index.lexical.scores(query), expected_scores, rtol=1e-14, atol=1e-16)
    rows = range(len(docs)) if mask is None else [i for i, allowed in enumerate(mask) if allowed]
    dense = sorted(rows, key=lambda i: (-float(vectors[i] @ vector), docs[i].key))
    sparse = sorted((i for i in rows if expected_scores[i] > 0),
                    key=lambda i: (-expected_scores[i], docs[i].key))
    found = index.orders(query, vector, eligible=mask, top_k=2)
    assert found.dense_top == tuple(dense[:2])
    assert found.lexical_top == tuple(sparse[:2])
    assert found.dense_ranks.tolist() == [dense.index(i) if i in dense else -1 for i in range(len(docs))]
    assert found.lexical_ranks.tolist() == [sparse.index(i) if i in sparse else -1 for i in range(len(docs))]


def test_synthetic_vectors_recall_and_fused_candidate_order_match_previous_algorithm():
    rng = np.random.default_rng(2701)
    docs = _docs([(f"tmdb:tv:{i}", f"пленник ищет выход из тюрьмы номер {i} на окраине города")
                  for i in range(1000, 1200)])
    vectors = rng.normal(size=(len(docs), 384)).astype(np.float32)
    query, vector = "побег ночью из тюрьмы", rng.normal(size=384).astype(np.float32)
    index = PreparedRetrievalIndex(docs, vectors)
    found = index.orders(query, vector)
    dense = sorted(range(len(docs)), key=lambda i: (-float(vectors[i] @ vector), docs[i].key))
    lexical_scores = LexicalIndex(docs).scores(query)
    sparse = sorted((i for i, score in enumerate(lexical_scores) if score > 0),
                    key=lambda i: (-lexical_scores[i], docs[i].key))
    assert found.dense_top == tuple(dense[:40])
    assert found.lexical_top == tuple(sparse[:40])
    def fused(dense_top, lexical_top, dense_rank, lexical_rank):
        return sorted(set(dense_top) | set(lexical_top), key=lambda i: (
            -(1 / (60 + dense_rank[i]) + (0.35 / (60 + lexical_rank[i]) if lexical_rank[i] >= 0 else 0)),
            docs[i].key,
        ))
    old_d = [dense.index(i) for i in range(len(docs))]
    old_l = [sparse.index(i) if i in sparse else -1 for i in range(len(docs))]
    assert fused(found.dense_top, found.lexical_top, found.dense_ranks, found.lexical_ranks) == fused(
        dense[:40], sparse[:40], old_d, old_l)

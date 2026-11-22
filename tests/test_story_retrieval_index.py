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
    np.testing.assert_array_equal(index.lexical.scores(query), expected_scores)
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


def test_lexical_scores_support_ordinary_float_sum_runtimes(monkeypatch):
    from candidates.story_lexical import grams
    from tools.qa.measure_story_lexical_capacity import make_documents
    from web import story_retrieval_index

    docs = tuple(make_documents(16, "low"))
    query = docs[0].overview
    baseline = LexicalIndex(docs)
    query_weights = baseline.vector(grams(query))

    def ordinary_score(document_weights):
        result = 0.
        for gram, weight in query_weights.items():
            result += weight * document_weights.get(gram, 0.)
        return result

    expected = [ordinary_score(weights) for weights in baseline.vectors]
    monkeypatch.setattr(story_retrieval_index, "_FLOAT_SUM_COMPENSATES", False)
    prepared = PreparedRetrievalIndex(docs, np.zeros((len(docs), 1), dtype=np.float32))
    np.testing.assert_array_equal(prepared.lexical.scores(query), expected)


def test_float32_near_pairs_follow_scalar_ranks_through_fifth_card():
    from candidates.story_semantic import SemanticStorySearch

    rng = np.random.default_rng(322)
    left = rng.normal(size=(1000, 384)).astype(np.float32)
    left /= np.linalg.norm(left, axis=1)[:, None]
    right = left.copy()
    right[:, 0] = np.nextafter(right[:, 0], np.float32(np.inf))
    matrix = np.vstack((left, right))
    query_vector = rng.normal(size=(2, 384)).astype(np.float32)[1].copy()
    query_vector /= np.linalg.norm(query_vector)

    docs = _docs([(f"tmdb:movie:{10000 + i}" if i != 1171 else "tmdb:tv:10171",
                   f"Садовая дорожка {i}.") for i in range(len(matrix))])
    query = "Туман"
    # On the reproducing OpenBLAS runtime a matvec ties rows 171 and 1171,
    # but the scalar dot product distinguishes them. Four greater scores
    # force their ordering to decide the final fifth result.
    dense = sorted(range(len(matrix)), key=lambda i: (-float(matrix[i] @ query_vector), docs[i].key))
    visible = (*dense[:4], 171, 1171)
    mask = [i in visible for i in range(len(matrix))]
    oracle = [i for i in dense if mask[i]]
    assert oracle[-2:] == sorted((171, 1171),
                                 key=lambda i: (-float(matrix[i] @ query_vector), docs[i].key))

    index = PreparedRetrievalIndex(docs, matrix)
    order = index.orders(query, query_vector, eligible=mask, top_k=5)
    assert order.dense_top == tuple(oracle[:5])
    assert order.lexical_top == ()
    assert [int(order.dense_ranks[i]) for i in oracle] == list(range(len(oracle)))
    assert np.all(order.dense_ranks[~np.asarray(mask)] == -1)

    class ControlledEncoder:
        variant = "synthetic"

        def encode(self, texts, prefix="passage: ", **_kwargs):
            if prefix == "query: ":
                assert texts == [query]
                return query_vector[None, :]
            assert texts == [doc.overview for doc in docs]
            return matrix

    hidden = {doc.key for i, doc in enumerate(docs) if not mask[i]}
    expected = [docs[i].key for i in oracle[:5]]
    for factory in (None, PreparedRetrievalIndex):
        engine = SemanticStorySearch(docs, ControlledEncoder(), retrieval_factory=factory)
        result = engine.search(query, excluded=hidden, limit=5, repair_typos=False, evidence=False)
        assert [hit.document.key for hit in result.hits] == expected

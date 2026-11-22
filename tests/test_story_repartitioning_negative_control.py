"""Synthetic monolith parity controls; not an implementation of shard serving."""
import pytest

np = pytest.importorskip("numpy")

from candidates.story_lexical import LexicalIndex
from candidates.story_search import StoryDocument
from candidates.story_semantic import SemanticStorySearch
from web.story_retrieval_index import PreparedRetrievalIndex


def doc(kind, number, synopsis):
    return StoryDocument(f"tmdb:{kind}:{number}", "Example", synopsis, kind, "fixture")


def test_shard_file_validity_does_not_make_local_idf_scores_comparable():
    docs = (
        doc("movie", 7, "детектив расследует убийство"),
        doc("movie", 8, "доктор вспоминает детство"),
        doc("tv", 7, "полиция расследует исчезновение"),
        doc("tv", 8, "детектив расследует дело"),
    )
    query = "детектив расследует исчезновение"

    def global_scores(items):
        reference = LexicalIndex(items).scores(query)
        prepared = PreparedRetrievalIndex(items, np.ones((len(items), 1))).lexical.scores(query)
        assert prepared == pytest.approx(reference, abs=1e-12)
        return {item.key: score for item, score in zip(items, prepared, strict=True)}

    global_ = global_scores(docs)
    assert global_["tmdb:tv:7"] == pytest.approx(.725011, abs=1e-6)
    assert global_["tmdb:movie:7"] == pytest.approx(.468230, abs=1e-6)
    for groups in ((docs[:2], docs[2:]), (docs[:1], docs[1:]), (docs[::2], docs[1::2])):
        reordered = tuple(item for group in groups for item in group)
        shared = global_scores(reordered)
        assert shared == pytest.approx(global_, abs=1e-12)
    local = global_scores(docs[:2]) | global_scores(docs[2:])
    assert local["tmdb:movie:7"] == pytest.approx(.830380, abs=1e-6)
    assert local["tmdb:tv:7"] == pytest.approx(.688379, abs=1e-6)
    assert global_["tmdb:tv:7"] > global_["tmdb:movie:7"]
    assert local["tmdb:tv:7"] < local["tmdb:movie:7"]


def test_monolith_uses_global_typo_vocabulary_and_deep_opposing_ranks():
    # Both same-number rows tie in each lane, a dense-only leader has zero
    # lexical score, and a lexical Top-40 row sits deep in the dense lane.
    docs = (
        doc("movie", 7, "детектив расследует исчезновение"),
        doc("tv", 7, "детектив расследует исчезновение"),
        doc("movie", 8, "зебра топчет траву"),
        *[doc("movie", 800 + i, "детектив расследует исчезновение") for i in range(41)],
    )
    dense = np.array([0, 0, 100, *range(1, 42)], dtype=np.float32).reshape(-1, 1)

    class Encoder:
        variant = "synthetic"

        def __init__(self):
            self.queries = []

        def encode(self, texts, prefix="passage: ", **_):
            if prefix == "query: ":
                self.queries.append(texts)
                return np.ones((1, 1), dtype=np.float32)
            return dense

    for factory in (None, PreparedRetrievalIndex):
        encoder = Encoder()
        engine = SemanticStorySearch(docs, encoder, retrieval_factory=factory)
        seen = []
        actual = engine.search("исчезновениие", evidence=False, observe_candidates=seen.append)
        assert encoder.queries == [["исчезновение"]]
        trace, = seen
        assert "tmdb:movie:8" == trace.dense_keys[0]
        assert "tmdb:movie:8" not in trace.lexical_keys
        assert "tmdb:movie:7" in trace.lexical_keys and "tmdb:movie:7" not in trace.dense_keys
        if factory is None:
            expected = actual
        else:
            assert actual == expected

    index = PreparedRetrievalIndex(docs, dense)
    orders = index.orders("исчезновение", np.ones(1), top_k=40)
    assert orders.dense_ranks[0] == 42
    assert orders.dense_ranks[1] == 43
    assert orders.lexical_ranks[2] == -1
    assert orders.lexical_ranks[1] >= 40
    assert 43 in orders.dense_top and 43 not in orders.lexical_top
    assert orders.lexical_ranks[43] == 41
    assert orders.lexical_ranks[0] < orders.lexical_ranks[1]
    # Compare the same fixed scores and query under different synthetic
    # groupings. This oracle deliberately scans eligible rows for ranks; it
    # says nothing about the cost of distributed ranking.
    scores = index.lexical.scores("исчезновение")
    scores.flags.writeable = False
    dense.flags.writeable = False
    size_skew = (tuple(range(43)), (43,))
    mixed = (tuple(range(0, 44, 2)), tuple(range(1, 44, 2)))
    typed = tuple(tuple(i for i, item in enumerate(docs) if item.media_type == kind)
                  for kind in ("movie", "tv"))
    for mask in ([True] * len(docs), [item.media_type == "tv" for item in docs],
                 [i in (0, 1, 2, 30, 43) for i in range(len(docs))]):
        eligible = {i for i, selected in enumerate(mask) if selected}
        reference = index.orders("исчезновение", np.ones(1), eligible=mask)
        verified_final = engine.search(
            "исчезновениие", evidence=False,
            excluded={item.key for i, item in enumerate(docs) if i not in eligible},
        )
        for partition in (size_skew, typed, mixed):
            def dense_key(i):
                return -float(dense[i, 0]), docs[i].key

            def lexical_key(i):
                return -float(scores[i]), docs[i].key

            def merge(lane, key):
                local = [i for group in partition for i in sorted(lane.intersection(group), key=key)[:40]]
                return tuple(sorted(local, key=key)[:40])

            positive = {i for i in eligible if scores[i] > 0}
            d_top = merge(eligible, dense_key)
            l_top = merge(positive, lexical_key)
            assert (d_top, l_top) == (reference.dense_top, reference.lexical_top)
            fused = {}
            for i in set(d_top) | set(l_top):
                dr = sum(dense_key(j) < dense_key(i) for group in partition for j in group if j in eligible)
                lr = (sum(lexical_key(j) < lexical_key(i) for group in partition for j in group if j in positive)
                      if i in positive else -1)
                assert (dr, lr) == (reference.dense_ranks[i], reference.lexical_ranks[i])
                fused[i] = 1 / (60 + dr) + (.35 / (60 + lr) if lr >= 0 else 0)
            merged_top5 = sorted(fused, key=lambda i: (-fused[i], docs[i].key))[:5]
            assert [(docs[i].key, fused[i]) for i in merged_top5] == [
                (hit.document.key, hit.score) for hit in verified_final.hits
            ]

    tv_only = [item.media_type == "tv" for item in docs]
    filtered = index.orders("исчезновение", np.ones(1), eligible=tv_only, top_k=40)
    assert filtered.dense_top == filtered.lexical_top == (1,)
    assert filtered.dense_ranks[1] == filtered.lexical_ranks[1] == 0

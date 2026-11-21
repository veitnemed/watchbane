from types import SimpleNamespace

from candidates.story_lexical import LexicalIndex
from candidates.story_search import StoryDocument
from tools.qa import compare_story_server_rankers as compare


def engine_fixture():
    docs = (
        StoryDocument("tmdb:movie:1", "Море", "Пират выходит в море.", "movie", "TMDb", year=2021),
        StoryDocument("tmdb:tv:2", "Берег", "Пират прибывает на берег.", "tv", "TMDb", year=2022),
        StoryDocument("tmdb:movie:3", "Комета", "Герой наблюдает комету.", "movie", "TMDb", year=2022),
    )

    class Dot:
        def __init__(self, value):
            self.value = value

        def __matmul__(self, _):
            return self.value

    calls = []
    engine = SimpleNamespace(
        documents=docs, title_words=set(), vectors=[Dot(.6), Dot(.8), Dot(.2)],
        vocabulary={word for doc in docs for word in compare.tokens(doc.overview)},
        lexical=LexicalIndex(docs),
        encoder=SimpleNamespace(encode=lambda words, **kw: calls.append((words, kw)) or [0]),
        search=lambda query, limit: SimpleNamespace(hits=[SimpleNamespace(document=docs[2])]),
    )
    return engine, calls


def ids(search, query):
    return [hit["id"] for hit in search(query)["results"]]


def test_all_baselines_share_scope_mask_and_never_encode_rejected_queries():
    engine, calls = engine_fixture()
    compare_rankers = compare.rankers(engine)
    for search in compare_rankers.values():
        assert ids(search, "как подключить клавиатуру") == []
        assert ids(search, "сериал 1920 про пирата") == []
    assert calls == []
    for search in compare_rankers.values():
        assert ids(search, "сериал 2022 про берег") == ["tmdb:tv:2"]
    assert len(calls) == 1
    assert calls[0][1] == {"prefix": "query: "}


def test_dense_retrieves_without_overlap_but_sparse_rankers_abstain():
    engine, _ = engine_fixture()
    rank = compare.rankers(engine, include_hybrid=True)
    for name in ("bm25", "char_tfidf"):
        assert ids(rank[name], "цццщщщ") == []
    assert ids(rank["dense_e5"], "цццщщщ") == [
        "tmdb:tv:2", "tmdb:movie:1", "tmdb:movie:3",
    ]
    assert ids(rank["current_hybrid"], "пираты") == ["tmdb:movie:3"]


def test_bm25_uses_fixed_idf_and_prefers_rare_term():
    engine, _ = engine_fixture()
    bm25 = compare.BM25(engine.documents)
    assert bm25.scores("комету")[2] > bm25.scores("пират")[0] > 0

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


def test_bm25_matches_either_word_and_ties_by_typed_id_without_indexing_titles():
    docs = (
        StoryDocument("tmdb:tv:4", "Кальмар", "Пират наблюдает чайку.", "tv", "TMDb"),
        StoryDocument("tmdb:movie:4", "Кальмар", "Пират наблюдает чайку.", "movie", "TMDb"),
        StoryDocument("tmdb:tv:7", "Пират", "Врач изучает карту.", "tv", "TMDb"),
    )
    query = "Пират кальмар"
    bm25 = compare.BM25(docs)
    scores = bm25.scores(query)
    assert scores[0] == scores[1] > 0
    assert dict(bm25.scores("КАЛЬМАР")) == {}
    assert dict(bm25.scores("!!!")) == {}
    assert dict(bm25.scores("пира")) == {}
    engine, _ = engine_fixture()
    engine.documents = docs
    engine.vocabulary = {word for doc in docs for word in compare.tokens(doc.overview)}
    assert ids(compare.rankers(engine)["bm25"], query) == ["tmdb:movie:4", "tmdb:tv:4"]


def test_success_buckets_separate_refusal_filtered_and_eligible_empty_from_errors():
    engine, _ = engine_fixture()
    rank = compare.rankers(engine, include_hybrid=True)
    cases = [
        ("out_of_scope", "как подключить клавиатуру", None),
        ("insufficient_detail", "сериал 1920 про пирата", None),
        ("known_target", "берег", "tmdb:tv:2"),
        ("known_target", "цццщщщ", "tmdb:tv:2"),
        ("known_target", "ццццчччч", "tmdb:tv:99"),
        ("known_target", "имитация ошибки", "tmdb:tv:99"),
    ]
    indexed = {doc.key for doc in engine.documents}

    def search(query):
        if query == "имитация ошибки":
            return {"source": "tmdb", "results": [{"id": "tmdb:tv:99"}]}
        return rank["bm25"](query)

    report = compare.compare_metrics(cases, indexed, search)
    assert report["successful_outcomes"] == {
        "known_target": {"with_cards": 1, "scope_refused": 0,
                         "no_eligible_documents": 0, "eligible_but_empty": 2},
        "out_of_scope": {"with_cards": 0, "scope_refused": 1,
                         "no_eligible_documents": 0, "eligible_but_empty": 0},
        "insufficient_detail": {"with_cards": 0, "scope_refused": 0,
                                "no_eligible_documents": 1, "eligible_but_empty": 0},
    }
    assert report["known_successful_outcomes_by_coverage"] == {
        "covered": {"with_cards": 1, "scope_refused": 0,
                    "no_eligible_documents": 0, "eligible_but_empty": 1},
        "absent": {"with_cards": 0, "scope_refused": 0,
                   "no_eligible_documents": 0, "eligible_but_empty": 1},
    }
    assert report["known"]["query_coverage"]["n"] == 2
    assert report["known"]["hit_at_5_covered"]["n"] == 1
    assert report["request_errors"]["known_target"] == 1
    latency = report["latency_successful_process_ms"]
    assert latency["count"] == 5 and 0 <= latency["p50"] <= latency["p95"]
    assert "latency_successful_http_ms" not in report


def test_cli_uses_one_pinned_snapshot_and_prints_only_aggregate_metrics(tmp_path, monkeypatch, capsys):
    from hashlib import sha256
    import json
    from web import story_api

    engine, _ = engine_fixture()
    catalog = tmp_path / "private_catalog.jsonl"
    catalog.write_text("".join(json.dumps({
        "media_type": doc.media_type, "tmdb_id": int(doc.key.rsplit(":", 1)[1]),
        "title": doc.title, "overview": doc.overview, "year": doc.year, "language": "ru-RU",
    }, ensure_ascii=False) + "\n" for doc in engine.documents), encoding="utf-8")
    digest = sha256(catalog.read_bytes()).hexdigest()
    cases = tmp_path / "private_cases.jsonl"
    target = {"media_type": "tv", "tmdb_id": 2, "identity_label_ru": "берег",
              "source_url": "fixture"}
    queries = ("Герой прибывает на берег", "Пират видит берег")
    cases.write_text("".join(json.dumps({
        "id": f"private-row-{i}", "query": q, "target": target, "group": "tv:2",
        "expected": "known_target",
    }, ensure_ascii=False) + "\n" for i, q in enumerate(queries)), encoding="utf-8")
    monkeypatch.setattr(compare, "LANES", {"known_target": 2})
    monkeypatch.setattr(story_api, "build_engine", lambda *_: engine)
    assert compare.main(["--cases", str(cases), "--cases-sha256", sha256(cases.read_bytes()).hexdigest(),
                         "--catalog", str(catalog), "--catalog-sha256", digest,
                         "--model-dir", str(tmp_path), "--include-hybrid"]) == 0
    output = capsys.readouterr().out
    report = json.loads(output)
    assert report["eligible_catalog_ids"] == 3
    assert set(report["rankers"]) == {"bm25", "char_tfidf", "dense_e5", "current_hybrid"}
    assert report["rankers"]["bm25"]["known"]["hit_at_5_covered"]["n"] == 2
    assert all(q not in output for q in (*queries, "private-row", "tmdb:tv:2", str(tmp_path)))

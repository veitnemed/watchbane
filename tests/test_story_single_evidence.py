"""Control the provisional singleton explanation fast path without model downloads."""
import pytest

np = pytest.importorskip("numpy")

from candidates.story_search import StoryDocument
from candidates.story_semantic import SemanticStorySearch
from web.story_retrieval_index import PreparedRetrievalIndex


class Encoder:
    variant = "controlled offline fixture"

    def __init__(self, query_value=1.):
        self.query = query_value
        self.calls = []

    def encode(self, texts, prefix="passage: ", **_kwargs):
        self.calls.append((tuple(texts), prefix))
        scores = {"Первый мастер.": 0.1, "Второй архив!": 0.9, "Один мастер!": 0.5}
        value = lambda text: self.query if prefix == "query: " else scores.get(text, .25)
        return np.array([[value(text)] for text in texts], dtype=np.float32)


@pytest.mark.parametrize("query_value", [1., float("nan"), float("inf")])
def test_trimmed_singleton_requires_no_evidence_encode(query_value):
    enc = Encoder(query_value)
    docs = [StoryDocument("a", "A", " \n Один мастер!\t ", "movie", "fixture"),
            StoryDocument("empty", "B", " \n\t ", "movie", "fixture")]
    eng = SemanticStorySearch(docs, enc, retrieval_factory=PreparedRetrievalIndex, skip_singleton_evidence=True)
    enc.calls.clear()
    result = eng.search("фильм про мастера", repair_typos=False)
    assert [(hit.document.key, hit.evidence) for hit in result.hits] == [("a", "Один мастер!")]
    assert len(enc.calls) == 1 and enc.calls[0][1] == "query: "


def test_multi_and_optional_rerank_unchanged():
    enc = Encoder()
    docs = [StoryDocument("a", "A", "Один мастер!", "movie", "fixture"),
            StoryDocument("b", "B", "Первый мастер.\n  Второй архив!", "tv", "fixture")]
    eng = SemanticStorySearch(docs, enc, retrieval_factory=PreparedRetrievalIndex, skip_singleton_evidence=True)
    enc.calls.clear()
    normal = eng.search("мастер архив", repair_typos=False)
    assert {h.document.key: h.evidence for h in normal.hits} == {"a":"Один мастер!", "b":"Второй архив!"}
    assert enc.calls[1:] == [(("Первый мастер.", "Второй архив!"), "passage: ")]
    enc.calls.clear()
    no_evidence = eng.search("мастер архив", evidence=False, repair_typos=False)
    assert {h.document.key: h.evidence for h in no_evidence.hits} == {"a":"Один мастер!", "b":"Первый мастер."}
    assert len(enc.calls) == 1
    enc.calls.clear()
    reranked = eng.search("мастер архив", rerank=True, repair_typos=False)
    assert {h.document.key: h.evidence for h in reranked.hits} == {"a":"Один мастер!", "b":"Второй архив!"}
    assert (("Один мастер!",), "passage: ") in enc.calls[1:]
    assert (("Первый мастер.", "Второй архив!"), "passage: ") in enc.calls[1:]


def test_default_keeps_legacy_passage_cache_traffic():
    enc = Encoder()
    doc = StoryDocument("a", "A", "Один мастер!", "movie", "fixture")
    eng = SemanticStorySearch([doc], enc, retrieval_factory=PreparedRetrievalIndex)
    enc.calls.clear()
    assert eng.search("фильм про мастера", repair_typos=False).hits[0].evidence == "Один мастер!"
    assert enc.calls[1:] == [(("Один мастер!",), "passage: ")]


def test_server_option_is_disabled_unless_requested(tmp_path):
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient
    from web.story_api import create_app

    calls = []
    def engine_factory(_catalog, _model, **kwargs):
        calls.append(kwargs)
        doc = StoryDocument("tmdb:movie:1", "A", "Один мастер!", "movie", "fixture")
        return SemanticStorySearch([doc], Encoder(), **kwargs)

    def body(options):
        with TestClient(create_app(tmp_path, tmp_path, engine_factory=engine_factory, **options)) as client:
            result = client.post("/v1/search", json={"query": "фильм про мастера", "limit": 1})
            assert result.status_code == 200
            return result.json()

    assert body({}) == body({"skip_singleton_evidence": True})
    assert calls == [{}, {"skip_singleton_evidence": True}]


def test_overlap_can_preserve_a_different_cache_path_and_flag_must_remain_opt_in():
    single = "Один мастер!"
    other = "Второй архив!"
    docs = [
        StoryDocument("a", "A", single, "movie", "fixture"),
        StoryDocument("b", "B", f"{single} {other}", "tv", "fixture"),
    ]

    class BatchSensitive(Encoder):
        """Explicit counterexample for an encoder/runtime with shape-sensitive vectors."""
        def __init__(self):
            super().__init__()
            self.cache = {}

        def encode(self, texts, prefix="passage: ", **kwargs):
            if prefix == "query: ":
                return super().encode(texts, prefix=prefix, **kwargs)
            for text in texts:
                if text == single:
                    self.cache.setdefault(text, 0.9 if len(texts) == 1 else 0.1)
                else:
                    self.cache.setdefault(text, 0.5)
            return np.array([[self.cache[text]] for text in texts], dtype=np.float32)

    def chronology(fast):
        enc = BatchSensitive()
        eng = SemanticStorySearch(docs, enc, retrieval_factory=PreparedRetrievalIndex,
                                  skip_singleton_evidence=fast)
        enc.cache.clear()  # model passage text cache is empty after a snapshot hit
        a = eng.search("фильм про мастера", repair_typos=False).hits[0]
        b = eng.search("сериал про мастера", repair_typos=False).hits[0]
        return a.evidence, b.evidence

    assert chronology(False) == (single, single)
    assert chronology(True) == (single, other)  # not a guarantee of sequence equivalence

import pytest

from candidates.story_search import StoryDocument, StorySearch, unsupported_negation


@pytest.mark.parametrize("query", [
    "девочка понятия не имела, куда уехала семья",
    "братья понятия не имеют, кто украл скрипку",
    "врач понятия не имеет, где его дочь",
])
def test_ignorance_idiom_reaches_search(query):
    engine = StorySearch([StoryDocument("movie:1", "Семья", "Врач ищет дочь.", "movie", "qa")])
    assert not unsupported_negation(query)
    assert "Отрицания" not in engine.search(query).notice


@pytest.mark.parametrize("query", [
    "триллер, в котором врач понятия не имеет, где дочь, но без насилия",
    "братья понятия не имеют, кто украл скрипку, только не комедия",
    "любовная история, которая не имеет отношения к войне",
    "не про врача, который понятия не имел о пропаже",
])
def test_ignorance_idiom_does_not_override_exclusions(query):
    engine = StorySearch([StoryDocument("movie:1", "Семья", "Врач ищет дочь.", "movie", "qa")])
    assert unsupported_negation(query)
    result = engine.search(query)
    assert not result.hits and "Отрицания" in result.notice


@pytest.mark.parametrize("query", [
    "Отец ищет пропавшую дочь, а полиция ему не верит",
    "Следователи не верят свидетелю, и он ищет записку сам.",
    "Мать ей не верила и оставалась у дома.",
    "Герой не верит, что под снегом стоит целый город.",
    "Детектив не верил в случайность.",
    "История о сестре, которая не верит в возвращение брата.",
    "Врачи ему не верили.",
])
def test_third_person_disbelief_has_narrow_narrative_context(query):
    engine = StorySearch([StoryDocument("movie:1", "Фикстура", "Семья ищет ответ.", "movie", "qa")])
    assert not unsupported_negation(query)
    assert "Отрицания" not in engine.search(query).notice


@pytest.mark.parametrize("query", [
    "не верит",
    "полиция не верит",
    "полиция не верит в",
    "полиция не верит, что",
    "я не верю в хороший финал",
    "Фильм о внезапном открытии. Не верит ему зритель.",
    "В кадре полиция. Ему не верит человек у окна.",
    "Герой не-верит в тайну старого дома",
    "Детектив не верил в случайность, пока не понял улику.",
    "Врач ему не верил, только не сериал",
    "Он не верит в исчезновение, но не про месть",
    "Семья ей не верит, но без похищения",
    "Полицейские не верят ему, кроме истории про обман",
    "Ищу не мелодраму, где героиня не верит, что брат вернётся",
])
def test_disbelief_exception_cannot_do_unsupported_filtering(query):
    assert unsupported_negation(query)


def test_user_disbelief_example_reaches_real_fp32_and_exclusions_do_not(tmp_path):
    import json
    import os
    from pathlib import Path

    model = os.environ.get("WATCHBANE_QA_MODEL_DIR")
    if not model:
        pytest.skip("Pinned local FP32 weights are needed")
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient
    from web.story_api import build_engine, create_app

    assert (Path(model) / "onnx/model.onnx").is_file(), "Expected pinned local portable FP32 weights"
    catalog = tmp_path / "synthetic.jsonl"
    catalog.write_text(json.dumps({
        "media_type": "movie", "tmdb_id": 2147482068, "title": "Фикстура поиска",
        "overview": "Реставратор ремонтирует часы в старой библиотеке.", "language": "ru-RU",
        "year": 2005,
    }, ensure_ascii=False) + "\n", encoding="utf-8")
    engine = build_engine(catalog, Path(model))
    assert engine.encoder.variant == "fp32"
    encode, query_encodes = engine.encoder.encode, []

    def count(texts, prefix="passage: ", **kwargs):
        if prefix == "query: ":
            query_encodes.append(len(texts))
        return encode(texts, prefix=prefix, **kwargs)

    engine.encoder.encode = count
    user = "Отец ищет пропавшую дочь, а полиция ему не верит"
    headers = {"Watchbane-Search-Outcome": "1"}
    with TestClient(create_app(catalog, Path(model), engine_factory=lambda *_: engine)) as client:
        result = client.post("/v1/search", headers=headers, json={"query": user})
        assert result.status_code == 200 and result.json()["outcome"]["state"] == "candidates"
        assert query_encodes == [1]  # Gate acceptance only, not a relevance or exact-match result.
        for query in (user + ", только не сериал", user + ", но без драки", "не про полицию"):
            result = client.post("/v1/search", headers=headers, json={"query": query})
            assert result.status_code == 200
            assert result.json() == {"source": "tmdb", "results": [],
                                     "outcome": {"state": "clarification", "reason": "unsupported_exclusion"}}
            assert query_encodes == [1]

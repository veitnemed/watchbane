from dataclasses import replace
import pytest
from candidates.story_search import StorySearch, StoryDocument, concepts, tokens
from candidates.story_demo import demo_documents


def test_typo_and_short_query():
    engine = StorySearch(demo_documents())
    assert concepts(tokens("пристурник"), fuzzy=True) == {"criminal"}
    assert engine.search("пристурник").hits
    assert engine.search("космос").hits[0].document.key == "demo:05"


def test_role_and_type():
    engine = StorySearch(demo_documents())
    criminal = engine.search("сериал про преступника").hits
    detective = engine.search("сериал про следователя").hits
    assert {h.document.key for h in criminal} == {"demo:01","demo:03","demo:15","demo:18","demo:25"}
    assert {h.document.key for h in criminal}.isdisjoint(h.document.key for h in detective)
    assert all(h.document.media_type == "tv" for h in criminal)


def test_unseen_titles_and_evidence_not_invented():
    docs = [StoryDocument("a", "Новый текст", "Вор ищет способ спасти дочь. Следователь идет по его следу.", "tv", "тест"),
            StoryDocument("b", "Другое", "Следователь ловит вора. Улики ведут к его семье.", "tv", "тест")]
    result = StorySearch(docs).search("преступник")
    assert result.hits[0].document.key == "a"
    assert all(h.evidence in h.document.overview for h in result.hits)
    assert [h.document.key for h in StorySearch(list(reversed(docs))).search("преступник").hits] == [h.document.key for h in result.hits]


def test_exclusion_applies_before_retrieval_and_no_random_refill():
    docs = demo_documents()
    result = StorySearch(docs).search("преступник", excluded=frozenset(d.key for d in docs))
    assert not result.hits
    assert result.notice


@pytest.mark.parametrize("query", ["", "   ", "сериал", "без преступников", "не про войну", "кроме войны", "x" * 601, "орхидея"])
def test_abstain(query):
    result = StorySearch(demo_documents()).search(query)
    assert not result.hits and result.notice


def test_retriever_is_replaceable():
    class Provider:
        def retrieve(self, query, documents, limit):
            return [(documents[-1], 1.0)]
    doc = StoryDocument("x", "X", "Астронавт летит в космос.", "movie", "owned")
    assert StorySearch([doc], Provider()).search("космос").hits[0].document == doc


def test_local_adapter_hidden_watched_and_safety(monkeypatch):
    from candidates import story_service
    from candidates.title_state_service import hide_candidate, mark_watched
    records = [{"title": "Title " + str(i), "year": 2020, "media_type":"tv", "tmdb_id": 8000+i,
                "overview":"Преступник планирует ограбление.", "source":"synthetic"} for i in range(3)]
    monkeypatch.setattr(story_service, "get_pool_view", lambda: records)
    hide_candidate(records[0]); mark_watched(records[1])
    engine, mapped = story_service.local_story_catalog()
    assert len(engine.documents) == len(mapped) == 1
    assert engine.documents[0].title == "Title 2"


def test_role_candidate_is_not_lost_behind_many_lexical_decoys():
    decoys = [StoryDocument(str(i), "Case", "Следователь ищет преступника.", "tv", "test") for i in range(120)]
    hero = StoryDocument("last", "Hero", "Вор начинает новую жизнь.", "tv", "test")
    assert StorySearch([*decoys, hero]).search("сериал про преступника").hits[0].document.key == "last"


def test_adult_and_missing_overview_are_not_story_candidates(monkeypatch):
    from candidates import story_service
    records = [{"title":"Adult", "year":2020,"media_type":"tv","adult":True,"overview":"Преступник скрывается."},
               {"title":"No plot", "year":2020,"media_type":"tv"}]
    monkeypatch.setattr(story_service,"get_pool_view",lambda: records)
    engine, mapped = story_service.local_story_catalog()
    assert not engine.documents and not mapped


def test_explicit_year_is_release_constraint_not_plot_year():
    from candidates.story_search import media_constraints
    assert media_constraints('фильм 2014 про космос') == ('movie',2014)
    assert media_constraints('история о событиях 1985 года') == (None,None)
    assert media_constraints('сериал вышел в 2022') == ('tv',2022)


def test_negative_plot_description_is_not_exclusion():
    from candidates.story_search import unsupported_negation
    assert not unsupported_negation('герой не может вспомнить свое имя')
    assert unsupported_negation('не про войну')


def test_both_media_types_are_not_silently_narrowed():
    from candidates.story_search import media_constraints
    assert media_constraints('сериал или фильм про космос') == (None,None)
    assert media_constraints('фильм или сериал') == (None,None)


@pytest.mark.parametrize('query',['исключая войну','не детектив','только не ужасы','без убийств','никакой романтики'])
def test_exclusions_are_explicitly_declined(query):
    response=StorySearch(demo_documents()).search(query)
    assert not response.hits and 'Отрицания' in response.notice


def test_session_index_reuse_change_and_explicit_refresh():
    from candidates import story_service as service
    docs = demo_documents()
    service.clear_story_search_cache()
    notices = []
    first = service.create_story_search(docs, on_progress=notices.append)
    assert service.create_story_search(list(docs), on_progress=notices.append) is first
    assert len(notices) == 1
    changed = service.create_story_search(docs[:-1])
    assert changed is not first
    service.clear_story_search_cache()
    assert service.create_story_search(docs[:-1]) is not changed
    service.clear_story_search_cache()


def test_auto_source_does_not_replace_filtered_catalog_with_demo(monkeypatch):
    from candidates import story_service as service
    monkeypatch.setattr(service, 'get_pool_view', lambda: [{'title':'Missing description','media_type':'tv'}])
    engine, records = service.local_story_catalog(auto_demo=True)
    assert not engine.documents and not records

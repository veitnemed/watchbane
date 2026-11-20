"""Real model integration is explicit and opt-in; never downloads in tests."""
import os
from pathlib import Path
import pytest
from candidates.story_search import StoryDocument


@pytest.fixture(scope='module')
def encoder():
    directory=os.environ.get('WATCHBANE_TEST_MODEL_DIR')
    if not directory:pytest.skip('Set WATCHBANE_TEST_MODEL_DIR to verified local E5 artifacts')
    from candidates.story_semantic import LocalE5
    return LocalE5(directory)


def test_real_e5_normalized_vectors_and_semantic_recall(encoder):
    from candidates.story_semantic import SemanticStorySearch
    docs=[StoryDocument('memory','A','После травмы мужчина утратил способность сохранять новые воспоминания.', 'movie','authored',year=2000),
          StoryDocument('food','B','Повар готовит ужин для гостей ресторана.', 'movie','authored',year=2014)]
    v=encoder.encode([d.overview for d in docs])
    assert v.shape==(2,384)
    assert encoder.np.allclose(encoder.np.linalg.norm(v,axis=1),1,atol=1e-5)
    engine=SemanticStorySearch(docs,encoder)
    assert engine.search('человек не может запоминать новые события').hits[0].document.key=='memory'
    assert engine.search('фильм 2014 о поваре').hits[0].document.key=='food'
    assert not engine.search('сериал о поваре').hits


def test_contrastive_role_and_conflict(encoder):
    from candidates.story_semantic import SemanticStorySearch
    docs=[StoryDocument('thief','A','Вор скрывается от полиции после ограбления. Он ищет способ покинуть город.', 'tv','authored'),
          StoryDocument('police','B','Полицейский ловит вора после ограбления. Он ищет подозреваемого в городе.', 'tv','authored'),
          StoryDocument('family','C','Вор возвращается домой после тюрьмы. Он хочет восстановить отношения с дочерью.', 'tv','authored')]
    engine=SemanticStorySearch(docs,encoder)
    assert engine.search('вор скрывается от полиции',rerank=True).hits[0].document.key=='thief'
    assert engine.search('полицейский ловит вора',rerank=True).hits[0].document.key=='police'
    assert engine.search('человек после заключения пытается вернуть доверие дочери',rerank=True).hits[0].document.key=='family'


def test_invalid_model_fails_closed_without_network(tmp_path,monkeypatch):
    pytest.importorskip('onnxruntime')
    from candidates.story_semantic import LocalE5
    import requests
    calls=[]
    monkeypatch.setattr(requests.Session,'request',lambda *a,**k:calls.append(a))
    with pytest.raises(ValueError,match='Missing or unverified'):
        LocalE5(tmp_path)
    assert not calls


def test_e5_qt_flow_is_local(qtbot,encoder,monkeypatch):
    from candidates import story_service
    from desktop.story.view import StorySearchView
    from PyQt6.QtCore import Qt
    monkeypatch.setattr(story_service,'_local_encoder',lambda _:encoder)
    monkeypatch.setattr(story_service, "get_pool_view", lambda: [{
        "title": "Fixture", "tmdb_id": 167, "media_type": "tv",
        "overview": "Преступник скрывается от полиции и планирует ограбление.",
    }])
    view=StorySearchView();view.model_dir=os.environ['WATCHBANE_TEST_MODEL_DIR']
    qtbot.addWidget(view.widget);view.widget.show();view.query.setText('сериал про пристурника')
    qtbot.mouseClick(view.search_button,Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda:view._worker is None,timeout=20000)
    assert 'E5' in view.backend_label.text()
    assert view.cards_layout.count()>1


def test_evidence_does_not_change_default_hybrid_order(encoder):
    from candidates.story_semantic import SemanticStorySearch
    docs=[StoryDocument('a','A','Вор бежит от полиции. Он хочет спасти семью.','tv','authored'),
          StoryDocument('b','B','Полицейский ищет вора. Он раскрывает ограбление.','movie','authored')]
    engine=SemanticStorySearch(docs,encoder)
    with_evidence=engine.search('сериал или фильм о воре')
    without=engine.search('сериал или фильм о воре',evidence=False)
    assert [h.document.key for h in with_evidence.hits]==[h.document.key for h in without.hits]
    assert {h.document.media_type for h in with_evidence.hits}=={'tv','movie'}
    assert all(h.evidence in h.document.overview for h in with_evidence.hits)


def test_opt_in_explicit_criminal_role_does_not_promote_investigator(encoder):
    from candidates.story_semantic import SemanticStorySearch
    from tests.fixtures.story_demo import demo_documents
    result=SemanticStorySearch(demo_documents(),encoder).search('сериал про пристурника',role_adjustment=True)
    assert result.hits[0].document.key in {'demo:01','demo:03','demo:15','demo:18','demo:25'}


def test_only_final_cards_get_sentence_extraction(encoder):
    from candidates.story_semantic import SemanticStorySearch
    class RecordingEncoder:
        variant = encoder.variant
        def __init__(self): self.calls = []
        def encode(self, texts, **kwargs):
            self.calls.append((len(texts), kwargs.get('prefix', 'passage: ')))
            return encoder.encode(texts, **kwargs)
    proxy = RecordingEncoder()
    docs = [StoryDocument(str(i),str(i),f'Врач лечит пациентов. В больницу приходит посетитель номер {i}.','tv','authored') for i in range(12)]
    engine = SemanticStorySearch(docs, proxy)
    proxy.calls.clear()
    result = engine.search('врач в больнице',limit=3)
    assert len(result.hits) == 3
    assert proxy.calls == [(1,'query: ')] + [(2,'passage: ')] * 3


def test_persistent_cache_preserves_real_vectors_ranks_and_evidence(encoder,tmp_path):
    from candidates.story_semantic import SemanticStorySearch
    from candidates.story_vector_cache import CachedPassageEncoder
    from tests.fixtures.story_demo import demo_documents
    docs=demo_documents()[:8]
    baseline=SemanticStorySearch(docs,encoder)
    cached=SemanticStorySearch(docs,CachedPassageEncoder(encoder,tmp_path))
    assert encoder.np.array_equal(baseline.vectors,cached.vectors)
    for query in ['сериал про преступника','полицейский ловит вора','фильм или сериал о семье']:
        assert baseline.search(query)==cached.search(query)
    restarted=SemanticStorySearch(docs,CachedPassageEncoder(encoder,tmp_path))
    assert restarted.encoder.cache.hits==len(docs)
    assert restarted.encoder.cache.writes==0

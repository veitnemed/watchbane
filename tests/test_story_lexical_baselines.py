from types import SimpleNamespace

import pytest
from tools.qa.story_lexical_baselines import BM25, CharTFIDF, evaluate


@pytest.mark.parametrize('method', [BM25, CharTFIDF])
def test_baselines_rank_relevant_overview_and_never_use_title(method):
    docs = [SimpleNamespace(key='z', title='снеговик', overview='Детектив расследует убийство'),
            SimpleNamespace(key='a', title='убийство', overview='Музыкант бежит в пустыню')]
    engine = method(docs)
    assert engine.search('снеговик') == []
    assert engine.search('убийство')[0] == 'z'
    assert engine.search('') == []


@pytest.mark.parametrize('method', [BM25, CharTFIDF])
def test_baselines_handle_empty_and_ties(method):
    assert method([]).search('query') == []
    docs = [SimpleNamespace(key=k, overview='тайна') for k in 'ba']
    assert method(docs).search('ТАЙНА', limit=1) == ['a']


def test_eval_coverage_and_exact_rank_are_independent():
    row, = evaluate({'baseline': lambda _: ['tv:2']},
                    [{'id':'q','expect':'match','full':['tv:1'],'query':'test'}], {'tv:1','tv:2'})
    assert row['covered']
    assert row['runners']['baseline']['exact_rank'] is None

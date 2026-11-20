import pytest

from candidates.story_semantic import normalized_query
from candidates.story_search import tokens


@pytest.mark.parametrize('query,expected', [
    ('гладиатор Спартаков поднял мятеж', 'гладиатор спартаков поднял мятеж'),
    ('ищу персонажа «Спартаков»?!', 'ищу персонажа спартаков'),
    ('ищу персонажа Спартаков-Сидоров', 'ищу персонажа спартаков сидоров'),
    ('подозреваемый МакГаррет действует', 'подозреваемый макгаррет действует'),
    ('агент Бонд расследует', 'агент бонд расследует'),
    ('пристурник скрывается', 'преступник скрывается'),
    ('Пристурник скрывается', 'преступник скрывается'),
    ('ПРИСТУРНИК СКРЫВАЕТСЯ?!', 'преступник скрывается'),
    ('ограбление?! Пристурник скрывается.', 'ограбление преступник скрывается'),
])
def test_repair_keeps_mid_sentence_proper_name_intent(query, expected):
    vocab = set(tokens('спартака сидорову макгаретом агент бонд поднял мятеж расследует'))
    assert normalized_query(query, vocab) == expected


def test_normalized_output_still_uses_search_token_schema():
    query = 'Ёжик — «Евгений» и Straße_42.'
    assert normalized_query(query, set(tokens(query))) == ' '.join(tokens(query))

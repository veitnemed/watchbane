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

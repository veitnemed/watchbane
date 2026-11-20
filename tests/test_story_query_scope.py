import pytest

from candidates.story_search import (
    OUT_OF_SCOPE_NOTICE,
    StoryDocument,
    StorySearch,
    instructional_non_plot,
)

INSTRUCTIONS = [
    "как настроить статический IP для сетевого прибора",
    "как в редакторе с клавиатуры скопировать вывод терминала?",
    "Как мне обновить драйвер на ноутбуке",
    "как приготовить картофель с грибами",
    "жареная картошка рецепт с грибами",
    "рецепт супа с овощами",
]
PLOTS = [
    "как герой избавляется от преследования",
    "как хакер пытается настроить терминал в захваченном здании",
    "как в фильме компьютер становится злодеем",
    "как в сериале хакеру удалось настроить терминал",
    "Как приручить дракона",
    "Как украсть миллион",
    "Как приготовить любовь",
    "как называется фильм о поваре",
    "что посмотреть про повара и его новый ресторан",
    "фильм про то, как приготовить рискованное блюдо для короля",
    "сериал: программист пытается настроить терминал в космосе",
    "рецепт счастья",
    "подросток узнаёт рецепт пирога от бабушки",
    "«Как приготовить омара»",
]


@pytest.mark.parametrize("query", INSTRUCTIONS)
def test_instructions_are_out_of_scope(query):
    assert instructional_non_plot(query, set())


@pytest.mark.parametrize("query", PLOTS)
def test_plot_and_title_wording_is_not_blocked(query):
    assert not instructional_non_plot(query, set())


def test_exact_local_title_overrides_heuristic():
    movie = StoryDocument("a", "Как приготовить омара", "Повар готовит омара.", "movie", "test")
    engine = StorySearch([movie])
    assert engine.search(movie.title).notice != OUT_OF_SCOPE_NOTICE


def test_both_production_backends_stop_before_retrieval():
    np = pytest.importorskip("numpy")
    from candidates.story_semantic import SemanticStorySearch

    class FakeEncoder:
        variant = "test"

        def encode(self, texts, prefix="passage: "):
            if prefix == "query: ":
                raise AssertionError("Out-of-scope query reached semantic inference")
            return np.zeros((len(texts), 384))

    doc = StoryDocument("a", "A", "Астронавт летит в космос.", "movie", "test")
    semantic = SemanticStorySearch([doc], FakeEncoder())
    lexical = StorySearch([doc])
    for engine in (lexical, semantic):
        for query in INSTRUCTIONS:
            response = engine.search(query)
            assert not response.hits
            assert response.notice == OUT_OF_SCOPE_NOTICE

import pytest

from candidates.story_search import StoryDocument, StorySearch, media_constraints


@pytest.mark.parametrize(("query", "expected"), [
    ("подросток снимает фильм", (None, None)),
    ("сценарист написал сериал про войну", (None, None)),
    ("подросток переснимает фильм 1964 года", (None, None)),
    ("сериал про подростка, который переснимает фильм 1964 года", ("tv", None)),
    ("фильм о режиссёре, чей сериал вышел в 2001 году", ("movie", None)),
    ("как снимали фильм в 1964", (None, None)),
    ("найди, пожалуйста, сериал про войну", ("tv", None)),
    ("ищу фильм 1964 года про войну", ("movie", 1964)),
    ("хочу найти сериал, выпущенный в 2022 году", ("tv", 2022)),
    ("покажи фильм про рыбака, год выпуска: 2017", ("movie", 2017)),
    ("история о путешествии (год выпуска 2019)", (None, 2019)),
    ("сериал или фильм про писателя", (None, None)),
    ("найди фильм или сериал 2014 года про писателя", (None, 2014)),
    ("фильм или сериал про писателя, который переснимает фильм 1964 года", (None, None)),
    ("сериальный актёр снимает документальный фильм", (None, None)),
])
def test_explicit_result_constraints_only(query, expected):
    assert media_constraints(query) == expected


@pytest.mark.parametrize("mode", ["lexical", "semantic"])
def test_nested_media_and_year_do_not_filter_either_search_mode(mode):
    docs = [
        StoryDocument("target", "Target", "Подросток переснимает фильм 1964 года.", "tv", "test", year=2021),
        StoryDocument("other", "Other", "Повар открывает ресторан.", "movie", "test", year=1964),
    ]
    if mode == "semantic":
        np = pytest.importorskip("numpy")
        from candidates.story_semantic import SemanticStorySearch

        class LocalFixtureEncoder:
            variant = "fixture"

            def encode(self, texts, **_kwargs):
                return np.array([(1., 0.) if "подросток" in t.casefold() else (0., 1.)
                                 for t in texts])
        engine = SemanticStorySearch(docs, LocalFixtureEncoder())
    else:
        engine = StorySearch(docs)
    assert next(iter(engine.search("подросток переснимает фильм 1964 года").hits)).document.key == "target"
    assert not engine.search("сериал 1964 года про подростка").hits

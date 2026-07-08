from common.cards import build_watched_movie_card
from desktop.i18n import tr
from desktop.watched.model.filters import filter_entries_by_media_type
from desktop.watched.model.formatters import format_list_label
from desktop.watched.model.load import watched_entry_search_haystack


def test_build_watched_movie_card_exposes_media_type() -> None:
    card = build_watched_movie_card(
        {
            "main_info": {
                "title": "Watchmen",
                "year": 2009,
                "user_score": 8.5,
                "media_type": "movie",
            },
            "raw_scores": {},
        },
        poster_cache={},
    )

    assert card["media_type"] == "movie"


def test_build_watched_movie_card_exposes_movie_runtime() -> None:
    card = build_watched_movie_card(
        {
            "main_info": {
                "title": "Watchmen",
                "year": 2009,
                "user_score": 8.5,
                "media_type": "movie",
                "runtime": 162,
            },
            "raw_scores": {},
            "source_values": {"runtime": 162, "status": "Released"},
        },
        poster_cache={},
    )

    assert card["runtime"] == 162
    assert card["status"] == "Released"


def test_format_list_label_shows_explicit_movie_type() -> None:
    label = format_list_label({
        "title": "Watchmen",
        "year": 2009,
        "user_score": 8.5,
        "media_type": "movie",
    })

    assert label.startswith(f"Watchmen (2009) · {tr('media_type.movie')}")


def test_filter_entries_by_media_type_matches_card_type() -> None:
    series = ("Series", {}, {"title": "Series", "media_type": "tv"})
    movie = ("Movie", {}, {"title": "Movie", "media_type": "movie"})
    entries = [series, movie]

    assert filter_entries_by_media_type(entries, None) == entries
    assert filter_entries_by_media_type(entries, "movie") == [movie]
    assert filter_entries_by_media_type(entries, "tv") == [series]
    assert filter_entries_by_media_type(entries, "unexpected") == entries


def test_watched_entry_search_haystack_includes_media_type() -> None:
    entry = (
        "Watchmen",
        {"main_info": {"title": "Watchmen", "media_type": "movie"}},
        {"title": "Watchmen", "media_type": "movie"},
    )

    assert "movie" in watched_entry_search_haystack(entry)
    assert "фильм" in watched_entry_search_haystack(entry)

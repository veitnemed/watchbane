from common.cards import build_watched_movie_card
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


def test_format_list_label_shows_explicit_movie_type() -> None:
    label = format_list_label({
        "title": "Watchmen",
        "year": 2009,
        "user_score": 8.5,
        "media_type": "movie",
    })

    assert label.startswith("Watchmen (2009) · Movie")


def test_watched_entry_search_haystack_includes_media_type() -> None:
    entry = (
        "Watchmen",
        {"main_info": {"title": "Watchmen", "media_type": "movie"}},
        {"title": "Watchmen", "media_type": "movie"},
    )

    assert "movie" in watched_entry_search_haystack(entry)

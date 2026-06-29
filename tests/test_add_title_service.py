from dataset.add_title_service import (
    build_movie_record_from_defaults,
    build_preview_card_from_defaults,
    build_preview_movie_from_defaults,
)
from config import scheme


def test_build_movie_record_from_defaults_sets_score_and_year() -> None:
    defaults = {
        scheme.MAIN_INFO: {"title": "Test Show", "year": 2020, "user_score": None},
        scheme.RAW_SCORES: {
            "kp_score": 7.5,
            "kp_votes": 1000,
            "imdb_score": 8.0,
            "imdb_votes": 2000,
        },
        scheme.GENRE: {"has_drama": 1},
        scheme.TAGS_VIBE: {},
    }

    movie = build_movie_record_from_defaults(defaults, 9.2, year=2021)

    assert movie["main_info"]["title"] == "Test Show"
    assert movie["main_info"]["user_score"] == 9.2
    assert movie["main_info"]["year"] == 2021
    assert movie["raw_scores"]["imdb_score"] == 8.0


def test_build_preview_card_uses_genre_labels_ru() -> None:
    defaults = {
        scheme.MAIN_INFO: {"title": "Crime Show", "year": 2019, "user_score": None},
        scheme.RAW_SCORES: {
            "kp_score": None,
            "kp_votes": None,
            "imdb_score": None,
            "imdb_votes": None,
        },
        scheme.GENRE: {"has_crime": 1, "has_drama": 0},
        scheme.TAGS_VIBE: {},
    }
    resolved = {"source_values": {"description": "Test overview"}}
    card = build_preview_card_from_defaults(defaults, resolved=resolved)

    assert card["title"] == "Crime Show"
    assert card["year"] == 2019
    assert "Криминал" in (card.get("genres") or [])
    assert card.get("overview") == "Test overview"


def test_build_preview_card_downloads_poster_for_preview(monkeypatch) -> None:
    import tempfile
    from pathlib import Path

    defaults = {
        scheme.MAIN_INFO: {"title": "Poster Show", "year": 2020, "user_score": None},
        scheme.RAW_SCORES: {},
        scheme.GENRE: {},
        scheme.TAGS_VIBE: {},
    }
    poster_hints = {
        "status": "found",
        "poster_url": "https://example.com/preview.jpg",
    }

    with tempfile.TemporaryDirectory() as temp_root:
        image_path = Path(temp_root) / "preview.jpg"

        def fake_download(url: str) -> str:
            image_path.write_bytes(b"poster")
            return str(image_path)

        monkeypatch.setattr(
            "posters.download_images.download_poster_url_for_preview",
            fake_download,
        )

        card = build_preview_card_from_defaults(defaults, poster_hints=poster_hints)

    assert card["poster_url"] == "https://example.com/preview.jpg"
    assert card["poster_src"] == str(image_path)
    assert card["poster_path"] == str(image_path)


def test_add_title_preview_card_profile_is_compact() -> None:
    from desktop.watched_view import (
        ADD_TITLE_PREVIEW_CARD_PROFILE,
        DETAIL_CARD_LAYOUT_PROFILE,
        POSTER_HEIGHT,
        POSTER_WIDTH,
    )

    profile = ADD_TITLE_PREVIEW_CARD_PROFILE
    assert profile.poster_width == POSTER_WIDTH // 2
    assert profile.poster_height == POSTER_HEIGHT // 2
    assert profile.show_user_score is False
    assert profile.include_bottom_stretch is False
    assert profile.rating_widget_size < DETAIL_CARD_LAYOUT_PROFILE.rating_widget_size


def test_add_title_country_combo_has_any_default() -> None:
    from candidates.tmdb_country_options import (
        ADD_TITLE_COUNTRY_ANY_LABEL,
        add_title_country_combo_options,
    )

    options = add_title_country_combo_options()
    assert options[0] == (ADD_TITLE_COUNTRY_ANY_LABEL, "")


def test_build_preview_movie_from_defaults() -> None:
    defaults = {
        scheme.MAIN_INFO: {"title": "Alpha", "year": 2020, "user_score": None},
        scheme.RAW_SCORES: {},
        scheme.GENRE: {},
        scheme.TAGS_VIBE: {},
    }

    movie = build_preview_movie_from_defaults(defaults)

    assert movie["main_info"]["title"] == "Alpha"
    assert movie["main_info"]["user_score"] is None

import copy
import inspect
import tempfile
from pathlib import Path
from unittest.mock import patch

from config import constant
from config import scheme
from common import format_score


def _make_movie(title: str, user_score: float, year: int, raw_score: float = 8.0) -> dict:
    tags_vibe = {feature: 0 for feature in constant.TAGS_VIBE}
    genre_tags = {feature: 0 for feature in constant.GENRE}

    return {
        "main_info": {
            "title": title,
            "user_score": user_score,
            "year": year,
        },
        "raw_scores": {
            "kp_score": raw_score,
            "kp_votes": 120000,
            "imdb_score": raw_score,
            "imdb_votes": 1200,
        },
        "computed_scores": format_score.raw_to_struct(
            {
                "kp_score": raw_score,
                "kp_votes": 120000,
                "imdb_score": raw_score,
                "imdb_votes": 1200,
            },
            {
                "title": title,
                "user_score": user_score,
                "year": year,
            },
        ),
        scheme.TAGS_VIBE: tags_vibe,
        constant.GENRE_SECTION: genre_tags,
    }


def _make_entries() -> list[tuple[str, dict, dict]]:
    from desktop.watched import prepare_card_for_display

    entries = [
        ("Alpha", _make_movie("Alpha", 9.0, 2020, 8.1), None),
        ("Bravo", _make_movie("Bravo", 7.5, 2018, 7.0), None),
        ("Charlie", _make_movie("Charlie", 8.0, 2022, 8.5), None),
    ]
    return [(key, movie, prepare_card_for_display(movie)) for key, movie, _ in entries]


def test_desktop_app_imports_without_window() -> None:
    import desktop.app as app_module

    assert app_module.__name__ == "desktop.app"
    assert callable(app_module.main)
    assert app_module.WatchedMoviesWindow is not None


def test_start_app_entrypoint_is_guarded() -> None:
    import start_app as start_app_module

    assert start_app_module.__name__ != "__main__"
    assert callable(start_app_module.main)


def test_desktop_app_icon_asset_loads(qapp) -> None:
    from desktop.shell.app_icon import APP_ICON_PATH, build_app_icon

    assert APP_ICON_PATH.exists()
    assert build_app_icon().isNull() is False


def test_apply_app_icon_sets_qapplication_icon(qapp) -> None:
    from desktop.shell.app_icon import apply_app_icon

    icon = apply_app_icon(qapp)

    assert icon.isNull() is False
    assert qapp.windowIcon().isNull() is False


def test_score_edit_dialog_is_custom_dark_dialog() -> None:
    import desktop.watched.dialogs.score_edit as dialog_module

    source = inspect.getsource(dialog_module)

    assert "class ScoreEditDialog(QDialog)" in source
    assert "QInputDialog" not in source
    assert "layout_px(390)" in source
    assert "scoreEditCard" in source
    assert "scoreEditSaveButton" in source


def test_add_title_button_opens_wizard_dialog() -> None:
    import desktop.watched.add_title.preview_dialog as preview_module
    import desktop.watched.add_title.search_dialog as search_module
    import desktop.watched.sidebar as sidebar_module
    import desktop.watched.tab as watched_tab_module
    import desktop.watched.tab_actions as actions_module

    sidebar_source = inspect.getsource(sidebar_module.build_watched_sidebar)
    handler_source = inspect.getsource(actions_module.WatchedTabActionsMixin._open_add_title_dialog)
    search_source = inspect.getsource(search_module)
    preview_source = inspect.getsource(preview_module)

    assert "watchedAddTitle" in sidebar_source
    assert "+ Добавить тайтл" in sidebar_source
    assert "run_add_title_flow" in handler_source
    assert "reload_entries" in handler_source
    assert "_show_add_title_stub" not in handler_source
    assert "class AddTitleSearchDialog" in search_source
    assert "class AddTitlePreviewDialog" in preview_source
    assert "run_add_title_flow" in handler_source
    assert "Искать другой" in preview_source


def test_add_title_preview_dialog_uses_readonly_year_and_score_only_save() -> None:
    import desktop.watched.add_title.dialog as dialog_module

    source = inspect.getsource(dialog_module.AddTitlePreviewDialog)
    assert "_year_label" in source
    assert "QSpinBox" not in source
    assert "year=" not in source.replace("resolved_year", "")
    assert "save_add_title_record" in source


def test_add_title_search_dialog_enter_starts_search_without_default_cancel(qapp) -> None:
    from PyQt6.QtCore import Qt
    from PyQt6.QtTest import QTest

    from desktop.watched.add_title.search_dialog import AddTitleSearchDialog

    dialog = AddTitleSearchDialog(initial_title="Триггер")
    calls = []
    dialog._start_search = lambda *, trigger="unknown": calls.append(trigger)

    assert dialog._cancel_button.autoDefault() is False
    assert dialog._cancel_button.isDefault() is False

    QTest.keyClick(dialog._title_input, Qt.Key.Key_Return)

    assert calls == ["enter"]


def test_add_title_search_dialog_reject_defers_while_worker_running(qapp) -> None:
    from desktop.watched.add_title.search_dialog import AddTitleSearchDialog

    class FakeWorker:
        def __init__(self) -> None:
            self.interrupted = False

        def isRunning(self) -> bool:
            return True

        def requestInterruption(self) -> None:
            self.interrupted = True

    dialog = AddTitleSearchDialog(initial_title="Триггер")
    worker = FakeWorker()
    dialog._worker = worker
    dialog._active_request_id = 7

    dialog.reject()

    assert worker.interrupted is True
    assert dialog.result() == 0
    assert dialog._cancel_after_worker is True


def test_prepare_card_for_display_does_not_mutate_movie() -> None:
    from desktop.watched import prepare_card_for_display

    movie = _make_movie("Mutation Check", 8.5, 2019)
    original = copy.deepcopy(movie)

    card = prepare_card_for_display(movie)

    assert movie == original
    assert card["title"] == "Mutation Check"


def test_filter_by_title() -> None:
    from desktop.watched import filter_by_title

    entries = _make_entries()

    filtered = filter_by_title(entries, "brav")

    assert [entry[0] for entry in filtered] == ["Bravo"]


def test_filter_entries_by_user_score_empty() -> None:
    from desktop.watched import filter_entries_by_user_score

    assert filter_entries_by_user_score([], 7.0, 10.0) == []


def test_filter_entries_by_user_score_range() -> None:
    from desktop.watched import filter_entries_by_user_score

    entries = _make_entries()

    filtered = filter_entries_by_user_score(entries, 7.0, 10.0)

    assert [entry[0] for entry in filtered] == ["Alpha", "Bravo", "Charlie"]


def test_filter_entries_by_user_score_narrow_range() -> None:
    from desktop.watched import filter_entries_by_user_score

    entries = _make_entries()

    filtered = filter_entries_by_user_score(entries, 8.0, 8.9)

    assert [entry[0] for entry in filtered] == ["Charlie"]


def test_filter_entries_by_user_score_string_and_invalid_scores() -> None:
    from desktop.watched import filter_entries_by_user_score

    entries = [
        ("String Score", {}, {"title": "String Score", "user_score": "7.5"}),
        ("Missing Score", {}, {"title": "Missing Score"}),
        ("Invalid Score", {}, {"title": "Invalid Score", "user_score": "bad"}),
    ]

    filtered = filter_entries_by_user_score(entries, 7.0, 8.0)

    assert [entry[0] for entry in filtered] == ["String Score"]


def test_filter_entries_by_user_score_swaps_invalid_range() -> None:
    from desktop.watched import filter_entries_by_user_score

    entries = _make_entries()

    filtered = filter_entries_by_user_score(entries, 9.0, 8.0)

    assert [entry[0] for entry in filtered] == ["Alpha", "Charlie"]


def test_filter_entries_by_year_empty() -> None:
    from desktop.watched import filter_entries_by_year

    assert filter_entries_by_year([], 2015, 2026) == []


def test_filter_entries_by_year_range() -> None:
    from desktop.watched import filter_entries_by_year

    entries = _make_entries()

    filtered = filter_entries_by_year(entries, 2015, 2026)

    assert [entry[0] for entry in filtered] == ["Alpha", "Bravo", "Charlie"]


def test_filter_entries_by_year_exact_year() -> None:
    from desktop.watched import filter_entries_by_year

    entries = [
        ("Old", _make_movie("Old", 7.0, 2022), {"title": "Old", "user_score": 7.0, "year": 2022}),
        ("Exact", _make_movie("Exact", 8.0, 2023), {"title": "Exact", "user_score": 8.0, "year": 2023}),
    ]

    filtered = filter_entries_by_year(entries, 2023, 2023)

    assert [entry[0] for entry in filtered] == ["Exact"]


def test_filter_entries_by_year_string_and_invalid_years() -> None:
    from desktop.watched import filter_entries_by_year

    entries = [
        ("String Year", {"main_info": {"year": "2020"}}, {"title": "String Year", "user_score": 7.5}),
        ("Missing Year", {"main_info": {}}, {"title": "Missing Year", "user_score": 8.0}),
        ("Invalid Year", {"main_info": {"year": "abc"}}, {"title": "Invalid Year", "user_score": 8.0}),
    ]

    filtered = filter_entries_by_year(entries, 2019, 2021)

    assert [entry[0] for entry in filtered] == ["String Year"]


def test_filter_entries_by_year_swaps_invalid_range() -> None:
    from desktop.watched import filter_entries_by_year

    entries = _make_entries()

    filtered = filter_entries_by_year(entries, 2022, 2020)

    assert [entry[0] for entry in filtered] == ["Alpha", "Charlie"]


def test_get_available_genres_empty() -> None:
    from desktop.watched import get_available_genres

    assert get_available_genres([]) == []


def test_get_available_genres_sorts_and_hides_empty_duplicates() -> None:
    from desktop.watched import get_available_genres

    entries = [
        ("Alpha", {}, {"title": "Alpha", "genres": ["Драма", "Криминал", "Драма"]}),
        ("Bravo", {}, {"title": "Bravo", "genres": ["Комедия", "", "  "]}),
        ("Charlie", {}, {"title": "Charlie"}),
    ]

    assert get_available_genres(entries) == ["Драма", "Комедия", "Криминал"]


def test_filter_entries_by_genre_no_filter_returns_all() -> None:
    from desktop.watched import GENRE_FILTER_ALL, filter_entries_by_genre

    entries = [
        ("Alpha", {}, {"title": "Alpha", "genres": ["Драма"]}),
        ("Bravo", {}, {"title": "Bravo", "genres": ["Комедия"]}),
    ]

    assert filter_entries_by_genre(entries, None) == entries
    assert filter_entries_by_genre(entries, GENRE_FILTER_ALL) == entries


def test_filter_entries_by_genre_matches_selected_genre() -> None:
    from desktop.watched import filter_entries_by_genre

    entries = [
        ("Alpha", {}, {"title": "Alpha", "genres": ["Драма", "Криминал"]}),
        ("Bravo", {}, {"title": "Bravo", "genres": ["Комедия"]}),
        ("Charlie", {}, {"title": "Charlie"}),
    ]

    filtered = filter_entries_by_genre(entries, "Драма")

    assert [entry[0] for entry in filtered] == ["Alpha"]


def test_filter_entries_by_genre_missing_genre_returns_empty() -> None:
    from desktop.watched import filter_entries_by_genre

    entries = [
        ("Alpha", {}, {"title": "Alpha", "genres": ["Драма"]}),
        ("No Genre", {}, {"title": "No Genre"}),
    ]

    assert filter_entries_by_genre(entries, "Фантастика") == []


def test_apply_view_combines_title_score_year_genre_filter_and_sort() -> None:
    from desktop.watched import apply_view

    entries = [
        *_make_entries(),
        (
            "Bravo Low",
            _make_movie("Bravo Low", 6.0, 2017, 7.0),
            {"title": "Bravo Low", "user_score": 6.0, "year": 2017, "genres": ["Драма"]},
        ),
        (
            "Bravo New",
            _make_movie("Bravo New", 8.5, 2024, 7.0),
            {"title": "Bravo New", "user_score": 8.5, "year": 2024, "genres": ["Драма"]},
        ),
        (
            "Bravo Genre",
            _make_movie("Bravo Genre", 8.2, 2021, 7.0),
            {"title": "Bravo Genre", "user_score": 8.2, "year": 2021, "genres": ["Комедия"]},
        ),
    ]
    entries[1][2]["genres"] = ["Драма"]

    filtered = apply_view(entries, "bravo", "user_score", 7.0, 10.0, 2018, 2023, "Драма")

    assert [entry[0] for entry in filtered] == ["Bravo"]


def test_apply_view_empty_after_year_filter() -> None:
    from desktop.watched import apply_view

    filtered = apply_view(_make_entries(), "", "user_score", 0.0, 10.0, 1990, 1995)

    assert filtered == []


def test_apply_view_sorts_after_year_filter() -> None:
    from desktop.watched import apply_view

    filtered = apply_view(_make_entries(), "", "year", 0.0, 10.0, 2019, 2022)

    assert [entry[0] for entry in filtered] == ["Charlie", "Alpha"]


def test_apply_view_sorts_after_genre_filter() -> None:
    from desktop.watched import apply_view

    entries = [
        ("Older", {}, {"title": "Older", "user_score": 7.0, "year": 2018, "genres": ["Драма"]}),
        ("Newer", {}, {"title": "Newer", "user_score": 9.0, "year": 2022, "genres": ["Драма"]}),
        ("Other", {}, {"title": "Other", "user_score": 10.0, "year": 2023, "genres": ["Комедия"]}),
    ]

    filtered = apply_view(entries, "", "user_score", 0.0, 10.0, 2000, 2026, "Драма")

    assert [entry[0] for entry in filtered] == ["Newer", "Older"]


def test_sort_by_user_score() -> None:
    from desktop.watched import sort_entries

    entries = _make_entries()
    sorted_entries = sort_entries(entries, "user_score")

    assert [entry[0] for entry in sorted_entries] == ["Alpha", "Charlie", "Bravo"]


def test_sort_by_year() -> None:
    from desktop.watched import sort_entries

    entries = _make_entries()
    sorted_entries = sort_entries(entries, "year")

    assert [entry[0] for entry in sorted_entries] == ["Charlie", "Alpha", "Bravo"]


def test_format_user_score_display() -> None:
    from desktop.watched import format_user_score_display

    assert format_user_score_display(8.25) == "8.3"
    assert format_user_score_display(8) == "8.0"
    assert format_user_score_display(None) == "—"


def test_build_meta_pill_items() -> None:
    from desktop.watched import build_meta_pill_items

    items = build_meta_pill_items(
        {
            "year": 2025,
            "tmdb_score": 7.4,
            "final_score": 0.74,
            "imdb_score": 9.9,
            "kp_score": 9.8,
        }
    )

    assert len(items) == 1
    assert items[0]["kind"] == "score_ring"
    assert items[0]["source"] == "tmdb"
    assert items[0]["display_value"] == "7.4"
    assert items[0]["display_label"] == "TMDb"
    assert items[0]["ring_progress"] == 0.74
    assert "footer_label" not in items[0]
    assert "footer_stars" not in items[0]
    assert all(item.get("source") not in {"imdb", "kp"} for item in items)


def test_build_meta_pill_labels() -> None:
    from desktop.watched import build_meta_pill_labels

    pills = build_meta_pill_labels(
        {
            "year": 2025,
            "tmdb_score": 7.34,
            "final_score": 0.74,
        }
    )

    assert pills == ["2025", "TMDb 7.3", "Итог 74"]


def test_normalize_and_format_final_score() -> None:
    from desktop.shared.detail.presenters import final_score_to_stars
    from desktop.watched import format_final_score, normalize_final_score

    assert normalize_final_score(0.74) == 0.74
    assert normalize_final_score(74) == 0.74
    assert normalize_final_score(None) == 0.0
    assert format_final_score(0.74) == "Итог 74"
    assert format_final_score(74) == "Итог 74"
    assert format_final_score(None) == "Итог —"
    assert final_score_to_stars(0.86) == 4.5
    assert final_score_to_stars(60) == 3.0
    assert final_score_to_stars(0.52) == 2.5
    assert final_score_to_stars(None) is None


def test_score_ring_item_uses_tmdb_display_and_tmdb_progress() -> None:
    from desktop.shared.detail.presenters import score_ring_color_for_tmdb_score
    from desktop.watched import build_score_ring_item

    item = build_score_ring_item({"tmdb_score": 7.4, "final_score": 0.74})

    assert item is not None
    assert item["display_value"] == "7.4"
    assert item["display_label"] == "TMDb"
    assert item["ring_progress"] == 0.74
    assert "footer_label" not in item
    assert "footer_stars" not in item
    assert item["accent"] == score_ring_color_for_tmdb_score(7.4)


def test_score_ring_item_ignores_final_score_for_progress_and_color() -> None:
    from desktop.watched import build_score_ring_item

    low_final = build_score_ring_item({"tmdb_score": 7.4, "final_score": 0.1})
    high_final = build_score_ring_item({"tmdb_score": 7.4, "final_score": 0.99})

    assert low_final is not None
    assert high_final is not None
    assert low_final["ring_progress"] == 0.74
    assert high_final["ring_progress"] == 0.74
    assert low_final["accent"] == high_final["accent"]
    assert "Итог" not in str(low_final)
    assert "Итог" not in str(high_final)


def test_final_score_star_item_uses_final_score_only() -> None:
    from desktop.watched import build_final_score_star_item

    item = build_final_score_star_item({"tmdb_score": 7.4, "final_score": 0.74})

    assert item == {
        "kind": "final_stars",
        "stars": 3.5,
        "label": "Хороший рейтинг",
        "tooltip": "Хороший рейтинг",
    }
    assert "Итог" not in str(item)


def test_user_score_badge_is_watched_only() -> None:
    from desktop.watched import build_user_score_badge_item

    assert build_user_score_badge_item({"runtime_status": "watched", "user_score": 9}) == {
        "kind": "user_score_badge",
        "value": "9.0",
        "text": "★ 9.0",
    }
    assert build_user_score_badge_item({"runtime_status": "watched", "user_score": None}) is None
    assert build_user_score_badge_item({"runtime_status": "candidate", "user_score": 9}) is None
    assert build_user_score_badge_item({"user_score": 9}) is None


def test_watched_detail_has_no_my_score_ring_payload() -> None:
    from desktop.watched import build_meta_pill_items

    items = build_meta_pill_items({"runtime_status": "watched", "user_score": 9, "tmdb_score": 7.4})

    assert len(items) == 1
    assert items[0]["source"] == "tmdb"
    assert all(item.get("display_label") != "моя" for item in items)
    assert all(item.get("kind") != "user_score_ring" for item in items)


def test_score_ring_color_uses_theme_cyan_quality_scale() -> None:
    from desktop.watched import score_ring_color_for_final_score
    from desktop.theme import COLOR_ACCENT, COLOR_ACCENT_HOVER

    assert score_ring_color_for_final_score(0) == COLOR_ACCENT.lower()
    assert score_ring_color_for_final_score(1) == COLOR_ACCENT_HOVER.lower()


def test_score_ring_item_accepts_percent_final_score() -> None:
    from desktop.watched import build_score_ring_item

    item = build_score_ring_item({"tmdb_score": 8.9, "final_score": 48})

    assert item is not None
    assert item["display_value"] == "8.9"
    assert item["ring_progress"] == 0.89
    assert "footer_label" not in item
    assert "footer_stars" not in item


def test_score_ring_item_handles_missing_final_score() -> None:
    from desktop.watched import build_score_ring_item

    item = build_score_ring_item({"tmdb_score": 7.4})

    assert item is not None
    assert item["ring_progress"] == 0.74
    assert "footer_label" not in item


def test_score_ring_item_handles_missing_tmdb_score() -> None:
    from desktop.watched import build_score_ring_item

    item = build_score_ring_item({"final_score": 0.74})

    assert item is None


def test_rating_circle_indicator_accepts_tmdb_score_ring_payload(qapp) -> None:
    from desktop.shared.detail.rating_indicator import RatingCircleIndicator

    ring = RatingCircleIndicator(
        "TMDb",
        display_value="7.4",
        display_label="TMDb",
        ring_progress=0.74,
    )

    assert ring._display_value == "7.4"
    assert ring._display_label == "TMDb"
    assert ring._ring_progress == 0.74
    assert not hasattr(ring, "_footer_label")
    assert not hasattr(ring, "_footer_stars")
    assert ring.width() == 88
    assert ring.height() == 88


def test_rating_circle_indicator_keeps_fixed_circle_size(qapp) -> None:
    from desktop.shared.detail.rating_indicator import RatingCircleIndicator

    ring = RatingCircleIndicator("моя")
    original_height = ring.height()

    ring.set_score(9.0)

    assert ring.width() == 88
    assert ring.height() == original_height
    assert ring.height() == 88


def test_meta_pill_does_not_render_final_text_under_circle(qapp) -> None:
    from desktop.shared.detail.card_pills import make_meta_pill
    from desktop.shared.detail.profiles import DETAIL_CARD_LAYOUT_PROFILE

    ring = make_meta_pill(
        {
            "display_value": "7.8",
            "display_label": "TMDb",
            "ring_progress": 0.78,
            "footer_label": "Итог 75",
            "footer_stars": 4.0,
        }
    )

    assert not hasattr(ring, "_footer_label")
    assert not hasattr(ring, "_footer_stars")
    assert ring.width() == DETAIL_CARD_LAYOUT_PROFILE.detail_rating_widget_size
    assert ring.height() == DETAIL_CARD_LAYOUT_PROFILE.detail_rating_widget_size


def test_star_rating_indicator_accepts_stars(qapp) -> None:
    from desktop.shared.detail.rating_indicator import StarRatingIndicator

    stars = StarRatingIndicator()

    stars.set_stars(4.5, "Итог 90")

    assert stars._stars == 4.5
    assert stars.toolTip() == "Итог 90"
    assert stars.isVisible()


def test_build_genre_pill_labels_hides_empty() -> None:
    from desktop.watched import build_genre_pill_labels

    assert build_genre_pill_labels({"genres": []}) == []
    assert build_genre_pill_labels({"genres": ["Драма", "Криминал"]}) == [
        "Драма",
        "Криминал",
    ]


def test_build_detail_info_pill_labels_keeps_only_genres() -> None:
    from desktop.watched import build_detail_info_pill_labels

    assert build_detail_info_pill_labels({"year": 2025, "genres": ["Драма"]}) == ["Драма"]
    assert build_detail_info_pill_labels({"year": 2015.0, "genres": []}) == []
    assert build_detail_info_pill_labels({"genres": ["Драма"]}) == ["Драма"]
    assert build_detail_info_pill_labels({"year": 2025, "genres": ["Драма"], "country": "Россия"}) == [
        "Драма",
    ]


def test_build_main_info_items_formats_type_and_country_only() -> None:
    from desktop.watched import build_main_info_items

    assert build_main_info_items(
        {
            "country": "Россия",
            "year": 2025,
            "object_type": "series",
            "number_of_seasons": 2,
            "number_of_episodes": 16,
            "tmdb_votes": 3456,
            "imdb_votes": 1200,
            "kp_votes": 128536,
        }
    ) == [
        {"label": "Тип", "value": "Сериал"},
        {"label": "Страна", "value": "Россия"},
    ]


def test_build_title_meta_text_formats_year_and_seasons() -> None:
    from desktop.shared.detail import build_title_meta_text

    assert build_title_meta_text(
        {
            "year": 2025,
            "number_of_seasons": 2,
            "number_of_episodes": 16,
        }
    ) == "2025 • 2 сезона / 16 серий"
    assert build_title_meta_text({"year": 2020}) == "2020"
    assert build_title_meta_text({"number_of_seasons": 1, "number_of_episodes": 8}) == "1 сезон / 8 серий"


def test_build_main_info_items_displays_normalized_country_value() -> None:
    from desktop.watched import build_main_info_items

    assert build_main_info_items({"country": "RU, Russia", "object_type": "series"})[1] == {
        "label": "Страна",
        "value": "Россия",
    }


def test_build_main_info_items_hides_empty_votes_and_defaults_type() -> None:
    from desktop.watched import build_main_info_items

    assert build_main_info_items({"imdb_votes": None, "kp_votes": 0}) == [
        {"label": "Тип", "value": "Неизвестно"},
    ]


def test_build_additional_info_items_formats_tmdb_fields() -> None:
    from desktop.shared.detail import build_additional_info_items

    assert build_additional_info_items(
        {
            "number_of_seasons": 2,
            "number_of_episodes": 32,
            "watch_providers": ["Kinopoisk", "Okko"],
            "status": "Ended",
            "episode_run_time": [52],
            "tmdb_votes": 3456,
        }
    ) == [
        {"label": "Где смотреть", "value": "Kinopoisk, Okko"},
        {"label": "Статус", "value": "Завершен"},
        {"label": "Длительность серии", "value": "52 мин"},
        {"label": "Голоса TMDb", "value": "3 456"},
    ]


def test_normalize_object_type_detects_tmdb_tv_shape() -> None:
    from desktop.watched import normalize_object_type

    assert normalize_object_type(None, {"number_of_seasons": 2}) == "Сериал"
    assert normalize_object_type("movie") == "Фильм"
    assert normalize_object_type("unknown") == "Неизвестно"


def test_build_watched_movie_card_includes_main_info_type() -> None:
    from web.export import build_watched_movie_card

    card = build_watched_movie_card(
        {
            "main_info": {"title": "Alpha", "year": 2024, "user_score": 8.0},
            "raw_scores": {
                "kp_score": 7.5,
                "kp_votes": 1200,
                "imdb_score": 7.1,
                "imdb_votes": 900,
                "tmdb_score": 7.8,
                "tmdb_votes": 456,
                "tmdb_popularity": 12.3,
            },
        },
        poster_cache={},
    )

    assert card["object_type"] == "series"
    assert card["tmdb_score"] == 7.8
    assert card["tmdb_votes"] == 456
    assert card["tmdb_popularity"] == 12.3
    assert "kp_score" not in card
    assert "kp_votes" not in card
    assert "imdb_score" not in card
    assert "imdb_votes" not in card


def test_build_watched_movie_card_splits_legacy_combined_genres() -> None:
    from web.export import build_watched_movie_card

    card = build_watched_movie_card(
        {
            "main_info": {"title": "Alpha", "year": 2024, "user_score": 8.0},
            "genres_display": ["Боевик/приключения", "Фантастика/фэнтези"],
        },
        poster_cache={},
    )

    assert card["genres"] == ["Боевик", "Приключения", "Фантастика", "Фэнтези"]


def test_build_watched_movie_card_uses_meta_country_fallback() -> None:
    from web.export import build_export_lookup_cache, build_watched_movie_card

    movie = {
        "main_info": {"title": "Alpha", "year": 2024, "user_score": 8.0},
        "raw_scores": {"kp_score": 7.5, "kp_votes": 1200, "imdb_score": 7.1, "imdb_votes": 900},
    }
    lookup_cache = build_export_lookup_cache(meta={"Alpha": {"main_info": {"country": "США"}}}, pool_by_identity={})

    card = build_watched_movie_card(movie, poster_cache={}, lookup_cache=lookup_cache)

    assert card["country"] == "США"


def test_build_watched_movie_card_normalizes_tmdb_country_codes_for_display() -> None:
    from web.export import build_export_lookup_cache, build_watched_movie_card

    movie = {
        "main_info": {"title": "Alpha", "year": 2024, "user_score": 8.0},
        "raw_scores": {"tmdb_score": 7.5, "tmdb_votes": 60, "tmdb_popularity": 10.0},
    }
    lookup_cache = build_export_lookup_cache(
        meta={
            "Alpha": {
                "countries": ["RU", "Russia"],
                "country_codes": ["RU"],
                "origin_country": ["RU"],
            }
        },
        pool_by_identity={},
    )

    card = build_watched_movie_card(movie, poster_cache={}, lookup_cache=lookup_cache)

    assert card["country"] == "Россия"
    assert "RU" not in card["country"]
    assert "Russia" not in card["country"]


def test_build_watched_movie_card_normalizes_english_country_name_for_display() -> None:
    from web.export import build_watched_movie_card

    card = build_watched_movie_card(
        {
            "main_info": {"title": "Alpha", "year": 2024, "country": "Russia"},
            "raw_scores": {"tmdb_score": 7.5, "tmdb_votes": 60, "tmdb_popularity": 10.0},
        },
        poster_cache={},
    )

    assert card["country"] == "Россия"


def test_build_watched_movie_card_uses_meta_tmdb_fallback() -> None:
    from web.export import build_export_lookup_cache, build_watched_movie_card

    movie = {
        "main_info": {"title": "Alpha", "year": 2024, "user_score": 8.0},
        "raw_scores": {"kp_score": 7.5, "kp_votes": 1200},
    }
    lookup_cache = build_export_lookup_cache(
        meta={
            "Alpha": {
                "main_info": {"country": "США"},
                "raw_scores": {"tmdb_score": 7.9, "tmdb_votes": 321, "tmdb_popularity": 14.5},
            }
        },
        pool_by_identity={},
    )

    card = build_watched_movie_card(movie, poster_cache={}, lookup_cache=lookup_cache)

    assert card["tmdb_score"] == 7.9
    assert card["tmdb_votes"] == 321
    assert card["tmdb_popularity"] == 14.5
    assert "kp_votes" not in card


def test_build_watched_movie_card_uses_meta_additional_info_fallback() -> None:
    from web.export import build_export_lookup_cache, build_watched_movie_card

    movie = {
        "main_info": {"title": "Alpha", "year": 2024, "user_score": 8.0},
        "raw_scores": {},
    }
    lookup_cache = build_export_lookup_cache(
        meta={
            "Alpha": {
                "number_of_seasons": 2,
                "number_of_episodes": 16,
                "episode_run_time": [48],
                "watch_providers": ["Kinopoisk"],
                "status": "Returning Series",
                "in_production": True,
            }
        },
        pool_by_identity={},
    )

    card = build_watched_movie_card(movie, poster_cache={}, lookup_cache=lookup_cache)

    assert card["number_of_seasons"] == 2
    assert card["number_of_episodes"] == 16
    assert card["episode_run_time"] == [48]
    assert card["watch_providers"] == ["Kinopoisk"]
    assert card["status"] == "Returning Series"
    assert card["in_production"] is True


def test_build_watched_movie_card_uses_candidate_pool_tmdb_fallback() -> None:
    from candidates.models.keys import title_identity_key
    from web.export import build_export_lookup_cache, build_watched_movie_card

    movie = {
        "main_info": {"title": "Alpha", "year": 2024, "user_score": 8.0},
        "raw_scores": {"kp_score": 7.5, "kp_votes": 1200},
    }
    candidate = {"title": "Alpha", "year": 2024, "tmdb_score": 8.1, "tmdb_votes": 777, "tmdb_popularity": 21.0}
    lookup_cache = build_export_lookup_cache(
        meta={},
        pool_by_identity={title_identity_key(candidate): candidate},
    )

    card = build_watched_movie_card(movie, poster_cache={}, lookup_cache=lookup_cache)

    assert card["tmdb_score"] == 8.1
    assert card["tmdb_votes"] == 777
    assert card["tmdb_popularity"] == 21.0
    assert "kp_votes" not in card


def test_build_watched_movie_card_computes_tmdb_final_score_for_low_vote_watched_title() -> None:
    from desktop.watched import build_final_score_star_item, build_score_ring_item, build_user_score_badge_item
    from web.export import build_export_lookup_cache, build_watched_movie_card

    movie = {
        "main_info": {"title": "Открытый брак", "year": 2023, "user_score": 4.0},
        "raw_scores": {"tmdb_score": 8.5, "tmdb_votes": 8, "tmdb_popularity": 10.402},
        "genre": {"has_drama": 1, "has_comedy": 1, "has_melodrama": 1},
    }
    meta = {
        "Открытый брак": {
            "main_info": {"country": "Россия"},
            "origin_country": ["RU"],
            "country_codes": ["RU"],
            "original_language": "ru",
            "description": "Описание",
            "overview": "Описание",
            "poster_path": "/poster.jpg",
            "poster_url": "https://image.tmdb.org/t/p/original/poster.jpg",
            "imdb_id": "tt27907967",
        }
    }

    card = build_watched_movie_card(
        movie,
        poster_cache={},
        lookup_cache=build_export_lookup_cache(meta=meta, pool_by_identity={}),
    )
    ring = build_score_ring_item(card)

    assert card["tmdb_score"] == 8.5
    assert card["quality_score"] == 0.4604
    assert card["final_score"] == 0.52
    assert build_user_score_badge_item(card) == {
        "kind": "user_score_badge",
        "value": "4.0",
        "text": "★ 4.0",
    }
    assert ring["display_value"] == "8.5"
    assert ring["ring_progress"] == 0.85
    assert "footer_label" not in ring
    assert "footer_stars" not in ring
    assert build_final_score_star_item(card)["stars"] == 2.5


def test_format_genre_pill_label_unknown_genre() -> None:
    from desktop.watched import format_genre_pill_label

    assert format_genre_pill_label("Документальный") == "Документальный"


def test_build_user_score_update_payload() -> None:
    from desktop.watched import build_user_score_update_payload

    assert build_user_score_update_payload(8.25) == {"main_info": {"user_score": 8.3}}


def test_format_save_user_score_status() -> None:
    from dataset.dataset_records import UpdateRecordResult
    from desktop.watched import format_save_user_score_status

    assert format_save_user_score_status(
        UpdateRecordResult(True, "Alpha", "Запись обновлена.", "updated", ["main_info.user_score"])
    ) == "Оценка сохранена"
    assert format_save_user_score_status(
        UpdateRecordResult(False, "Alpha", "Ошибка обновления!", "invalid_patch", [])
    ) == "Ошибка обновления!"


def test_save_watched_user_score_uses_update_pipeline(monkeypatch) -> None:
    from dataset.dataset_records import UpdateRecordResult
    from desktop.watched import save_watched_user_score

    calls = []

    def fake_update(title, patch, source_name=""):
        calls.append((title, patch, source_name))
        return UpdateRecordResult(True, title, "Запись обновлена.", "updated", ["main_info.user_score"])

    monkeypatch.setattr("dataset.service.update_dataset_record", fake_update)

    result = save_watched_user_score("Dataset Key", 8.5)

    assert result.ok is True
    assert calls == [("Dataset Key", {"main_info": {"user_score": 8.5}}, "desktop_gui")]


def test_save_watched_user_score_does_not_touch_unrelated_artifacts(monkeypatch) -> None:
    from dataset.dataset_records import UpdateRecordResult
    from desktop.watched import save_watched_user_score

    def fail(_payload=None):
        raise AssertionError("desktop score save must not touch unrelated artifacts")

    def fake_update(title, patch, source_name=""):
        return UpdateRecordResult(True, title, "Запись обновлена.", "updated", ["main_info.user_score"])

    monkeypatch.setattr("dataset.service.update_dataset_record", fake_update)
    monkeypatch.setattr("candidates.repositories.pool_repository.save_candidate_pool", fail)

    result = save_watched_user_score("Dataset Key", 8.5)

    assert result.ok is True


def test_get_user_score_spin_value() -> None:
    from desktop.watched import get_user_score_spin_value

    assert get_user_score_spin_value({"user_score": 8.25}) == 8.3
    assert get_user_score_spin_value({"user_score": None}) == 0.0


def test_validate_score_edit_entry() -> None:
    from desktop.watched import validate_score_edit_entry

    assert validate_score_edit_entry(None) == (False, "Запись не выбрана")
    assert validate_score_edit_entry(("  ", {}, {})) == (False, "Запись не выбрана")
    assert validate_score_edit_entry(("Alpha", {}, {})) == (True, "")


def test_get_country_display() -> None:
    from desktop.watched import get_country_display

    assert get_country_display({"country": "Россия"}) == "Россия"
    assert get_country_display({"country": ""}) is None
    assert get_country_display({}) is None


def test_has_overview_text() -> None:
    from desktop.watched import get_overview_display, has_overview_text

    assert has_overview_text({"overview": "Короткое описание."}) is True
    assert get_overview_display({"overview": "  Текст  "}) == "Текст"
    assert has_overview_text({"overview": ""}) is False
    assert has_overview_text({"overview": "   "}) is False
    assert has_overview_text({}) is False


def test_format_watched_list_status() -> None:
    from desktop.watched import format_watched_list_status

    assert format_watched_list_status(12, 12, "") == "Всего 12"
    assert format_watched_list_status(3, 12, "alpha") == "Показано 3 из 12"
    assert format_watched_list_status(3, 12, "", True) == "Показано 3 из 12"
    assert format_watched_list_status(3, 12, "", False, True) == "Показано 3 из 12"
    assert format_watched_list_status(3, 12, "", False, False, True) == "Показано 3 из 12"
    assert format_watched_list_status(0, 12, "missing") == "Ничего не найдено"
    assert format_watched_list_status(0, 12, "", True) == "Ничего не найдено"
    assert format_watched_list_status(0, 12, "", False, True) == "Ничего не найдено"
    assert format_watched_list_status(0, 12, "", False, False, True) == "Ничего не найдено"
    assert format_watched_list_status(0, 0, "") == "Список пуст"


def test_format_watched_list_counter() -> None:
    from desktop.watched import format_watched_list_counter

    assert format_watched_list_counter(12, 12, "") == "Всего 12"
    assert format_watched_list_counter(3, 12, "alpha") == "3 из 12"
    assert format_watched_list_counter(3, 12, "", True) == "3 из 12"
    assert format_watched_list_counter(0, 12, "missing") == "Ничего не найдено"
    assert format_watched_list_counter(0, 0, "") == "Список пуст"


def test_count_active_filters() -> None:
    from desktop.watched import count_active_filters

    assert count_active_filters() == 0
    assert count_active_filters(True, False, False) == 1
    assert count_active_filters(True, True, True) == 3


def test_score_filter_is_active() -> None:
    from desktop.watched import USER_SCORE_MAX, USER_SCORE_MIN, score_filter_is_active

    assert score_filter_is_active(USER_SCORE_MIN, USER_SCORE_MAX) is False
    assert score_filter_is_active(8.0, USER_SCORE_MAX) is True
    assert score_filter_is_active(USER_SCORE_MIN, 7.5) is True


def test_year_filter_is_active() -> None:
    from datetime import date

    from desktop.watched import (
        YEAR_FILTER_DEFAULT_FROM,
        YEAR_FILTER_DEFAULT_TO,
        year_filter_is_active,
    )

    current_year = date.today().year
    assert year_filter_is_active(YEAR_FILTER_DEFAULT_FROM, YEAR_FILTER_DEFAULT_TO) is False
    assert year_filter_is_active(2015, current_year) is True
    assert year_filter_is_active(YEAR_FILTER_DEFAULT_FROM, current_year - 1) is True


def test_genre_filter_is_active() -> None:
    from desktop.watched import GENRE_FILTER_ALL, genre_filter_is_active

    assert genre_filter_is_active(None) is False
    assert genre_filter_is_active(GENRE_FILTER_ALL) is False
    assert genre_filter_is_active("Триллер") is True


def test_watched_filters_are_active_from_ranges() -> None:
    from datetime import date

    from desktop.watched import (
        USER_SCORE_MAX,
        USER_SCORE_MIN,
        YEAR_FILTER_DEFAULT_FROM,
        watched_filters_are_active_from_ranges,
    )

    current_year = date.today().year
    assert (
        watched_filters_are_active_from_ranges(
            USER_SCORE_MIN,
            USER_SCORE_MAX,
            YEAR_FILTER_DEFAULT_FROM,
            current_year,
            None,
        )
        is False
    )
    assert watched_filters_are_active_from_ranges(8.0, USER_SCORE_MAX) is True
    assert watched_filters_are_active_from_ranges(year_from=2015, year_to=current_year) is True
    assert watched_filters_are_active_from_ranges(genre="Триллер") is True
    assert (
        watched_filters_are_active_from_ranges(
            8.0,
            USER_SCORE_MAX,
            2015,
            current_year,
            "Триллер",
        )
        is True
    )


def test_format_watched_filters_label() -> None:
    from desktop.watched import format_watched_filters_label

    assert format_watched_filters_label() == "▸ Фильтры"
    assert format_watched_filters_label(is_expanded=True) == "▾ Фильтры"
    assert format_watched_filters_label(has_score_filter=True) == "▸ Фильтры активны"
    assert format_watched_filters_label(has_year_filter=True, is_expanded=True) == "▾ Фильтры активны"
    assert format_watched_filters_label(has_genre_filter=True) == "▸ Фильтры активны"
    assert " (" not in format_watched_filters_label(has_score_filter=True)


def test_apply_view_after_default_filter_reset_respects_search() -> None:
    from desktop.watched import (
        USER_SCORE_MAX,
        USER_SCORE_MIN,
        YEAR_FILTER_DEFAULT_FROM,
        YEAR_FILTER_DEFAULT_TO,
        apply_view,
    )

    entries = _make_entries()
    narrowed = apply_view(
        entries,
        "",
        "user_score",
        USER_SCORE_MIN,
        USER_SCORE_MAX,
        2022,
        2022,
        None,
    )
    assert [entry[0] for entry in narrowed] == ["Charlie"]

    reset = apply_view(
        entries,
        "bravo",
        "user_score",
        USER_SCORE_MIN,
        USER_SCORE_MAX,
        YEAR_FILTER_DEFAULT_FROM,
        YEAR_FILTER_DEFAULT_TO,
        None,
    )
    assert [entry[0] for entry in reset] == ["Bravo"]


def test_watched_layout_uses_collapsible_filters_and_rich_list() -> None:
    import inspect

    import desktop.watched.filters_panel as filters_panel_module
    import desktop.watched.sidebar as sidebar_module
    import desktop.watched.tab as watched_tab_module
    import desktop.watched.tab_actions as actions_module

    tab_source = inspect.getsource(watched_tab_module.WatchedTabView)
    actions_source = inspect.getsource(actions_module.WatchedTabActionsMixin)
    sidebar_source = inspect.getsource(sidebar_module.build_watched_sidebar)
    filters_source = inspect.getsource(filters_panel_module.WatchedFiltersPanel)

    assert "WatchedFiltersPanel" in sidebar_source
    assert "build_watched_sidebar" in tab_source
    assert "watchedFiltersPanel" in filters_source
    assert "format_watched_filters_label" in filters_source
    assert "watchedFilterResetAll" in filters_source
    assert "WatchedListItemDelegate" in sidebar_source
    assert "watchedListCounter" in sidebar_source
    assert "watchedSortRow" in sidebar_source
    assert "watchedSortLabel" in sidebar_source
    assert "Сортировка" in sidebar_source
    assert "reset_all" in filters_source
    assert "watchedScoreReset" not in filters_source
    assert "watchedYearReset" not in filters_source
    assert "Удалить запись" in actions_source
    assert "_delete_watched_entry" in actions_source
    assert "execute_watched_delete" in actions_source


def test_is_delete_confirmation_valid() -> None:
    from desktop.watched.delete import is_delete_confirmation_valid

    assert is_delete_confirmation_valid("DELETE") is True
    assert is_delete_confirmation_valid(" DELETE ") is True
    assert is_delete_confirmation_valid("delete") is False
    assert is_delete_confirmation_valid("") is False
    assert is_delete_confirmation_valid("REMOVE") is False


def test_format_delete_preview_lines() -> None:
    from desktop.watched.delete import format_delete_preview_lines

    lines = format_delete_preview_lines(
        {
            "title": "Alpha",
            "year": 2020,
            "user_score": 8.0,
            "tmdb_score": 7.8,
            "kp_score": 7.5,
            "imdb_score": 8.1,
            "has_meta": True,
            "has_poster_cache": False,
        }
    )
    assert "Название: Alpha" in lines
    assert "Год: 2020" in lines
    assert "Моя оценка: 8.0" in lines
    assert "TMDb: 7.8" in lines
    assert "КП: 7.5" not in lines
    assert "IMDb: 8.1" not in lines
    assert "Meta: есть" in lines
    assert "Poster-cache: нет" in lines


def test_format_delete_preview_lines_handles_missing_fields() -> None:
    from desktop.watched.delete import format_delete_preview_lines

    lines = format_delete_preview_lines({"title": "No Meta"})
    joined = "\n".join(lines)
    assert "Название: No Meta" in joined
    assert "Meta: нет" in joined
    assert "Poster-cache: нет" in joined
    assert "КП:" not in joined
    assert "IMDb:" not in joined


def test_watched_delete_entry_uses_service_helper() -> None:
    import inspect

    import desktop.watched.tab as watched_tab_module

    source = inspect.getsource(watched_tab_module.WatchedTabView._delete_watched_entry)
    assert "load_delete_preview" in source
    assert "WatchedDeleteDialog" in source
    assert "execute_watched_delete" in source
    assert "storage_data.save_dataset" not in source


def test_watched_detail_card_layout_contract() -> None:
    import inspect

    import desktop.shared.detail.card as watched_view_module

    source = inspect.getsource(watched_view_module.WatchedDetailCard)
    init_source = source.split("def _info_column_content_width", 1)[0]

    assert "info_column.addStretch" not in init_source
    assert "content_layout.addStretch(1)" in init_source
    assert "root.addStretch(1)" not in init_source
    assert "QSizePolicy.Policy.Minimum" in init_source
    assert "setWordWrap(True)" in init_source
    assert "maximumHeight" not in init_source


def test_detail_hero_layout_skeleton(qapp) -> None:
    from PyQt6.QtWidgets import QLabel, QFrame, QWidget

    from desktop.shared.detail import DETAIL_CARD_LAYOUT_PROFILE, WatchedDetailCard

    def is_descendant(child, parent) -> bool:
        current = child
        while current is not None:
            if current is parent:
                return True
            current = current.parent()
        return False

    detail = WatchedDetailCard(profile=DETAIL_CARD_LAYOUT_PROFILE)
    detail.show_entry(
        (
            "Alpha",
            {},
            {
                "title": "Alpha",
                "runtime_status": "watched",
                "tmdb_score": 7.4,
                "final_score": 0.74,
                "genres": ["Драма"],
                "year": 2024,
            },
        )
    )
    qapp.processEvents()

    hero = detail.widget
    poster_column = hero.findChild(QWidget, "detailPosterColumn")
    info_column = hero.findChild(QWidget, "detailInfoColumn")
    poster_shell = hero.findChild(QFrame, "detailPosterShell")
    title = hero.findChild(QLabel, "detailTitle")
    chips = hero.findChild(QWidget, "detailChipsContainer")
    score_row = hero.findChild(QWidget, "detailScoreSummaryRow")

    assert hero.objectName() == "detailHeroCard"
    assert poster_column is not None
    assert info_column is not None
    assert poster_shell is not None
    assert title is not None
    assert chips is not None
    assert score_row is not None
    assert poster_column.width() == DETAIL_CARD_LAYOUT_PROFILE.detail_poster_width
    assert poster_shell.width() == DETAIL_CARD_LAYOUT_PROFILE.detail_poster_width
    assert poster_shell.height() == DETAIL_CARD_LAYOUT_PROFILE.detail_poster_height
    assert info_column.minimumWidth() == DETAIL_CARD_LAYOUT_PROFILE.detail_info_min_width
    assert is_descendant(title, info_column)
    assert is_descendant(chips, info_column)
    assert is_descendant(score_row, info_column)
    assert is_descendant(poster_shell, poster_column)


def test_detail_chip_rows_fit_short_labels_in_one_row(qapp) -> None:
    from PyQt6.QtGui import QFontMetrics

    from desktop.shared.detail.card_pills import build_detail_chip_rows
    from desktop.shared.detail.profiles import DETAIL_CARD_LAYOUT_PROFILE

    rows = build_detail_chip_rows(
        ["2024", "Драма", "Комедия"],
        600,
        DETAIL_CARD_LAYOUT_PROFILE,
        QFontMetrics(qapp.font()),
    )

    assert rows == [["2024", "Драма", "Комедия"]]


def test_detail_chip_rows_use_two_rows_and_overflow(qapp) -> None:
    from PyQt6.QtGui import QFontMetrics

    from desktop.shared.detail.card_pills import build_detail_chip_rows
    from desktop.shared.detail.profiles import DETAIL_CARD_LAYOUT_PROFILE

    rows = build_detail_chip_rows(
        [
            "2024",
            "Криминал",
            "Драма",
            "Детектив",
            "Триллер",
            "Фантастика",
            "Боевик",
        ],
        300,
        DETAIL_CARD_LAYOUT_PROFILE,
        QFontMetrics(qapp.font()),
    )

    assert len(rows) == 2
    assert rows[0][0] == "2024"
    assert any(label.startswith("+") for row in rows for label in row)
    assert all(len(row) > 0 for row in rows)


def test_detail_chip_rows_never_create_third_row(qapp) -> None:
    from PyQt6.QtGui import QFontMetrics

    from desktop.shared.detail.card_pills import build_detail_chip_rows
    from desktop.shared.detail.profiles import DETAIL_CARD_LAYOUT_PROFILE

    rows = build_detail_chip_rows(
        ["2024"] + [f"Жанр {index}" for index in range(20)],
        170,
        DETAIL_CARD_LAYOUT_PROFILE,
        QFontMetrics(qapp.font()),
    )

    assert len(rows) <= 2
    assert rows[0][0] == "2024"
    assert rows[-1][-1].startswith("+")


def test_detail_chip_rows_elide_long_text(qapp) -> None:
    from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

    from desktop.shared.detail.card_pills import fill_detail_chip_rows
    from desktop.shared.detail.profiles import DETAIL_CARD_LAYOUT_PROFILE

    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    long_label = "Очень длинный жанр который точно не помещается"

    fill_detail_chip_rows(
        layout,
        ["2024", long_label],
        240,
        "genrePill",
        DETAIL_CARD_LAYOUT_PROFILE,
    )

    chips = container.findChildren(QLabel, "genrePill")

    assert len(chips) >= 2
    assert chips[0].text() == "2024"
    assert chips[1].text() != long_label
    assert chips[1].toolTip() == long_label
    assert chips[1].width() <= DETAIL_CARD_LAYOUT_PROFILE.detail_chip_max_width


def test_detail_chips_do_not_elide_common_short_labels(qapp) -> None:
    from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

    from desktop.shared.detail.card_pills import fill_detail_chip_rows
    from desktop.shared.detail.profiles import DETAIL_CARD_LAYOUT_PROFILE

    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)

    fill_detail_chip_rows(
        layout,
        ["2020", "Драма", "Триллер", "Боевик"],
        520,
        "genrePill",
        DETAIL_CARD_LAYOUT_PROFILE,
    )

    chips = container.findChildren(QLabel, "genrePill")

    assert [chip.text() for chip in chips] == ["2020", "Драма", "Триллер", "Боевик"]
    assert all(chip.toolTip() == "" for chip in chips)


def test_detail_chips_center_text(qapp) -> None:
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

    from desktop.shared.detail.card_pills import fill_detail_chip_rows
    from desktop.shared.detail.profiles import DETAIL_CARD_LAYOUT_PROFILE

    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)

    fill_detail_chip_rows(
        layout,
        ["2020", "Драма"],
        260,
        "genrePill",
        DETAIL_CARD_LAYOUT_PROFILE,
    )

    chips = container.findChildren(QLabel, "genrePill")

    assert len(chips) == 2
    assert all(chip.alignment() == Qt.AlignmentFlag.AlignCenter for chip in chips)


def test_detail_chips_container_stays_above_score_row(qapp) -> None:
    from PyQt6.QtWidgets import QWidget

    from desktop.shared.detail import DETAIL_CARD_LAYOUT_PROFILE, WatchedDetailCard

    detail = WatchedDetailCard(profile=DETAIL_CARD_LAYOUT_PROFILE)
    detail.show_entry(
        (
            "Alpha",
            {},
            {
                "title": "Alpha",
                "runtime_status": "watched",
                "tmdb_score": 7.4,
                "final_score": 0.74,
                "genres": ["Криминал", "Драма", "Детектив", "Триллер", "Фантастика"],
                "year": 2024,
            },
        )
    )
    qapp.processEvents()

    info_column = detail.widget.findChild(QWidget, "detailInfoColumn")
    chips = detail.widget.findChild(QWidget, "detailChipsContainer")
    score_row = detail.widget.findChild(QWidget, "detailScoreSummaryRow")
    info_layout = info_column.layout()

    assert info_layout.indexOf(chips) < info_layout.indexOf(score_row)


def test_detail_chips_container_height_matches_visible_rows(qapp) -> None:
    from PyQt6.QtWidgets import QWidget

    from desktop.shared.detail import DETAIL_CARD_LAYOUT_PROFILE, WatchedDetailCard

    detail = WatchedDetailCard(profile=DETAIL_CARD_LAYOUT_PROFILE)
    detail._info_column_widget.setFixedWidth(300)
    detail.show_entry(
        (
            "Alpha",
            {},
            {
                "title": "Alpha",
                "runtime_status": "watched",
                "tmdb_score": 7.4,
                "final_score": 0.74,
                "genres": ["Криминал", "Драма", "Детектив", "Триллер", "Фантастика", "Боевик"],
                "year": 2024,
            },
        )
    )
    qapp.processEvents()

    chips = detail.widget.findChild(QWidget, "detailChipsContainer")
    expected_height = DETAIL_CARD_LAYOUT_PROFILE.detail_chip_height

    assert chips.layout().count() == 1
    assert chips.height() == expected_height


def test_watched_detail_card_hides_overview_without_text() -> None:
    import inspect

    import desktop.shared.detail.card as watched_view_module

    source = inspect.getsource(watched_view_module.WatchedDetailCard.show_entry)
    init_source = inspect.getsource(watched_view_module.WatchedDetailCard.__init__)
    assert "has_overview_text(card)" in source
    assert "_overview_frame.setVisible(False)" in source
    assert "detailOverviewDivider" in init_source
    assert "detail_overview_top_gap" in init_source


def test_detail_overview_section_renders_description(qapp) -> None:
    from PyQt6.QtWidgets import QLabel, QFrame

    from desktop.shared.detail import DETAIL_CARD_LAYOUT_PROFILE, WatchedDetailCard

    detail = WatchedDetailCard(profile=DETAIL_CARD_LAYOUT_PROFILE)
    detail.show_entry(
        (
            "Alpha",
            {},
            {
                "title": "Alpha",
                "runtime_status": "watched",
                "overview": "Короткое описание тайтла.",
            },
        )
    )
    qapp.processEvents()

    section = detail.widget.findChild(QFrame, "detailOverviewSection")
    divider = detail.widget.findChild(QFrame, "detailOverviewDivider")
    header = detail.widget.findChild(QLabel, "detailOverviewHeader")
    text = detail.widget.findChild(QLabel, "detailOverviewText")

    assert section is not None
    assert section.isHidden() is False
    assert divider is not None
    assert header is not None
    assert header.text() == "ОПИСАНИЕ"
    assert text is not None
    assert text.text() == "Короткое описание тайтла."
    assert text.wordWrap() is True


def test_detail_overview_section_hides_without_description(qapp) -> None:
    from PyQt6.QtWidgets import QFrame

    from desktop.shared.detail import DETAIL_CARD_LAYOUT_PROFILE, WatchedDetailCard

    detail = WatchedDetailCard(profile=DETAIL_CARD_LAYOUT_PROFILE)
    detail.show_entry(
        (
            "Alpha",
            {},
            {
                "title": "Alpha",
                "runtime_status": "watched",
                "overview": "   ",
            },
        )
    )
    qapp.processEvents()

    section = detail.widget.findChild(QFrame, "detailOverviewSection")

    assert section is not None
    assert section.isHidden() is True


def test_detail_overview_section_is_below_top_row(qapp) -> None:
    from PyQt6.QtWidgets import QFrame, QWidget

    from desktop.shared.detail import DETAIL_CARD_LAYOUT_PROFILE, WatchedDetailCard

    detail = WatchedDetailCard(profile=DETAIL_CARD_LAYOUT_PROFILE)
    detail.show_entry(
        (
            "Alpha",
            {},
            {
                "title": "Alpha",
                "runtime_status": "watched",
                "overview": "Описание",
            },
        )
    )
    qapp.processEvents()

    top_row = detail.widget.findChild(QWidget, "detailTopRow")
    content = detail.widget.findChild(QWidget, "detailContentContainer")
    section = detail.widget.findChild(QFrame, "detailOverviewSection")

    assert top_row is not None
    assert content is not None
    assert section is not None
    content_layout = content.layout()
    assert content_layout.indexOf(top_row) < content_layout.indexOf(section)


def test_detail_card_uses_profile_composition_widths(qapp) -> None:
    from PyQt6.QtWidgets import QFrame, QWidget

    from desktop.shared.detail import DETAIL_CARD_LAYOUT_PROFILE, WatchedDetailCard

    detail = WatchedDetailCard(profile=DETAIL_CARD_LAYOUT_PROFILE)

    content = detail.widget.findChild(QWidget, "detailContentContainer")
    info_column = detail.widget.findChild(QWidget, "detailInfoColumn")
    overview = detail.widget.findChild(QFrame, "detailOverviewSection")
    main_info = detail.widget.findChild(QWidget, "detailMainInfoSection")
    additional_info = detail.widget.findChild(QWidget, "detailAdditionalInfoSection")

    assert content.maximumWidth() == DETAIL_CARD_LAYOUT_PROFILE.detail_content_max_width
    assert info_column.maximumWidth() == DETAIL_CARD_LAYOUT_PROFILE.detail_info_column_max_width
    assert overview.maximumWidth() == DETAIL_CARD_LAYOUT_PROFILE.detail_overview_max_width
    assert main_info.maximumWidth() == DETAIL_CARD_LAYOUT_PROFILE.detail_section_max_width
    assert additional_info.maximumWidth() == DETAIL_CARD_LAYOUT_PROFILE.detail_section_max_width


def test_detail_content_container_is_horizontally_centered(qapp) -> None:
    import desktop.settings.app_settings  # noqa: F401 — preload before theme.shared imports
    import desktop.theme.scaling as scaling

    scaling.set_ui_scale(1.0)

    from PyQt6.QtCore import QPoint
    from PyQt6.QtWidgets import QWidget

    from desktop.shared.detail import DETAIL_CARD_LAYOUT_PROFILE, WatchedDetailCard

    detail = WatchedDetailCard(profile=DETAIL_CARD_LAYOUT_PROFILE)
    frame = detail.widget
    content = frame.findChild(QWidget, "detailContentContainer")
    assert content is not None
    frame.show()
    qapp.processEvents()

    padding = DETAIL_CARD_LAYOUT_PROFILE.detail_hero_card_padding
    frame.resize(1400, 900)
    qapp.processEvents()

    available_width = frame.width() - (2 * padding)
    content_left = content.mapTo(frame, QPoint(0, 0)).x()
    expected_x = padding + (available_width - content.width()) // 2
    assert abs(content_left - expected_x) <= 1

    frame.resize(800, 900)
    qapp.processEvents()

    content_left = content.mapTo(frame, QPoint(0, 0)).x()
    content_right = content.mapTo(frame, QPoint(content.width(), 0)).x()
    assert content_left >= padding
    assert content_right <= frame.width() - padding


def test_detail_overview_uses_profile_left_inset(qapp) -> None:
    from PyQt6.QtWidgets import QFrame

    from desktop.shared.detail import DETAIL_CARD_LAYOUT_PROFILE, WatchedDetailCard

    detail = WatchedDetailCard(profile=DETAIL_CARD_LAYOUT_PROFILE)
    section = detail.widget.findChild(QFrame, "detailOverviewSection")
    margins = section.layout().contentsMargins()

    assert margins.left() == DETAIL_CARD_LAYOUT_PROFILE.detail_overview_left_inset


def test_detail_overview_has_no_absolute_positioning() -> None:
    import inspect

    import desktop.shared.detail.card as watched_view_module

    init_source = inspect.getsource(watched_view_module.WatchedDetailCard.__init__)
    overview_source = init_source[
        init_source.index('setObjectName("detailOverviewSection")') :
        init_source.index("info_column.addWidget")
    ]

    assert ".move(" not in overview_source
    assert "setGeometry(" not in overview_source


def test_watched_detail_card_renders_main_info_block() -> None:
    import inspect

    import desktop.shared.detail.card as watched_view_module

    init_source = inspect.getsource(watched_view_module.WatchedDetailCard.__init__)
    show_source = inspect.getsource(watched_view_module.WatchedDetailCard.show_entry)
    empty_source = inspect.getsource(watched_view_module.WatchedDetailCard.show_empty)

    assert "ОСНОВНАЯ ИНФОРМАЦИЯ" in init_source
    assert 'setObjectName("detailMainInfoSection")' in init_source
    assert 'setObjectName("detailMainInfoPanel")' in init_source
    assert 'setObjectName("detailMainInfoHeader")' in init_source
    assert "build_main_info_items(card)" in show_source
    assert "_set_main_info_items([])" in empty_source


def test_detail_main_info_panel_renders_known_rows(qapp) -> None:
    from PyQt6.QtWidgets import QLabel, QFrame, QWidget

    from desktop.shared.detail import DETAIL_CARD_LAYOUT_PROFILE, WatchedDetailCard

    detail = WatchedDetailCard(profile=DETAIL_CARD_LAYOUT_PROFILE)
    detail.show_entry(
        (
            "Alpha",
            {},
            {
                "title": "Alpha",
                "runtime_status": "watched",
                "tmdb_score": 7.4,
                "final_score": 0.74,
                "country": "US",
                "object_type": "series",
                "year": 2025,
                "number_of_seasons": 2,
                "number_of_episodes": 16,
                "tmdb_votes": 12850,
            },
        )
    )
    qapp.processEvents()

    section = detail.widget.findChild(QWidget, "detailMainInfoSection")
    header = detail.widget.findChild(QLabel, "detailMainInfoHeader")
    panel = detail.widget.findChild(QFrame, "detailMainInfoPanel")
    labels = [item.text() for item in panel.findChildren(QLabel, "detailMainInfoLabel")]
    values = [item.text() for item in panel.findChildren(QLabel, "detailMainInfoValue")]

    assert section is not None
    assert section.isHidden() is False
    assert header is not None
    assert header.text() == "ОСНОВНАЯ ИНФОРМАЦИЯ"
    assert panel is not None
    assert labels == ["Тип", "Страна"]
    assert "Сериал" in values
    assert "США" in values


def test_detail_title_meta_renders_year_and_seasons_under_title(qapp) -> None:
    from PyQt6.QtWidgets import QLabel, QWidget

    from desktop.shared.detail import DETAIL_CARD_LAYOUT_PROFILE, WatchedDetailCard

    detail = WatchedDetailCard(profile=DETAIL_CARD_LAYOUT_PROFILE)
    detail.show_entry(
        (
            "Alpha",
            {},
            {
                "title": "Alpha",
                "year": 2025,
                "number_of_seasons": 2,
                "number_of_episodes": 16,
            },
        )
    )
    qapp.processEvents()

    title = detail.widget.findChild(QLabel, "detailTitle")
    meta = detail.widget.findChild(QLabel, "detailTitleMeta")
    info_column = detail.widget.findChild(QWidget, "detailInfoColumn")
    title_block = detail.widget.findChild(QWidget, "detailTitleBlock")

    assert title is not None
    assert meta is not None
    assert info_column is not None
    assert title_block is not None
    assert meta.text() == "2025 • 2 сезона / 16 серий"
    assert meta.isHidden() is False
    assert info_column.layout().indexOf(title_block) >= 0
    assert title_block.layout().spacing() == DETAIL_CARD_LAYOUT_PROFILE.detail_title_meta_gap
    assert title_block.layout().indexOf(detail._title_row_widget) < title_block.layout().indexOf(meta)


def test_detail_additional_info_panel_renders_known_rows(qapp) -> None:
    from PyQt6.QtWidgets import QLabel, QFrame, QWidget

    from desktop.shared.detail import DETAIL_CARD_LAYOUT_PROFILE, WatchedDetailCard

    detail = WatchedDetailCard(profile=DETAIL_CARD_LAYOUT_PROFILE)
    detail.show_entry(
        (
            "Alpha",
            {},
            {
                "title": "Alpha",
                "runtime_status": "watched",
                "number_of_seasons": 2,
                "number_of_episodes": 32,
                "watch_providers": ["Kinopoisk"],
                "status": "Ended",
                "episode_run_time": [52],
                "tmdb_votes": 12850,
            },
        )
    )
    qapp.processEvents()

    section = detail.widget.findChild(QWidget, "detailAdditionalInfoSection")
    header = detail.widget.findChild(QLabel, "detailAdditionalInfoHeader")
    panel = detail.widget.findChild(QFrame, "detailAdditionalInfoPanel")
    labels = [item.text() for item in panel.findChildren(QLabel, "detailAdditionalInfoLabel")]
    values = [item.text() for item in panel.findChildren(QLabel, "detailAdditionalInfoValue")]

    assert section is not None
    assert section.isHidden() is False
    assert header is not None
    assert header.text() == "ДОПОЛНИТЕЛЬНАЯ ИНФОРМАЦИЯ"
    assert labels == ["Где смотреть", "Статус", "Длительность серии", "Голоса TMDb"]
    assert values == ["Kinopoisk", "Завершен", "52 мин", "12 850"]


def test_detail_additional_info_section_has_top_gap(qapp) -> None:
    from PyQt6.QtWidgets import QWidget

    from desktop.shared.detail import DETAIL_CARD_LAYOUT_PROFILE, WatchedDetailCard

    detail = WatchedDetailCard(profile=DETAIL_CARD_LAYOUT_PROFILE)
    section = detail.widget.findChild(QWidget, "detailAdditionalInfoSection")
    margins = section.layout().contentsMargins()

    assert margins.top() == DETAIL_CARD_LAYOUT_PROFILE.detail_additional_info_top_gap


def test_detail_main_info_section_hides_when_empty(qapp) -> None:
    from PyQt6.QtWidgets import QWidget

    from desktop.shared.detail import DETAIL_CARD_LAYOUT_PROFILE, WatchedDetailCard

    detail = WatchedDetailCard(profile=DETAIL_CARD_LAYOUT_PROFILE)
    detail._set_main_info_items([])
    qapp.processEvents()

    section = detail.widget.findChild(QWidget, "detailMainInfoSection")

    assert section is not None
    assert section.isHidden() is True


def test_detail_main_info_panel_is_below_score_row(qapp) -> None:
    from PyQt6.QtWidgets import QWidget

    from desktop.shared.detail import DETAIL_CARD_LAYOUT_PROFILE, WatchedDetailCard

    detail = WatchedDetailCard(profile=DETAIL_CARD_LAYOUT_PROFILE)
    detail.show_entry(
        (
            "Alpha",
            {},
            {
                "title": "Alpha",
                "runtime_status": "watched",
                "tmdb_score": 7.4,
                "final_score": 0.74,
                "country": "US",
                "object_type": "series",
            },
        )
    )
    qapp.processEvents()

    info_column = detail.widget.findChild(QWidget, "detailInfoColumn")
    score_row = detail.widget.findChild(QWidget, "detailScoreSummaryRow")
    main_info = detail.widget.findChild(QWidget, "detailMainInfoSection")
    info_layout = info_column.layout()

    assert info_layout.indexOf(score_row) < info_layout.indexOf(main_info)


def test_watched_detail_card_does_not_render_my_score_ring() -> None:
    import inspect

    import desktop.shared.detail.card as watched_view_module

    init_source = inspect.getsource(watched_view_module.WatchedDetailCard.__init__)

    assert 'score_summary_widget.setObjectName("detailScoreSummaryRow")' in init_source
    assert 'self._final_score_stars_block.setObjectName("detailFinalScoreStars")' in init_source
    assert 'RatingCircleIndicator("моя"' not in init_source
    assert "self._metrics_row.addWidget(self._score_indicator" not in init_source
    assert "StarRatingIndicator(" in init_source
    assert "star_size=self._profile.detail_star_size" in init_source
    assert "star_gap=self._profile.detail_star_gap" in init_source
    assert "_rating_stars_row" not in init_source
    assert "_tmdb_ring_slot.setFixedSize(" in init_source
    assert "self._profile.detail_rating_widget_size," in init_source
    assert "self._score_summary_row.addWidget" in init_source


def test_watched_score_summary_row_contains_tmdb_ring_and_stars(qapp) -> None:
    from PyQt6.QtWidgets import QWidget

    from desktop.shared.detail import DETAIL_CARD_LAYOUT_PROFILE, WatchedDetailCard

    detail = WatchedDetailCard(profile=DETAIL_CARD_LAYOUT_PROFILE)
    detail.show_entry(
        (
            "Alpha",
            {},
            {
                "title": "Alpha",
                "runtime_status": "watched",
                "user_score": 9,
                "tmdb_score": 7.4,
                "final_score": 0.74,
            },
        )
    )
    qapp.processEvents()

    score_row = detail.widget.findChild(QWidget, "detailScoreSummaryRow")
    tmdb_ring = detail.widget.findChild(QWidget, "detailTmdbScoreRing")
    stars_block = detail.widget.findChild(QWidget, "detailFinalScoreStars")

    assert score_row is not None
    assert tmdb_ring is not None
    assert stars_block is not None
    assert tmdb_ring.parent() is not stars_block
    assert stars_block.isHidden() is False
    assert getattr(tmdb_ring, "_display_label") == "TMDb"
    assert getattr(tmdb_ring, "_display_value") == "7.4"
    assert getattr(tmdb_ring, "_ring_progress") == 0.74
    assert not any(getattr(child, "_display_label", "") == "моя" for child in score_row.findChildren(QWidget))


def test_candidate_score_summary_row_contains_tmdb_ring_and_stars(qapp) -> None:
    from PyQt6.QtWidgets import QWidget

    from desktop.shared.detail import CANDIDATE_DETAIL_CARD_PROFILE, WatchedDetailCard

    detail = WatchedDetailCard(profile=CANDIDATE_DETAIL_CARD_PROFILE)
    detail.show_entry(("Candidate", {}, {"title": "Candidate", "tmdb_score": 8.1, "final_score": 0.82}))
    qapp.processEvents()

    score_row = detail.widget.findChild(QWidget, "detailScoreSummaryRow")
    tmdb_ring = detail.widget.findChild(QWidget, "detailTmdbScoreRing")
    stars_block = detail.widget.findChild(QWidget, "detailFinalScoreStars")

    assert score_row is not None
    assert tmdb_ring is not None
    assert stars_block is not None
    assert stars_block.isHidden() is False
    assert getattr(tmdb_ring, "_display_label") == "TMDb"
    assert getattr(tmdb_ring, "_ring_progress") == 0.81


def test_score_summary_area_has_no_raw_final_score_text(qapp) -> None:
    from PyQt6.QtWidgets import QLabel, QWidget

    from desktop.shared.detail import DETAIL_CARD_LAYOUT_PROFILE, WatchedDetailCard

    detail = WatchedDetailCard(profile=DETAIL_CARD_LAYOUT_PROFILE)
    detail.show_entry(
        (
            "Alpha",
            {},
            {
                "title": "Alpha",
                "runtime_status": "watched",
                "user_score": 9,
                "tmdb_score": 7.4,
                "final_score": 0.74,
            },
        )
    )
    qapp.processEvents()

    score_row = detail.widget.findChild(QWidget, "detailScoreSummaryRow")

    assert score_row is not None
    assert "Итог" not in score_row.objectName()
    assert all("Итог" not in label.text() for label in score_row.findChildren(QLabel))


def test_detail_card_poster_shell_exists(qapp) -> None:
    from PyQt6.QtWidgets import QFrame, QLabel

    from desktop.shared.detail import DETAIL_CARD_LAYOUT_PROFILE, WatchedDetailCard

    detail = WatchedDetailCard(profile=DETAIL_CARD_LAYOUT_PROFILE)
    shell = detail.widget.findChild(QFrame, "detailPosterShell")
    poster = detail.widget.findChild(QLabel, "detailPoster")

    assert shell is not None
    assert poster is not None
    assert shell.parent() is detail._poster_column_widget
    assert shell.width() == DETAIL_CARD_LAYOUT_PROFILE.detail_poster_width
    assert shell.height() == DETAIL_CARD_LAYOUT_PROFILE.detail_poster_height
    assert poster.width() == DETAIL_CARD_LAYOUT_PROFILE.detail_poster_content_width
    assert poster.height() == DETAIL_CARD_LAYOUT_PROFILE.detail_poster_content_height


def test_watched_user_score_badge_is_poster_shell_overlay(qapp) -> None:
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QLabel, QFrame

    from desktop.shared.detail import DETAIL_CARD_LAYOUT_PROFILE, WatchedDetailCard

    detail = WatchedDetailCard(profile=DETAIL_CARD_LAYOUT_PROFILE)
    detail.show_entry(
        (
            "Alpha",
            {},
            {
                "title": "Alpha",
                "runtime_status": "watched",
                "user_score": 9,
            },
        )
    )
    qapp.processEvents()

    shell = detail.widget.findChild(QFrame, "detailPosterShell")
    badge = detail.widget.findChild(QLabel, "detailUserScoreBadge")

    assert shell is not None
    assert badge is not None
    assert badge.parent() is shell
    assert badge.text() == "★ 9.0"
    assert badge.isHidden() is False
    assert badge.testAttribute(Qt.WidgetAttribute.WA_StyledBackground) is True
    assert badge.x() >= shell.width() - badge.width() - DETAIL_CARD_LAYOUT_PROFILE.detail_user_score_badge_right - 1
    assert badge.y() == DETAIL_CARD_LAYOUT_PROFILE.detail_user_score_badge_top


def test_watched_user_score_badge_has_readable_background() -> None:
    import inspect

    import desktop.shared.detail.card as detail_card_module
    from desktop.theme import COLOR_RATING, COLOR_SCORE_BADGE_BG
    from desktop.theme.styles.detail_card import build_detail_card_style

    style = build_detail_card_style()
    init_source = inspect.getsource(detail_card_module.WatchedDetailCard.__init__)

    assert "QLabel#detailUserScoreBadge" in style
    assert f"background-color: {COLOR_SCORE_BADGE_BG}" in style
    assert f"border: 1px solid {COLOR_RATING}" in style
    assert "class UserScoreBadgeLabel(QLabel)" in init_source
    assert "drawRoundedRect" in init_source
    assert "QColor(COLOR_SCORE_BADGE_BG)" in init_source


def test_watched_user_score_badge_hides_without_user_score(qapp) -> None:
    from PyQt6.QtWidgets import QLabel

    from desktop.shared.detail import DETAIL_CARD_LAYOUT_PROFILE, WatchedDetailCard

    detail = WatchedDetailCard(profile=DETAIL_CARD_LAYOUT_PROFILE)
    detail.show_entry(("Alpha", {}, {"title": "Alpha", "runtime_status": "watched"}))
    qapp.processEvents()

    badge = detail.widget.findChild(QLabel, "detailUserScoreBadge")

    assert badge is not None
    assert badge.text() == ""
    assert badge.isHidden() is True


def test_candidate_detail_card_never_shows_user_score_badge(qapp) -> None:
    from PyQt6.QtWidgets import QLabel, QFrame

    from desktop.shared.detail import CANDIDATE_DETAIL_CARD_PROFILE, WatchedDetailCard

    detail = WatchedDetailCard(profile=CANDIDATE_DETAIL_CARD_PROFILE)
    detail.show_entry(("Candidate", {}, {"title": "Candidate", "user_score": 9, "tmdb_score": 7.2}))
    qapp.processEvents()

    shell = detail.widget.findChild(QFrame, "detailPosterShell")
    badge = detail.widget.findChild(QLabel, "detailUserScoreBadge")

    assert shell is not None
    assert badge is not None
    assert badge.parent() is shell
    assert badge.text() == ""
    assert badge.isHidden() is True


def test_candidate_detail_actions_are_icon_only_under_poster() -> None:
    import inspect

    import desktop.shared.detail.card as watched_view_module

    init_source = inspect.getsource(watched_view_module.WatchedDetailCard.__init__)

    assert 'QPushButton("👁")' not in init_source
    assert 'QPushButton("Hide")' not in init_source
    assert 'QPushButton()' in init_source
    assert 'make_detail_action_icon("eye"' in init_source
    assert 'make_detail_action_icon("hide"' in init_source
    assert "self._poster_actions_layout.addWidget" in init_source
    assert "poster_column.addWidget(self._poster_actions_widget)" in init_source
    assert "title_row.addWidget(self._poster_actions_widget" not in init_source
    assert "self._metrics_row.addWidget(self._mark_watched_button" not in init_source
    assert "self._metrics_row.addWidget(self._hide_button" not in init_source


def test_candidate_detail_actions_are_poster_descendants(qapp) -> None:
    from PyQt6.QtWidgets import QPushButton, QWidget

    from desktop.shared.detail import CANDIDATE_DETAIL_CARD_PROFILE, WatchedDetailCard

    def is_descendant(child, parent) -> bool:
        current = child
        while current is not None:
            if current is parent:
                return True
            current = current.parent()
        return False

    detail = WatchedDetailCard(profile=CANDIDATE_DETAIL_CARD_PROFILE)
    detail.show_entry(("Candidate", {}, {"title": "Candidate", "tmdb_score": 7.2, "final_score": 0.62}))
    qapp.processEvents()

    poster_actions = detail.widget.findChild(QWidget, "detailPosterActions")
    title_actions = detail.widget.findChild(QWidget, "detailTitleActions")
    mark_button = detail.widget.findChild(QPushButton, "candidateMarkWatchedButton")
    hide_button = detail.widget.findChild(QPushButton, "candidateHideButton")

    assert poster_actions is not None
    assert poster_actions.parent() is detail._poster_column_widget
    assert mark_button is not None
    assert hide_button is not None
    assert is_descendant(mark_button, poster_actions)
    assert is_descendant(hide_button, poster_actions)
    assert is_descendant(mark_button, detail._poster_column_widget)
    assert is_descendant(hide_button, detail._poster_column_widget)
    if title_actions is not None:
        assert not is_descendant(mark_button, title_actions)
        assert not is_descendant(hide_button, title_actions)


def test_candidate_detail_action_click_handlers_still_work(qapp) -> None:
    from PyQt6.QtWidgets import QPushButton

    from desktop.shared.detail import CANDIDATE_DETAIL_CARD_PROFILE, WatchedDetailCard

    calls: list[str] = []
    detail = WatchedDetailCard(profile=CANDIDATE_DETAIL_CARD_PROFILE)
    detail.set_mark_watched_handler(lambda: calls.append("watched"))
    detail.set_hide_handler(lambda: calls.append("hide"))
    detail.show_entry(("Candidate", {}, {"title": "Candidate", "tmdb_score": 7.2, "final_score": 0.62}))
    qapp.processEvents()

    mark_button = detail.widget.findChild(QPushButton, "candidateMarkWatchedButton")
    hide_button = detail.widget.findChild(QPushButton, "candidateHideButton")

    assert mark_button is not None
    assert hide_button is not None
    assert mark_button.isEnabled()
    assert hide_button.isEnabled()

    mark_button.click()
    hide_button.click()

    assert calls == ["watched", "hide"]


def test_build_score_count_html_smoke() -> None:
    from desktop.analytics.charts import build_score_count_html

    html = build_score_count_html(
        [
            {
                "score": 8.5,
                "count": 3,
                "example_titles": ["Alpha", "Bravo"],
                "extra_count": 0,
            }
        ]
    )

    assert "plotly" in html.lower()


def test_build_score_distribution_html_smoke() -> None:
    from desktop.analytics.charts import build_score_distribution_html

    html = build_score_distribution_html(
        [
            {
                "label": "7.0-7.9",
                "count": 3,
                "percent": 60.0,
                "example_titles": ["Alpha", "Bravo"],
                "extra_count": 0,
            }
        ]
    )

    assert "plotly" in html.lower()
    assert "7.0-7.9" in html


def test_build_genre_count_html_smoke() -> None:
    from desktop.analytics.charts import build_genre_count_html

    html = build_genre_count_html(
        [{"label": "Драма", "count": 5, "example_titles": ["Alpha"], "extra_count": 0}]
    )

    assert "plotly" in html.lower()
    assert "bar" in html.lower()


def test_build_year_average_html_smoke() -> None:
    from desktop.analytics.charts import build_year_average_html

    html = build_year_average_html(
        [
            {"year": 2020, "average": 8.0, "count": 3},
            {"year": 2021, "average": 7.5, "count": 2},
        ]
    )

    assert "plotly" in html.lower()
    assert "2020" in html


def test_analytics_view_removes_imdb_delta_report() -> None:
    import inspect

    import desktop.analytics.view as analytics_view_module

    source = inspect.getsource(analytics_view_module.AnalyticsView)
    assert "_fill_imdb_delta" not in source
    assert "_render_imdb_delta_list" not in source
    assert "build_imdb_delta_html" not in source


def test_analytics_style_includes_list_expand_button() -> None:
    from desktop.theme import build_analytics_style

    style = build_analytics_style()
    assert "QPushButton#analyticsListExpand" in style


def test_analytics_update_entries_uses_only_genres_and_constructor() -> None:
    import inspect

    import desktop.analytics.view as analytics_view_module

    source = inspect.getsource(analytics_view_module.AnalyticsView.update_entries)
    assert "get_pool_genre_count_rows" in source
    assert "build_genre_count_rows" in source
    assert "_render_chart_constructor" in source
    assert "build_score_analytics" not in source
    assert "_fill_year_average" not in source
    assert "_fill_rating_lower" not in source


def test_analytics_mvp_sections_wired() -> None:
    import inspect

    import desktop.analytics.view as analytics_view_module

    init_source = inspect.getsource(analytics_view_module.AnalyticsView.__init__)
    assert "Количество тайтлов по жанрам" in init_source
    assert "Количество тайтлов по жанрам (pool)" in init_source
    assert "Конструктор графика" in init_source
    assert "Средняя моя оценка по годам" not in init_source
    assert "Я сильно ниже IMDb" not in init_source
    assert "Отличие моих оценок от IMDb" not in init_source
    assert "Я сильно выше IMDb" not in init_source
    assert "Подозрительные оценки" not in init_source

    update_source = inspect.getsource(analytics_view_module.AnalyticsView.update_entries)
    assert "_fill_genre_count" in update_source
    assert "_fill_pool_genre_count" in update_source
    assert "_render_chart_constructor" in update_source
    assert "_fill_year_average" not in update_source
    assert "_fill_rating_lower" not in update_source
    assert "_fill_imdb_delta" not in update_source
    assert "_fill_rating_higher" not in update_source
    assert "_fill_suspicious" not in update_source


def test_analytics_hides_dataset_completeness_block() -> None:
    import inspect

    import desktop.analytics.view as analytics_view_module

    init_source = inspect.getsource(analytics_view_module.AnalyticsView.__init__)
    source = inspect.getsource(analytics_view_module.AnalyticsView)
    assert "completenessHeadline" not in init_source
    assert "completenessSubline" not in init_source
    assert "_fill_completeness" not in source


def test_score_count_chart_height_matches_plotly_constant() -> None:
    from desktop.analytics.charts import CHART_BASE_HEIGHT, SCORE_CHART_HEIGHT, build_score_count_figure

    figure = build_score_count_figure([{"score": 8.5, "count": 2, "example_titles": ["A"], "extra_count": 0}])
    assert SCORE_CHART_HEIGHT == CHART_BASE_HEIGHT
    assert figure.layout.height == CHART_BASE_HEIGHT
    assert figure.data[0].fill == "tozeroy"


def test_bar_chart_height_scales_with_rows() -> None:
    from desktop.analytics.charts import CHART_BASE_HEIGHT, bar_chart_height

    assert bar_chart_height(0) == CHART_BASE_HEIGHT
    assert bar_chart_height(3) == CHART_BASE_HEIGHT
    assert bar_chart_height(20) > CHART_BASE_HEIGHT


def test_analytics_plotly_view_uses_chart_object_name() -> None:
    import inspect

    import desktop.analytics.view as analytics_view_module

    source = inspect.getsource(analytics_view_module.AnalyticsView._fill_plotly_chart)
    assert "ANALYTICS_PLOTLY_OBJECT_NAME" in source
    assert analytics_view_module.ANALYTICS_PLOTLY_OBJECT_NAME == "analyticsPlotlyChart"


def test_analytics_style_includes_plotly_chart_selector() -> None:
    from desktop.theme import build_analytics_style

    style = build_analytics_style()
    assert "QWebEngineView#analyticsPlotlyChart" in style


def test_analytics_constructor_controls_are_wired() -> None:
    import inspect

    import desktop.analytics.view as analytics_view_module

    source = inspect.getsource(analytics_view_module.AnalyticsView._build_chart_constructor_controls)
    assert "chartConstructorControls" in source
    assert "chartConstructorCombo" in source
    assert "chartConstructorBuildButton" in source
    assert "Просмотренные тайтлы" in source
    assert "Candidate pool" in source
    assert "Оценка пользователя" in source
    assert "TMDb рейтинг" in source
    assert "Функция" in source
    assert "Построить график" in source


def test_analytics_insights_use_bullet_rows() -> None:
    import inspect

    import desktop.analytics.view as analytics_view_module

    source = inspect.getsource(analytics_view_module.AnalyticsView._make_insight_line)
    assert "insightBullet" in source
    assert "insightRow" in source


def test_analytics_section_headers_use_icons() -> None:
    import inspect

    import desktop.analytics.view as analytics_view_module

    source = inspect.getsource(analytics_view_module.AnalyticsView._make_section_header)
    assert "sectionHeaderIconBadge" in source
    assert "sectionTitle" in source


def test_format_list_label() -> None:
    from desktop.watched import format_list_label, format_year_display

    assert format_list_label({"title": "Alpha", "year": 2020, "user_score": 8.0}) == "Alpha (2020)  ·  8.0"
    assert format_list_label({"title": "Float Year", "year": 2015.0, "user_score": 8.0}) == (
        "Float Year (2015)  ·  8.0"
    )
    assert format_list_label({"title": "No Year", "user_score": None}) == "No Year"
    assert format_list_label({"year": 2019, "user_score": 7.5}) == "Без названия (2019)  ·  7.5"
    assert format_year_display(2015.0) == "2015"
    assert format_year_display("2015.0") == "2015"
    assert format_year_display("2015") == "2015"


def test_format_rating_score_display() -> None:
    from desktop.watched import format_rating_score_display

    assert format_rating_score_display(8.25) == "8.3"
    assert format_rating_score_display(None) is None
    assert format_rating_score_display("bad") is None


def test_normalize_user_score_value() -> None:
    from desktop.watched import normalize_user_score_value

    assert normalize_user_score_value(8.25) == 8.3
    assert normalize_user_score_value(7.0) == 7.0


def test_sort_entries_by_title() -> None:
    from desktop.watched import sort_entries

    entries = _make_entries()
    sorted_entries = sort_entries(entries, "title")
    assert [entry[0] for entry in sorted_entries] == ["Alpha", "Bravo", "Charlie"]


def test_poster_display_dimensions_are_scaled() -> None:
    import importlib

    import desktop.settings.app_settings  # noqa: F401
    import desktop.theme.scaling as scaling

    scaling.set_ui_scale(1.0)
    scaling._scale_tuning = {
        "ui": 1.0,
        "font": 1.0,
        "layout": 1.0,
        "control": 1.0,
        "list": 1.0,
        "detail": 1.0,
        "poster": 1.0,
    }
    profiles_module = importlib.reload(importlib.import_module("desktop.shared.detail.profiles"))
    POSTER_BASE_HEIGHT = profiles_module.POSTER_BASE_HEIGHT
    POSTER_BASE_WIDTH = profiles_module.POSTER_BASE_WIDTH
    POSTER_DISPLAY_SCALE = profiles_module.POSTER_DISPLAY_SCALE
    POSTER_HEIGHT = profiles_module.POSTER_HEIGHT
    POSTER_WIDTH = profiles_module.POSTER_WIDTH

    assert POSTER_WIDTH == int(POSTER_BASE_WIDTH * POSTER_DISPLAY_SCALE)
    assert POSTER_HEIGHT == int(POSTER_BASE_HEIGHT * POSTER_DISPLAY_SCALE)
    assert POSTER_WIDTH == 275
    assert POSTER_HEIGHT == 412


def test_detail_hero_contract_tokens_are_available() -> None:
    import importlib

    import desktop.settings.app_settings  # noqa: F401
    import desktop.theme.scaling as scaling
    from desktop import theme

    scaling.set_ui_scale(1.0)
    scaling._scale_tuning = {
        "ui": 1.0,
        "font": 1.0,
        "layout": 1.0,
        "control": 1.0,
        "list": 1.0,
        "detail": 1.0,
        "poster": 1.0,
    }
    profiles_module = importlib.reload(importlib.import_module("desktop.shared.detail.profiles"))
    DETAIL_CARD_LAYOUT_PROFILE = profiles_module.DETAIL_CARD_LAYOUT_PROFILE

    expected_tokens = {
        "DETAIL_HERO_CARD_RADIUS": 24,
        "DETAIL_HERO_CARD_PADDING": 28,
        "DETAIL_HERO_MIN_WIDTH": 980,
        "DETAIL_HERO_PREFERRED_MIN_WIDTH": 1200,
        "DETAIL_CONTENT_MAX_WIDTH": 1120,
        "DETAIL_POSTER_WIDTH": 360,
        "DETAIL_POSTER_HEIGHT": 530,
        "DETAIL_POSTER_RADIUS": 16,
        "DETAIL_POSTER_BORDER_WIDTH": 1,
        "DETAIL_POSTER_RIGHT_GAP": 42,
        "DETAIL_INFO_MIN_WIDTH": 440,
        "DETAIL_INFO_MAX_WIDTH": 760,
        "DETAIL_INFO_COLUMN_MAX_WIDTH": 700,
        "DETAIL_TITLE_FONT_FAMILY": "Segoe UI",
        "DETAIL_TITLE_FONT_FALLBACK": "Arial, sans-serif",
        "DETAIL_TITLE_FONT_SIZE": 34,
        "FONT_DETAIL_MAIN_INFO_HEADER": 17,
        "FONT_DETAIL_MAIN_INFO_LABEL": 17,
        "FONT_DETAIL_MAIN_INFO_VALUE": 18,
        "FONT_DETAIL_OVERVIEW_TEXT": 19,
        "DETAIL_TITLE_LINE_HEIGHT": 42,
        "DETAIL_TITLE_MAX_LINES": 2,
        "DETAIL_CHIP_HEIGHT": 36,
        "DETAIL_CHIP_RADIUS": 18,
        "DETAIL_CHIP_H_PADDING": 20,
        "DETAIL_CHIP_ROW_GAP": 10,
        "DETAIL_CHIP_COL_GAP": 14,
        "DETAIL_CHIP_MAX_ROWS": 2,
        "DETAIL_CHIP_MAX_WIDTH": 170,
        "DETAIL_SCORE_ROW_TOP_GAP": 34,
        "DETAIL_RATING_WIDGET_SIZE": 136,
        "DETAIL_RATING_CIRCLE_DIAMETER": 122,
        "DETAIL_STARS_LEFT_GAP": 52,
        "DETAIL_STAR_SIZE": 36,
        "DETAIL_STAR_GAP": 9,
        "DETAIL_USER_SCORE_BADGE_MIN_WIDTH": 80,
        "DETAIL_USER_SCORE_BADGE_HEIGHT": 40,
        "DETAIL_USER_SCORE_BADGE_RADIUS": 20,
        "DETAIL_USER_SCORE_BADGE_TOP": 16,
        "DETAIL_USER_SCORE_BADGE_RIGHT": 16,
        "DETAIL_USER_SCORE_BADGE_PADDING_X": 14,
        "DETAIL_MAIN_INFO_TOP_GAP": 38,
        "DETAIL_MAIN_INFO_PANEL_RADIUS": 16,
        "DETAIL_MAIN_INFO_PANEL_PADDING_X": 28,
        "DETAIL_MAIN_INFO_PANEL_PADDING_Y": 18,
        "DETAIL_MAIN_INFO_ROW_HEIGHT": 54,
        "DETAIL_MAIN_INFO_LABEL_WIDTH": 230,
        "DETAIL_OVERVIEW_TOP_GAP": 28,
        "DETAIL_OVERVIEW_LEFT_INSET": 0,
        "DETAIL_OVERVIEW_TITLE_TOP_GAP": 28,
        "DETAIL_OVERVIEW_TEXT_TOP_GAP": 20,
        "DETAIL_OVERVIEW_MAX_LINES_COLLAPSED": 4,
        "DETAIL_OVERVIEW_MAX_WIDTH": 920,
        "DETAIL_SECTION_MAX_WIDTH": 920,
    }

    for token_name, expected_value in expected_tokens.items():
        assert getattr(theme, token_name) == expected_value

    assert DETAIL_CARD_LAYOUT_PROFILE.detail_poster_width == theme.DETAIL_POSTER_WIDTH
    assert DETAIL_CARD_LAYOUT_PROFILE.detail_poster_border_width == theme.DETAIL_POSTER_BORDER_WIDTH
    assert DETAIL_CARD_LAYOUT_PROFILE.detail_poster_content_width == theme.DETAIL_POSTER_WIDTH - 2
    assert DETAIL_CARD_LAYOUT_PROFILE.detail_poster_content_radius == theme.DETAIL_POSTER_RADIUS - 1
    assert DETAIL_CARD_LAYOUT_PROFILE.detail_rating_widget_size == theme.DETAIL_RATING_WIDGET_SIZE
    assert DETAIL_CARD_LAYOUT_PROFILE.detail_user_score_badge_height == theme.DETAIL_USER_SCORE_BADGE_HEIGHT
    assert DETAIL_CARD_LAYOUT_PROFILE.detail_overview_left_inset == theme.DETAIL_OVERVIEW_LEFT_INSET
    assert DETAIL_CARD_LAYOUT_PROFILE.detail_content_max_width == theme.DETAIL_CONTENT_MAX_WIDTH
    assert DETAIL_CARD_LAYOUT_PROFILE.detail_info_column_max_width == theme.DETAIL_INFO_COLUMN_MAX_WIDTH
    assert DETAIL_CARD_LAYOUT_PROFILE.detail_overview_max_width == theme.DETAIL_OVERVIEW_MAX_WIDTH
    assert DETAIL_CARD_LAYOUT_PROFILE.detail_section_max_width == theme.DETAIL_SECTION_MAX_WIDTH


def test_detail_card_style_uses_requested_font_sizes() -> None:
    from desktop.theme.scaling import set_ui_scale
    from desktop.theme.styles.detail_card import build_detail_card_style

    set_ui_scale(1.0)
    style = build_detail_card_style()

    assert "QLabel#detailTitle" in style
    assert "font-size: 34px;" in style
    assert "QLabel#detailTitleMeta" in style
    assert "font-size: 17px;" in style
    assert "QLabel#detailMainInfoHeader" in style
    assert "font-size: 17px;" in style
    assert "font-size: 18px;" in style
    assert "QLabel#detailOverviewText" in style
    assert "font-size: 19px;" in style
    assert "QLabel#detailAdditionalInfoHeader" in style
    assert "font-size: 20px;" in style


def test_fit_poster_pixmap_for_display_avoids_upscale(qapp) -> None:
    from PyQt6.QtGui import QImage, QPixmap

    from desktop.shared.detail import POSTER_HEIGHT, POSTER_WIDTH, fit_poster_pixmap_for_display

    small = QPixmap.fromImage(QImage(100, 150, QImage.Format.Format_RGB32))
    result = fit_poster_pixmap_for_display(small, POSTER_WIDTH, POSTER_HEIGHT)

    assert result.width() == 100
    assert result.height() == 150


def test_fit_poster_pixmap_for_display_downscales_large_image(qapp) -> None:
    from PyQt6.QtGui import QImage, QPixmap

    from desktop.shared.detail import POSTER_HEIGHT, POSTER_WIDTH, fit_poster_pixmap_for_display

    large = QPixmap.fromImage(QImage(800, 1200, QImage.Format.Format_RGB32))
    result = fit_poster_pixmap_for_display(large, POSTER_WIDTH, POSTER_HEIGHT)

    assert result.width() <= POSTER_WIDTH
    assert result.height() <= POSTER_HEIGHT
    assert result.width() < 800
    assert result.height() < 1200


def test_watched_detail_card_uses_cover_crop_poster_helper() -> None:
    import inspect

    import desktop.shared.detail.card as watched_view_module
    import desktop.shared.detail.card_poster as poster_module

    source = inspect.getsource(watched_view_module.WatchedDetailCard._sync_poster_display)
    poster_source = inspect.getsource(poster_module.cover_crop_poster_pixmap_for_display)
    assert "cover_crop_poster_pixmap_for_display" in source
    assert "KeepAspectRatioByExpanding" in poster_source
    assert ".copy(" in poster_source
    assert "_target_poster_height" not in source


def test_cover_crop_poster_pixmap_rounds_corners(qapp) -> None:
    from PyQt6.QtGui import QColor, QImage, QPixmap

    from desktop.shared.detail.card_poster import cover_crop_poster_pixmap_for_display

    source_image = QImage(40, 60, QImage.Format.Format_ARGB32)
    source_image.fill(QColor("#ff0000"))

    result = cover_crop_poster_pixmap_for_display(
        QPixmap.fromImage(source_image),
        40,
        60,
        radius=12,
    )
    result_image = result.toImage()

    assert result.width() == 40
    assert result.height() == 60
    assert result_image.pixelColor(0, 0).alpha() == 0
    assert result_image.pixelColor(20, 30).alpha() == 255


def test_detail_poster_styles_keep_border_on_shell_only() -> None:
    import desktop.settings.app_settings  # noqa: F401
    import desktop.theme.scaling as scaling
    from desktop.theme.styles.detail_card import (
        build_detail_card_style,
        build_poster_image_style,
        build_poster_placeholder_style,
    )
    from desktop.theme import COLOR_BORDER_HOVER

    scaling.set_ui_scale(1.0)
    scaling._scale_tuning = {
        "ui": 1.0,
        "font": 1.0,
        "layout": 1.0,
        "control": 1.0,
        "list": 1.0,
        "detail": 1.0,
        "poster": 1.0,
    }
    detail_style = build_detail_card_style()
    placeholder_style = build_poster_placeholder_style()
    image_style = build_poster_image_style()

    assert "QFrame#detailPosterShell" in detail_style
    assert f"border: 1px solid {COLOR_BORDER_HOVER};" in detail_style
    assert "border: none" in placeholder_style
    assert "border-radius: 15px" in placeholder_style
    assert "border-radius: 15px" in image_style


def test_format_poster_path_display() -> None:
    from desktop.watched import format_poster_path_display

    assert format_poster_path_display(None) == "Локальный файл не найден"
    short = "D:/cache/posters/images/alpha.jpg"
    assert format_poster_path_display(short) == short
    long_path = "D:/very/long/cache/posters/images/" + ("a" * 40) + ".jpg"
    display = format_poster_path_display(long_path, max_len=30)
    assert len(display) <= 30
    assert "…" in display
    assert display.endswith(".jpg")


def test_open_path_in_shell_opens_existing_file(monkeypatch) -> None:
    from desktop.watched import open_path_in_shell

    opened: list[str] = []

    def fake_open_file(path: str) -> None:
        opened.append(path)

    monkeypatch.setattr("storage.files.open_file", fake_open_file)

    with tempfile.TemporaryDirectory() as temp_root:
        target = Path(temp_root) / "poster.jpg"
        target.write_bytes(b"x")
        ok, error = open_path_in_shell(str(target))

    assert ok is True
    assert error is None
    assert opened == [str(target)]


def test_open_path_in_shell_missing_path() -> None:
    from desktop.watched import open_path_in_shell

    ok, error = open_path_in_shell("D:/missing/poster-cache/images/nope.jpg")

    assert ok is False
    assert error is not None


def test_watched_detail_card_has_poster_context_menu() -> None:
    import inspect

    import desktop.shared.detail.card as watched_view_module

    init_source = inspect.getsource(watched_view_module.WatchedDetailCard.__init__)
    assert "CustomContextMenu" in init_source
    assert "_show_poster_context_menu" in init_source

    menu_source = inspect.getsource(watched_view_module.WatchedDetailCard._show_poster_context_menu)
    assert "Открыть постер" in menu_source
    assert "Папка poster-cache" in menu_source

    show_source = inspect.getsource(watched_view_module.WatchedDetailCard.show_entry)
    assert "_set_local_poster_path" in show_source


def test_resolve_local_poster_path_prefers_existing_file() -> None:
    from desktop.watched import resolve_local_poster_path

    with tempfile.TemporaryDirectory() as temp_root:
        poster = Path(temp_root) / "poster.jpg"
        poster.write_bytes(b"x")
        card = {"poster_path": str(poster)}
        assert resolve_local_poster_path({}, card) == str(poster)


def test_resolve_local_poster_path_ignores_http_urls() -> None:
    from desktop.watched import resolve_local_poster_path

    assert resolve_local_poster_path({"poster_src": "https://example.com/a.jpg"}, {}) is None
    assert resolve_local_poster_path({"poster_path": "http://example.com/b.jpg"}, {}) is None


def test_resolve_local_poster_path_reads_nested_poster_dict() -> None:
    from desktop.watched import resolve_local_poster_path

    with tempfile.TemporaryDirectory() as temp_root:
        poster = Path(temp_root) / "nested.jpg"
        poster.write_bytes(b"x")
        movie = {"poster": {"path": str(poster)}}
        assert resolve_local_poster_path(movie) == str(poster)


def test_resolve_local_poster_path_uses_preview_cache_for_poster_url() -> None:
    from desktop.watched import resolve_local_poster_path

    poster_url = "https://image.tmdb.org/t/p/w500/example.jpg"
    with tempfile.TemporaryDirectory() as temp_root:
        preview = Path(temp_root) / "preview.jpg"
        preview.write_bytes(b"x")
        card = {"poster_url": poster_url}

        def fake_preview_path(url: str) -> str | None:
            if url == poster_url:
                return str(preview)
            return None

        with patch("posters.download_images.local_preview_poster_path_if_cached", fake_preview_path):
            assert resolve_local_poster_path({}, card) == str(preview)


def test_watched_list_delegate_uses_poster_resolver() -> None:
    import inspect

    import desktop.shared.detail.list_delegate as watched_view_module

    source = inspect.getsource(watched_view_module.WatchedListItemDelegate.__new__)
    assert "resolve_local_poster_path" in source
    assert "format_user_score_display" in source


def test_format_delete_status_message() -> None:
    from desktop.watched.delete import format_delete_status_message

    assert format_delete_status_message({"ok": True}) == "Запись удалена"
    assert format_delete_status_message({"ok": False, "message": "Ошибка сервиса"}) == "Ошибка сервиса"
    assert format_delete_status_message({"ok": False}) == "Не удалось удалить запись"


def test_format_delete_preview_lines_includes_local_poster() -> None:
    from desktop.watched.delete import format_delete_preview_lines

    lines = format_delete_preview_lines(
        {
            "title": "Alpha",
            "poster_local_path": "posters/alpha.jpg",
        }
    )
    assert any("Локальный постер: posters/alpha.jpg" in line for line in lines)


def test_load_delete_preview_with_inline_dataset() -> None:
    from desktop.watched.delete import load_delete_preview

    data = {"Alpha": _make_movie("Alpha", 8.0, 2020)}
    preview = load_delete_preview("Alpha", data=data)
    assert preview is not None
    assert preview["dataset_key"] == "Alpha"
    assert preview["title"] == "Alpha"
    assert preview["year"] == 2020
    assert preview["user_score"] == 8.0


def test_load_delete_preview_returns_none_for_missing_key() -> None:
    from desktop.watched.delete import load_delete_preview

    assert load_delete_preview("Missing", data={}) is None


def test_execute_watched_delete_delegates_to_service(monkeypatch) -> None:
    from desktop.watched.delete import execute_watched_delete

    calls: list[str] = []

    def fake_delete(dataset_key: str) -> dict:
        calls.append(dataset_key)
        return {"ok": True, "dataset_key": dataset_key}

    monkeypatch.setattr("desktop.watched.delete.service.delete_watched_record", fake_delete)
    result = execute_watched_delete("Alpha")
    assert calls == ["Alpha"]
    assert result["ok"] is True


def test_build_delete_dialog_style_contains_selectors() -> None:
    from desktop.theme import build_delete_dialog_style

    style = build_delete_dialog_style()
    assert "deleteRecordDialog" in style
    assert "deleteRecordConfirmButton" in style
    assert "deleteRecordConfirmInput" in style


def test_watched_delete_dialog_contract() -> None:
    import inspect

    import desktop.watched.dialogs.delete_dialog as delete_dialog_module

    source = inspect.getsource(delete_dialog_module.WatchedDeleteDialog)
    assert "deleteRecordDialog" in source
    assert "is_delete_confirmation_valid" in source
    assert "setEnabled(False)" in source
    assert "dialog.exec()" not in source


def test_watched_delete_dialog_button_state_logic() -> None:
    import inspect

    import desktop.watched.dialogs.delete_dialog as delete_dialog_module

    source = inspect.getsource(delete_dialog_module.WatchedDeleteDialog._update_delete_button_state)
    assert "is_delete_confirmation_valid" in source
    assert "setEnabled" in source


def test_watched_delete_dialog_on_accept_requires_confirmation() -> None:
    import inspect

    import desktop.watched.dialogs.delete_dialog as delete_dialog_module

    source = inspect.getsource(delete_dialog_module.WatchedDeleteDialog._on_accept)
    assert "is_delete_confirmation_valid" in source
    assert "self.accept()" in source


def test_delete_watched_entry_handles_cancel_and_missing_preview() -> None:
    import inspect

    import desktop.watched.tab as watched_tab_module

    source = inspect.getsource(watched_tab_module.WatchedTabView._delete_watched_entry)
    assert "validate_score_edit_entry" in source
    assert "preview is None" in source
    assert "dialog.exec()" in source
    assert "QDialog.DialogCode.Accepted" in source


def test_refresh_after_user_score_save_wiring() -> None:
    import inspect

    import desktop.watched.tab as watched_tab_module

    source = inspect.getsource(watched_tab_module.WatchedTabView._refresh_after_user_score_save)
    assert "_reload_watched_search_index" in source
    assert "resolve_selection_row" in source
    assert "_model_view.refresh" not in source


def test_refresh_after_delete_wiring() -> None:
    import inspect

    import desktop.watched.tab as watched_tab_module

    source = inspect.getsource(watched_tab_module.WatchedTabView._refresh_after_delete)
    assert "load_watched_entries" in source
    assert "_filters.reload_genre_options" in source
    assert "_reload_watched_search_index" in source
    assert "resolve_selection_row" in source
    assert "_model_view.refresh" not in source
    assert "_show_empty_details" in source
    assert "format_delete_status_message" in source


def test_desktop_has_no_model_tab_wiring() -> None:
    import inspect

    import desktop.shell.main_window as app_module

    init_source = inspect.getsource(app_module.WatchedMoviesWindow.__init__)
    module_source = inspect.getsource(app_module)
    assert "ModelView" not in module_source
    assert '"Модель"' not in init_source
    assert "_model_view.refresh" not in module_source


def test_open_list_context_menu_includes_delete_action() -> None:
    import inspect

    import desktop.watched.tab as watched_tab_module

    source = inspect.getsource(watched_tab_module.WatchedTabView._open_list_context_menu)
    assert "Удалить запись" in source
    assert "_delete_watched_entry" in source
    assert "Изменить оценку" in source


def test_format_candidate_list_label_shows_sort_metric() -> None:
    from desktop.candidates.presenters import (
        format_candidate_list_label,
        format_candidate_metric_value,
        format_candidate_title_line,
    )

    candidate = {
        "title": "Test Show",
        "year": 2020,
        "final_score": 8.4,
        "tmdb_score": 8.1,
        "tmdb_votes": 12000,
        "tmdb_popularity": 33.5,
    }
    assert format_candidate_title_line(candidate) == "Test Show (2020)"
    assert format_candidate_metric_value(candidate, "final_score") == "Итог 8.4"
    assert format_candidate_metric_value(candidate, "tmdb_votes") == "TMDb 12 000"
    label = format_candidate_list_label(candidate, "final_score")
    assert "Test Show (2020)" in label
    assert "Итог 8.4" in label
    assert "incomplete" not in label
    assert "Q " not in label


def test_build_candidate_readonly_card_passes_main_info_fields(monkeypatch) -> None:
    from desktop.watched import build_user_score_badge_item
    from desktop.candidates.presenters import build_candidate_readonly_card

    monkeypatch.setattr(
        "desktop.candidates.presenters.resolve_local_poster_path_for_candidate",
        lambda candidate: None,
    )
    card = build_candidate_readonly_card(
        {
            "title": "Test Show",
            "year": 2020,
            "country_display": "Россия",
            "number_of_seasons": 2,
            "tmdb_score": 8.1,
            "tmdb_votes": 12000,
            "imdb_id": "tt123",
            "user_score": 9.0,
        }
    )

    assert card["country"] == "Россия"
    assert card["object_type"] == "series"
    assert card["tmdb_score"] == 8.1
    assert card["tmdb_votes"] == 12000
    assert card["imdb_id"] == "tt123"
    assert "kp_votes" not in card
    assert build_user_score_badge_item(card) is None
    assert "user_score_badge" not in card
    assert "imdb_votes" not in card


def test_build_candidate_readonly_card_normalizes_country_for_display(monkeypatch) -> None:
    from desktop.candidates.presenters import build_candidate_readonly_card

    monkeypatch.setattr(
        "desktop.candidates.presenters.resolve_local_poster_path_for_candidate",
        lambda candidate: None,
    )

    card = build_candidate_readonly_card(
        {
            "title": "Test Show",
            "year": 2020,
            "countries": ["RU", "Russia"],
            "country_codes": ["RU"],
            "tmdb_score": 8.1,
            "tmdb_votes": 12000,
        }
    )

    assert card["country"] == "Россия"


def test_build_candidate_readonly_card_ignores_tmdb_scripted_type(monkeypatch) -> None:
    from desktop.candidates.presenters import build_candidate_readonly_card

    monkeypatch.setattr(
        "desktop.candidates.presenters.resolve_local_poster_path_for_candidate",
        lambda candidate: None,
    )
    card = build_candidate_readonly_card(
        {
            "title": "Test Show",
            "year": 2020,
            "type": "Scripted",
        }
    )

    assert card["object_type"] == "unknown"


def test_candidate_filters_view_empty_pool_summary(monkeypatch, qapp) -> None:
    from desktop.candidates.filters_view import CandidateFiltersView
    from desktop.candidates.session import CandidateSearchSession

    monkeypatch.setattr(
        "desktop.candidates.filters_view.candidate_service.get_search_overview_view",
        lambda: {"is_empty": True, "summary": "", "candidates": []},
    )
    monkeypatch.setattr(
        "desktop.candidates.filters_view.candidate_service.get_search_filter_chip_options_view",
        lambda: {"genres": [], "countries": [], "dataset_total": 0, "is_empty": True, "source": "fallback"},
    )
    session = CandidateSearchSession()
    view = CandidateFiltersView(session)
    assert "пуст" in view._intro_lead.text().lower()
    assert view._apply_button.isEnabled() is False


def test_format_pool_stats_user_uses_plain_language() -> None:
    from desktop.candidates.filters_intro import format_pool_stats_user

    text = format_pool_stats_user(
        {"unique_total": 305, "ready_total": 204, "incomplete_total": 101},
    )
    assert "305 сериалов" in text
    assert "204 с полной TMDb metadata" in text
    assert "101 требуют metadata диагностики" in text
    assert "ready" not in text
    assert "pool" not in text.lower()


def test_candidate_filters_view_country_all_and_year_slider_defaults(monkeypatch, qapp) -> None:
    from config import constant
    from desktop.candidates.filters_view import CANDIDATE_YEAR_MIN, CandidateFiltersView
    from desktop.candidates.session import CandidateSearchSession

    monkeypatch.setattr(
        "desktop.candidates.filters_view.candidate_service.get_search_overview_view",
        lambda: {
            "is_empty": False,
            "summary": "в pool: 1 | ready: 1 | incomplete: 0",
            "candidates": [],
        },
    )
    monkeypatch.setattr(
        "desktop.candidates.filters_view.candidate_service.get_search_filter_defaults_view",
        lambda: {"defaults": {}},
    )
    monkeypatch.setattr(
        "desktop.candidates.filters_view.candidate_service.get_search_filter_chip_options_view",
        lambda: {"genres": [], "countries": [], "dataset_total": 0, "is_empty": True, "source": "fallback"},
    )

    view = CandidateFiltersView(CandidateSearchSession())
    filters = view._collect_filters()

    assert filters["country"] == []
    assert filters["year_min"] is None
    assert filters["year_max"] is None
    assert view._country_selector.is_all_selected() is True
    assert view._year_slider.values() == (CANDIDATE_YEAR_MIN, constant.NOW_YEAR)
    assert filters["min_tmdb_score"] is None
    assert filters["min_tmdb_votes"] is None
    assert view._only_complete_check.isChecked() is False


def test_country_chip_selector_clear_means_all_countries(qapp) -> None:
    from desktop.shared.widgets.country_chip_selector import CountryChipSelector

    selector = CountryChipSelector([{"code": "RU", "label": "Россия"}, {"code": "US", "label": "США"}])
    selector.set_selected_codes(["RU", "US"])

    assert selector.is_all_selected() is False
    assert selector.selected_country_codes() == ["RU", "US"]

    selector.clear_selection()

    assert selector.is_all_selected() is True
    assert selector.selected_country_codes() == []


def test_country_chip_selector_toggle_country_updates_selection(qapp) -> None:
    from desktop.shared.widgets.country_chip_selector import CountryChipSelector

    selector = CountryChipSelector([{"code": "RU", "label": "Россия"}, {"code": "US", "label": "США"}])
    selector._chips["RU"].setChecked(True)

    assert selector.selected_country_codes() == ["RU"]
    assert selector.is_all_selected() is False


def test_chip_expand_control_shows_five_chips_when_collapsed(qapp) -> None:
    from desktop.shared.widgets.collapsible_chip_helpers import COLLAPSED_VISIBLE_CHIP_COUNT
    from desktop.shared.widgets.genre_chip_selector import GenreChipSelector

    genres = [f"Жанр {index}" for index in range(8)]
    selector = GenreChipSelector()
    selector.set_options(genres)
    selector.show()

    visible = [chip.isVisible() for chip in selector._ordered_chips()]
    assert visible[:COLLAPSED_VISIBLE_CHIP_COUNT] == [True] * COLLAPSED_VISIBLE_CHIP_COUNT
    assert visible[COLLAPSED_VISIBLE_CHIP_COUNT:] == [False] * 3

    selector._toggle_expanded()
    assert all(chip.isVisible() for chip in selector._ordered_chips())


def test_genre_chip_selector_can_collapse_with_selected_chip_outside_top_five(qapp) -> None:
    from desktop.shared.widgets.collapsible_chip_helpers import COLLAPSED_VISIBLE_CHIP_COUNT
    from desktop.shared.widgets.genre_chip_selector import GenreChipSelector

    genres = [f"Жанр {index}" for index in range(8)]
    selector = GenreChipSelector()
    selector.set_options(genres)
    selector.show()

    selector._toggle_expanded()
    selector._chips["Жанр 7"].setChecked(True)
    selector._toggle_expanded()

    ordered_texts = [chip.text() for chip in selector._ordered_chips()]
    visible_texts = [chip.text() for chip in selector._ordered_chips() if chip.isVisible()]
    assert selector._expand.expanded is False
    assert ordered_texts[:COLLAPSED_VISIBLE_CHIP_COUNT] == [
        "Жанр 7",
        "Жанр 0",
        "Жанр 1",
        "Жанр 2",
        "Жанр 3",
    ]
    assert visible_texts == ordered_texts[:COLLAPSED_VISIBLE_CHIP_COUNT]
    assert selector._expand._button.text() == "Показать ещё (3) ▼"


def test_country_chip_selector_can_collapse_with_selected_chip_outside_top_five(qapp) -> None:
    from desktop.shared.widgets.collapsible_chip_helpers import COLLAPSED_VISIBLE_CHIP_COUNT
    from desktop.shared.widgets.country_chip_selector import CountryChipSelector

    options = [
        {"code": f"C{index}", "label": f"Страна {index}"}
        for index in range(8)
    ]
    selector = CountryChipSelector(options)
    selector.show()

    selector._toggle_expanded()
    selector._chips["C7"].setChecked(True)
    selector._toggle_expanded()

    ordered_texts = [chip.text() for chip in selector._ordered_chips()]
    visible_texts = [chip.text() for chip in selector._ordered_chips() if chip.isVisible()]
    assert selector._expand.expanded is False
    assert ordered_texts[:COLLAPSED_VISIBLE_CHIP_COUNT] == [
        "Страна 7",
        "Страна 0",
        "Страна 1",
        "Страна 2",
        "Страна 3",
    ]
    assert visible_texts == ordered_texts[:COLLAPSED_VISIBLE_CHIP_COUNT]
    assert selector._expand._button.text() == "Показать ещё (3) ▼"


def test_chip_selectors_sort_selected_items_by_popularity_not_click_order(qapp) -> None:
    from desktop.shared.widgets.country_chip_selector import CountryChipSelector
    from desktop.shared.widgets.genre_chip_selector import GenreChipSelector

    genres = [f"Жанр {index}" for index in range(8)]
    genre_selector = GenreChipSelector()
    genre_selector.set_options(genres)
    genre_selector.show()
    genre_selector._chips["Жанр 7"].setChecked(True)
    genre_selector._chips["Жанр 5"].setChecked(True)

    country_selector = CountryChipSelector(
        [{"code": f"C{index}", "label": f"Страна {index}"} for index in range(8)]
    )
    country_selector.show()
    country_selector._chips["C7"].setChecked(True)
    country_selector._chips["C5"].setChecked(True)

    assert genre_selector.selected_genres() == ["Жанр 5", "Жанр 7"]
    assert [chip.text() for chip in genre_selector._ordered_chips()[:4]] == [
        "Жанр 5",
        "Жанр 7",
        "Жанр 0",
        "Жанр 1",
    ]
    assert country_selector.selected_country_codes() == ["C5", "C7"]
    assert [chip.text() for chip in country_selector._ordered_chips()[:4]] == [
        "Страна 5",
        "Страна 7",
        "Страна 0",
        "Страна 1",
    ]


def test_chip_selector_collapsed_mode_never_shows_more_than_five_even_when_many_selected(qapp) -> None:
    from desktop.shared.widgets.collapsible_chip_helpers import COLLAPSED_VISIBLE_CHIP_COUNT
    from desktop.shared.widgets.genre_chip_selector import GenreChipSelector

    genres = [f"Жанр {index}" for index in range(8)]
    selector = GenreChipSelector()
    selector.set_options(genres)
    selector.show()

    selector._toggle_expanded()
    for index in range(6):
        selector._chips[f"Жанр {index}"].setChecked(True)
    selector._toggle_expanded()

    visible_texts = [chip.text() for chip in selector._ordered_chips() if chip.isVisible()]
    assert len(visible_texts) == COLLAPSED_VISIBLE_CHIP_COUNT
    assert visible_texts == ["Жанр 0", "Жанр 1", "Жанр 2", "Жанр 3", "Жанр 4"]
    assert selector._chips["Жанр 5"].isChecked() is True
    assert selector._chips["Жанр 5"].isVisible() is False


def test_chip_selectors_handle_empty_options(qapp) -> None:
    from desktop.shared.widgets.country_chip_selector import CountryChipSelector
    from desktop.shared.widgets.genre_chip_selector import GenreChipSelector

    genre_selector = GenreChipSelector()
    genre_selector.set_options([])
    country_selector = CountryChipSelector([])

    assert genre_selector.selected_genres() == []
    assert country_selector.selected_country_codes() == []
    assert genre_selector._expand._button.isVisible() is False
    assert country_selector._expand._button.isVisible() is False


def test_candidate_filters_view_numeric_threshold_sliders_collect_values(monkeypatch, qapp) -> None:
    from desktop.candidates.filters_view import (
        SCORE_SLIDER_MAX,
        VOTES_SLIDER_MAX_INDEX,
        CandidateFiltersView,
    )
    from desktop.candidates.session import CandidateSearchSession

    monkeypatch.setattr(
        "desktop.candidates.filters_view.candidate_service.get_search_overview_view",
        lambda: {"is_empty": False, "summary": "ok", "candidates": []},
    )
    monkeypatch.setattr(
        "desktop.candidates.filters_view.candidate_service.get_search_filter_defaults_view",
        lambda: {"defaults": {}},
    )
    monkeypatch.setattr(
        "desktop.candidates.filters_view.candidate_service.get_search_filter_chip_options_view",
        lambda: {"genres": [], "countries": [], "dataset_total": 0, "is_empty": True, "source": "fallback"},
    )

    view = CandidateFiltersView(CandidateSearchSession())
    view._tmdb_score_slider.setValues(75, SCORE_SLIDER_MAX)
    view._tmdb_votes_slider.setValues(4, VOTES_SLIDER_MAX_INDEX)

    filters = view._collect_filters()

    assert filters["min_tmdb_score"] == 7.5
    assert filters["min_tmdb_votes"] == 10_000


def test_candidate_filters_view_uses_threshold_sliders_not_spinboxes() -> None:
    import inspect

    import desktop.candidates.filters_form as form_module
    import desktop.candidates.filters_view as module

    init_source = inspect.getsource(module.CandidateFiltersView.__init__)
    form_source = inspect.getsource(form_module.build_filters_form)
    source = init_source + form_source
    assert "build_filters_form" in init_source
    assert "tmdb_score_slider" in source
    assert "tmdb_votes_slider" in source
    assert "_make_score_spin" not in source
    assert "_make_votes_spin" not in source
    assert "QDoubleSpinBox" not in source
    assert "QSpinBox" not in source


def test_candidate_filters_view_places_apply_button_in_top_bar() -> None:
    import inspect

    import desktop.candidates.filters_view as module

    source = inspect.getsource(module.CandidateFiltersView.__init__)
    assert "top_bar" in source
    assert "_update_apply_button_width" in source
    assert "form.addWidget(self._apply_button)" not in source


def test_watched_window_includes_candidate_tabs() -> None:
    import inspect

    import desktop.shell.main_window as app_module
    import desktop.shell.tabs as tabs_module

    init_source = inspect.getsource(app_module.WatchedMoviesWindow.__init__)
    factory_source = inspect.getsource(tabs_module.build_main_tabs)
    assert "build_main_tabs" in init_source
    assert "WatchedTabView" in factory_source
    assert "CandidateFiltersView" in factory_source
    assert "CandidateListView" in factory_source
    assert "AnalyticsView" in factory_source
    assert '"Фильтры"' in factory_source
    assert '"Кандидаты"' in factory_source
    assert '"Моё"' in factory_source
    assert '"Информация"' in factory_source
    assert '"Watched"' not in factory_source
    assert '"Analytics"' not in factory_source
    assert '"Search"' not in factory_source
    assert "MainTabRegistry" in factory_source
    assert "ShellTabSpec" in factory_source
    assert "_tab_registry.register" not in init_source
    assert "registry.register" in factory_source
    assert "registry.focus" in factory_source
    assert "on_watched_entries_changed" in factory_source


def test_analytics_view_hides_removed_imdb_sections() -> None:
    import inspect

    import desktop.analytics.constants as constants_module
    import desktop.analytics.view as analytics_view_module

    source = inspect.getsource(analytics_view_module.AnalyticsView.__init__)
    update_source = inspect.getsource(analytics_view_module.AnalyticsView.update_entries)
    icons = constants_module.SECTION_ICONS

    assert "Отличие моих оценок от IMDb" not in source
    assert "Я сильно выше IMDb" not in source
    assert "Подозрительные оценки" not in source
    assert "_fill_imdb_delta" not in update_source
    assert "_fill_rating_higher" not in update_source
    assert "_fill_suspicious" not in update_source
    assert "Отличие моих оценок от IMDb" not in icons
    assert "Я сильно выше IMDb" not in icons
    assert "Подозрительные оценки" not in icons
    assert "Я сильно ниже IMDb" not in source
    assert "Я сильно ниже IMDb" not in icons
    assert "Конструктор графика" in source


def test_genre_chip_selector_tracks_selection(qapp) -> None:
    from desktop.shared.widgets.genre_chip_selector import GenreChipSelector

    selector = GenreChipSelector()
    selector.set_options(["Драма", "Комедия", "Детектив"], ["Драма"])

    assert selector.selected_genres() == ["Драма"]

    selector._chips["Комедия"].setChecked(True)
    assert selector.selected_genres() == ["Драма", "Комедия"]

    selector.clear_selection()
    assert selector.selected_genres() == []


def test_candidate_filters_view_uses_genre_chip_selectors() -> None:
    import inspect

    import desktop.candidates.filters_form as form_module
    import desktop.candidates.filters_view as module

    init_source = inspect.getsource(module.CandidateFiltersView.__init__)
    form_source = inspect.getsource(form_module.build_filters_form)
    assert "build_filters_form" in init_source
    assert "GenreChipSelector" in form_source
    assert "include_genre_selector" in form_source
    assert "exclude_genre_selector" in form_source
    assert "_form" in init_source
    assert "_make_genre_list" not in init_source + form_source


def test_build_candidate_readonly_detail_entry_maps_fields() -> None:
    from desktop.candidates.presenters import build_candidate_readonly_detail_entry

    candidate = {
        "pool_entry_key": "show|2018",
        "title": "Pool Show",
        "year": 2018,
        "country": "Россия",
        "tmdb_score": 7.8,
        "tmdb_votes": 1200,
        "final_score": 0.74,
        "imdb_id": "tt123",
        "overview": "Test overview",
        "genres_display": ["Драма", "Комедия"],
        "number_of_seasons": 1,
        "number_of_episodes": 8,
        "episode_run_time": [45],
        "watch_providers": ["Kinopoisk"],
        "status": "Ended",
        "in_production": False,
        "poster_url": "https://example.com/poster.jpg",
    }

    entry_key, movie, card = build_candidate_readonly_detail_entry(candidate)

    assert entry_key == "__candidate__show|2018"
    assert movie["main_info"]["title"] == "Pool Show"
    assert card["title"] == "Pool Show"
    assert card["year"] == 2018
    assert card["country"] == "Россия"
    assert card["tmdb_score"] == 7.8
    assert card["tmdb_votes"] == 1200
    assert card["final_score"] == 0.74
    assert card["imdb_id"] == "tt123"
    assert card["number_of_seasons"] == 1
    assert card["number_of_episodes"] == 8
    assert card["episode_run_time"] == [45]
    assert card["watch_providers"] == ["Kinopoisk"]
    assert card["status"] == "Ended"
    assert card["in_production"] is False
    assert "kp_score" not in card
    assert "imdb_score" not in card
    assert card["overview"] == "Test overview"
    assert card["genres"] == ["Драма", "Комедия"]
    assert "poster_path" not in card
    assert "poster_src" not in card


def test_build_candidate_readonly_detail_entry_splits_legacy_combined_genres() -> None:
    from desktop.candidates.presenters import build_candidate_readonly_detail_entry

    _, _, card = build_candidate_readonly_detail_entry(
        {
            "title": "Pool Show",
            "genres_display": ["Боевик/приключения", "Фантастика/фэнтези"],
        }
    )

    assert card["genres"] == ["Боевик", "Приключения", "Фантастика", "Фэнтези"]


def test_build_candidate_readonly_detail_entry_does_not_download_poster(monkeypatch) -> None:
    from desktop.candidates.presenters import build_candidate_readonly_detail_entry

    def fail_download(_url: str):
        raise AssertionError("download_poster_url_for_preview must not run on read-only selection")

    monkeypatch.setattr(
        "posters.download_images.download_poster_url_for_preview",
        fail_download,
    )

    _, _, card = build_candidate_readonly_detail_entry(
        {
            "title": "Remote Poster",
            "poster_url": "https://example.com/poster.jpg",
        }
    )
    assert card["title"] == "Remote Poster"
    assert "poster_path" not in card


def test_candidate_search_session_sorts_once_and_returns_all(monkeypatch) -> None:
    from desktop.candidates.session import CandidateSearchSession

    calls = {"count": 0}
    candidates = [
        {"title": "A", "final_score": 9.0},
        {"title": "B", "final_score": 8.0},
        {"title": "C", "final_score": 7.0},
    ]

    def fake_sort(items, sort_mode):
        calls["count"] += 1
        return {
            "candidates": list(items),
            "sort_mode": sort_mode,
            "before_dedupe_count": len(items),
            "hidden_duplicates": 0,
        }

    monkeypatch.setattr(
        "desktop.candidates.session.candidate_service.sort_search_candidates",
        fake_sort,
    )
    monkeypatch.setattr(
        "desktop.candidates.session.candidate_service.get_search_overview_view",
        lambda: {"is_empty": False, "candidates": candidates},
    )
    monkeypatch.setattr(
        "desktop.candidates.session.candidate_service.search_candidate_pool",
        lambda _items, _filters: {"candidates": candidates, "filtered_count": len(candidates)},
    )

    session = CandidateSearchSession()
    session.apply_filters({})
    assert calls["count"] == 1
    assert [item["title"] for item in session.sorted_candidates()] == ["A", "B", "C"]
    assert session.sorted_total_count() == 3

    session.set_sort_mode("tmdb_score")
    assert calls["count"] == 2
    assert len(session.sorted_candidates()) == 3


def test_filter_candidates_by_title_matches_alternative_title() -> None:
    from desktop.candidates.presenters import filter_candidates_by_title

    candidates = [
        {"title": "Alpha", "year": 2020},
        {"title": "Beta", "alternative_title": "Gamma", "year": 2021},
    ]
    assert len(filter_candidates_by_title(candidates, "gamma")) == 1
    assert filter_candidates_by_title(candidates, "gamma")[0]["title"] == "Beta"


def test_list_search_index_filters_with_precomputed_haystack() -> None:
    from desktop.shared.widgets.list_search import SearchIndex, SearchIndexItem, normalize_search_query, resolve_selection_row

    index = SearchIndex([
        SearchIndexItem(item={"title": "Alpha"}, haystack="alpha show", selection_key="a"),
        SearchIndexItem(item={"title": "Beta"}, haystack="beta series", selection_key="b"),
    ])
    assert len(index.filter_by_query("show")) == 1
    assert index.filter_by_query("show")[0]["title"] == "Alpha"
    assert len(index.filter_by_query("")) == 2
    assert normalize_search_query("  AbC ") == "abc"

    filtered = index.filter_by_query("beta")
    assert resolve_selection_row("missing", filtered, key_getter=lambda item: item["title"]) == 0
    assert resolve_selection_row("Beta", filtered, key_getter=lambda item: item["title"]) == 0


def test_build_watched_search_index_matches_title() -> None:
    from desktop.watched import build_watched_search_index

    entries = [
        ("Alpha", {}, {"title": "Alpha Show"}),
        ("Beta", {}, {"title": "Beta"}),
    ]
    index = build_watched_search_index(entries)
    assert len(index.filter_by_query("show")) == 1
    assert index.filter_by_query("show")[0][0] == "Alpha"


def test_candidate_list_view_uses_list_search_module() -> None:
    import inspect

    import desktop.candidates.list_view as module

    source = inspect.getsource(module.CandidateListView)
    assert "DebouncedLineEditSearch" in source
    assert "build_candidate_search_index" in source
    assert "get_pool_stats_view" not in source.split("_update_counter_label")[1].split("def ")[0]


def test_candidate_list_view_uses_readonly_detail_builder() -> None:
    import inspect

    import desktop.candidates.list_view as module
    from desktop.shared.detail import CANDIDATE_DETAIL_CARD_PROFILE, DETAIL_CARD_LAYOUT_PROFILE

    source = inspect.getsource(module.CandidateListView)
    assert "build_candidate_readonly_detail_entry" in source
    assert "candidateListSearch" in source
    assert "build_candidate_search_index" in source
    assert "build_candidate_detail_entry" not in source
    assert "CANDIDATE_DETAIL_CARD_PROFILE" in source
    assert "detail_profiles.CANDIDATE_DETAIL_CARD_PROFILE" in source
    assert CANDIDATE_DETAIL_CARD_PROFILE.detail_poster_width == DETAIL_CARD_LAYOUT_PROFILE.detail_poster_width
    assert CANDIDATE_DETAIL_CARD_PROFILE.detail_poster_height == DETAIL_CARD_LAYOUT_PROFILE.detail_poster_height
    assert CANDIDATE_DETAIL_CARD_PROFILE.show_user_score is False
    assert CANDIDATE_DETAIL_CARD_PROFILE.show_mark_watched_button is True
    assert CANDIDATE_DETAIL_CARD_PROFILE.include_bottom_stretch is False


def test_candidate_list_view_wires_mark_watched_transfer() -> None:
    import inspect

    import desktop.candidates.list_view as module

    source = inspect.getsource(module.CandidateListView)
    assert "run_candidate_transfer_flow" in source
    assert "set_mark_watched_handler" in source
    assert "on_watched_added" in source


def test_candidate_list_view_starts_async_poster_download() -> None:
    import inspect

    import desktop.candidates.list_view as module

    source = inspect.getsource(module.CandidateListView)
    assert "CandidatePosterDownloadWorker" in source
    assert "candidate_poster_url_for_download" in source
    assert "apply_local_poster_path" in source


def test_candidate_session_reload_from_pool_reapplies_filters() -> None:
    import inspect

    import desktop.candidates.session as session_module

    source = inspect.getsource(session_module.CandidateSearchSession.reload_from_pool)
    assert "apply_filters" in source
    assert "_notify_listeners" in source

import copy
import inspect

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
    from desktop.watched_view import prepare_card_for_display

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


def test_start_app_entrypoint_is_guarded() -> None:
    import start_app as start_app_module

    assert start_app_module.__name__ != "__main__"
    assert callable(start_app_module.main)


def test_score_edit_dialog_is_custom_dark_dialog() -> None:
    import desktop.app as app_module

    source = inspect.getsource(app_module)

    assert "class ScoreEditDialog(QDialog)" in source
    assert "QInputDialog" not in source
    assert "setFixedWidth(390)" in source
    assert "scoreEditCard" in source
    assert "scoreEditSaveButton" in source


def test_add_title_button_is_ui_stub_only() -> None:
    import desktop.app as app_module

    source = inspect.getsource(app_module.WatchedMoviesWindow)
    handler_source = inspect.getsource(app_module.WatchedMoviesWindow._show_add_title_stub)

    assert "watchedAddTitle" in source
    assert "+ Добавить тайтл" in source
    assert "Добавление тайтла будет добавлено позже." in handler_source
    assert "План: поиск по названию" in handler_source
    assert "QMessageBox.information" in handler_source
    assert "save_" not in handler_source
    assert "update_dataset_record" not in handler_source
    assert "load_watched_entries" not in handler_source


def test_prepare_card_for_display_does_not_mutate_movie() -> None:
    from desktop.watched_view import prepare_card_for_display

    movie = _make_movie("Mutation Check", 8.5, 2019)
    original = copy.deepcopy(movie)

    card = prepare_card_for_display(movie)

    assert movie == original
    assert card["title"] == "Mutation Check"


def test_filter_by_title() -> None:
    from desktop.watched_view import filter_by_title

    entries = _make_entries()

    filtered = filter_by_title(entries, "brav")

    assert [entry[0] for entry in filtered] == ["Bravo"]


def test_filter_entries_by_user_score_empty() -> None:
    from desktop.watched_view import filter_entries_by_user_score

    assert filter_entries_by_user_score([], 7.0, 10.0) == []


def test_filter_entries_by_user_score_range() -> None:
    from desktop.watched_view import filter_entries_by_user_score

    entries = _make_entries()

    filtered = filter_entries_by_user_score(entries, 7.0, 10.0)

    assert [entry[0] for entry in filtered] == ["Alpha", "Bravo", "Charlie"]


def test_filter_entries_by_user_score_narrow_range() -> None:
    from desktop.watched_view import filter_entries_by_user_score

    entries = _make_entries()

    filtered = filter_entries_by_user_score(entries, 8.0, 8.9)

    assert [entry[0] for entry in filtered] == ["Charlie"]


def test_filter_entries_by_user_score_string_and_invalid_scores() -> None:
    from desktop.watched_view import filter_entries_by_user_score

    entries = [
        ("String Score", {}, {"title": "String Score", "user_score": "7.5"}),
        ("Missing Score", {}, {"title": "Missing Score"}),
        ("Invalid Score", {}, {"title": "Invalid Score", "user_score": "bad"}),
    ]

    filtered = filter_entries_by_user_score(entries, 7.0, 8.0)

    assert [entry[0] for entry in filtered] == ["String Score"]


def test_filter_entries_by_user_score_swaps_invalid_range() -> None:
    from desktop.watched_view import filter_entries_by_user_score

    entries = _make_entries()

    filtered = filter_entries_by_user_score(entries, 9.0, 8.0)

    assert [entry[0] for entry in filtered] == ["Alpha", "Charlie"]


def test_filter_entries_by_year_empty() -> None:
    from desktop.watched_view import filter_entries_by_year

    assert filter_entries_by_year([], 2015, 2026) == []


def test_filter_entries_by_year_range() -> None:
    from desktop.watched_view import filter_entries_by_year

    entries = _make_entries()

    filtered = filter_entries_by_year(entries, 2015, 2026)

    assert [entry[0] for entry in filtered] == ["Alpha", "Bravo", "Charlie"]


def test_filter_entries_by_year_exact_year() -> None:
    from desktop.watched_view import filter_entries_by_year

    entries = [
        ("Old", _make_movie("Old", 7.0, 2022), {"title": "Old", "user_score": 7.0, "year": 2022}),
        ("Exact", _make_movie("Exact", 8.0, 2023), {"title": "Exact", "user_score": 8.0, "year": 2023}),
    ]

    filtered = filter_entries_by_year(entries, 2023, 2023)

    assert [entry[0] for entry in filtered] == ["Exact"]


def test_filter_entries_by_year_string_and_invalid_years() -> None:
    from desktop.watched_view import filter_entries_by_year

    entries = [
        ("String Year", {"main_info": {"year": "2020"}}, {"title": "String Year", "user_score": 7.5}),
        ("Missing Year", {"main_info": {}}, {"title": "Missing Year", "user_score": 8.0}),
        ("Invalid Year", {"main_info": {"year": "abc"}}, {"title": "Invalid Year", "user_score": 8.0}),
    ]

    filtered = filter_entries_by_year(entries, 2019, 2021)

    assert [entry[0] for entry in filtered] == ["String Year"]


def test_filter_entries_by_year_swaps_invalid_range() -> None:
    from desktop.watched_view import filter_entries_by_year

    entries = _make_entries()

    filtered = filter_entries_by_year(entries, 2022, 2020)

    assert [entry[0] for entry in filtered] == ["Alpha", "Charlie"]


def test_get_available_genres_empty() -> None:
    from desktop.watched_view import get_available_genres

    assert get_available_genres([]) == []


def test_get_available_genres_sorts_and_hides_empty_duplicates() -> None:
    from desktop.watched_view import get_available_genres

    entries = [
        ("Alpha", {}, {"title": "Alpha", "genres": ["Драма", "Криминал", "Драма"]}),
        ("Bravo", {}, {"title": "Bravo", "genres": ["Комедия", "", "  "]}),
        ("Charlie", {}, {"title": "Charlie"}),
    ]

    assert get_available_genres(entries) == ["Драма", "Комедия", "Криминал"]


def test_filter_entries_by_genre_no_filter_returns_all() -> None:
    from desktop.watched_view import GENRE_FILTER_ALL, filter_entries_by_genre

    entries = [
        ("Alpha", {}, {"title": "Alpha", "genres": ["Драма"]}),
        ("Bravo", {}, {"title": "Bravo", "genres": ["Комедия"]}),
    ]

    assert filter_entries_by_genre(entries, None) == entries
    assert filter_entries_by_genre(entries, GENRE_FILTER_ALL) == entries


def test_filter_entries_by_genre_matches_selected_genre() -> None:
    from desktop.watched_view import filter_entries_by_genre

    entries = [
        ("Alpha", {}, {"title": "Alpha", "genres": ["Драма", "Криминал"]}),
        ("Bravo", {}, {"title": "Bravo", "genres": ["Комедия"]}),
        ("Charlie", {}, {"title": "Charlie"}),
    ]

    filtered = filter_entries_by_genre(entries, "Драма")

    assert [entry[0] for entry in filtered] == ["Alpha"]


def test_filter_entries_by_genre_missing_genre_returns_empty() -> None:
    from desktop.watched_view import filter_entries_by_genre

    entries = [
        ("Alpha", {}, {"title": "Alpha", "genres": ["Драма"]}),
        ("No Genre", {}, {"title": "No Genre"}),
    ]

    assert filter_entries_by_genre(entries, "Фантастика") == []


def test_apply_view_combines_title_score_year_genre_filter_and_sort() -> None:
    from desktop.watched_view import apply_view

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
    from desktop.watched_view import apply_view

    filtered = apply_view(_make_entries(), "", "user_score", 0.0, 10.0, 1990, 1995)

    assert filtered == []


def test_apply_view_sorts_after_year_filter() -> None:
    from desktop.watched_view import apply_view

    filtered = apply_view(_make_entries(), "", "year", 0.0, 10.0, 2019, 2022)

    assert [entry[0] for entry in filtered] == ["Charlie", "Alpha"]


def test_apply_view_sorts_after_genre_filter() -> None:
    from desktop.watched_view import apply_view

    entries = [
        ("Older", {}, {"title": "Older", "user_score": 7.0, "year": 2018, "genres": ["Драма"]}),
        ("Newer", {}, {"title": "Newer", "user_score": 9.0, "year": 2022, "genres": ["Драма"]}),
        ("Other", {}, {"title": "Other", "user_score": 10.0, "year": 2023, "genres": ["Комедия"]}),
    ]

    filtered = apply_view(entries, "", "user_score", 0.0, 10.0, 2000, 2026, "Драма")

    assert [entry[0] for entry in filtered] == ["Newer", "Older"]


def test_sort_by_user_score() -> None:
    from desktop.watched_view import sort_entries

    entries = _make_entries()
    sorted_entries = sort_entries(entries, "user_score")

    assert [entry[0] for entry in sorted_entries] == ["Alpha", "Charlie", "Bravo"]


def test_sort_by_year() -> None:
    from desktop.watched_view import sort_entries

    entries = _make_entries()
    sorted_entries = sort_entries(entries, "year")

    assert [entry[0] for entry in sorted_entries] == ["Charlie", "Alpha", "Bravo"]


def test_format_user_score_display() -> None:
    from desktop.watched_view import format_user_score_display

    assert format_user_score_display(8.25) == "8.3"
    assert format_user_score_display(8) == "8.0"
    assert format_user_score_display(None) == "—"


def test_build_meta_pill_items() -> None:
    from desktop.watched_view import build_meta_pill_items

    items = build_meta_pill_items(
        {
            "year": 2025,
            "imdb_score": 7.34,
            "kp_score": 7.8,
        }
    )

    assert len(items) == 2
    assert items[0]["kind"] == "rating_indicator"
    assert items[0]["source"] == "imdb"
    assert items[0]["label"] == "IMDb"
    assert items[0]["score"] == "7.3"
    assert items[0]["accent"] == "#8b949e"
    assert items[1]["kind"] == "rating_indicator"
    assert items[1]["source"] == "kp"
    assert items[1]["label"] == "КП"
    assert items[1]["score"] == "7.8"
    assert items[1]["accent"] == "#87978f"


def test_build_meta_pill_labels() -> None:
    from desktop.watched_view import build_meta_pill_labels

    pills = build_meta_pill_labels(
        {
            "year": 2025,
            "imdb_score": 7.34,
            "kp_score": 7.8,
        }
    )

    assert pills == ["2025", "IMDb 7.3", "КП 7.8"]


def test_build_genre_pill_labels_hides_empty() -> None:
    from desktop.watched_view import build_genre_pill_labels

    assert build_genre_pill_labels({"genres": []}) == []
    assert build_genre_pill_labels({"genres": ["Драма", "Криминал"]}) == [
        "Драма",
        "Криминал",
    ]


def test_build_detail_info_pill_labels_moves_year_to_genres() -> None:
    from desktop.watched_view import build_detail_info_pill_labels

    assert build_detail_info_pill_labels({"year": 2025, "genres": ["Драма"]}) == [
        "2025",
        "Драма",
    ]
    assert build_detail_info_pill_labels({"genres": ["Драма"]}) == ["Драма"]
    assert build_detail_info_pill_labels({"year": 2025, "genres": ["Драма"], "country": "Россия"}) == [
        "2025",
        "Драма",
        "Россия",
    ]


def test_format_genre_pill_label_unknown_genre() -> None:
    from desktop.watched_view import format_genre_pill_label

    assert format_genre_pill_label("Документальный") == "Документальный"


def test_build_user_score_update_payload() -> None:
    from desktop.watched_view import build_user_score_update_payload

    assert build_user_score_update_payload(8.25) == {"main_info": {"user_score": 8.3}}


def test_format_save_user_score_status() -> None:
    from dataset.dataset_records import UpdateRecordResult
    from desktop.watched_view import format_save_user_score_status

    assert format_save_user_score_status(
        UpdateRecordResult(True, "Alpha", "Запись обновлена.", "updated", ["main_info.user_score"])
    ) == "Оценка сохранена"
    assert format_save_user_score_status(
        UpdateRecordResult(False, "Alpha", "Ошибка обновления!", "invalid_patch", [])
    ) == "Ошибка обновления!"


def test_save_watched_user_score_uses_update_pipeline(monkeypatch) -> None:
    from dataset.dataset_records import UpdateRecordResult
    from desktop.watched_view import save_watched_user_score

    calls = []

    def fake_update(title, patch, source_name=""):
        calls.append((title, patch, source_name))
        return UpdateRecordResult(True, title, "Запись обновлена.", "updated", ["main_info.user_score"])

    monkeypatch.setattr("dataset.dataset_records.update_dataset_record", fake_update)

    result = save_watched_user_score("Dataset Key", 8.5)

    assert result.ok is True
    assert calls == [("Dataset Key", {"main_info": {"user_score": 8.5}}, "desktop_gui")]


def test_save_watched_user_score_does_not_touch_model_artifacts(monkeypatch) -> None:
    from dataset.dataset_records import UpdateRecordResult
    from desktop.watched_view import save_watched_user_score

    def fail(_payload=None):
        raise AssertionError("desktop score save must not touch model artifacts")

    def fake_update(title, patch, source_name=""):
        return UpdateRecordResult(True, title, "Запись обновлена.", "updated", ["main_info.user_score"])

    monkeypatch.setattr("dataset.dataset_records.update_dataset_record", fake_update)
    monkeypatch.setattr("storage.data.save_weights", fail)
    monkeypatch.setattr("storage.data.save_model_metrics", fail)
    monkeypatch.setattr("candidates.candidate_pool.save_candidate_pool", fail)
    monkeypatch.setattr("model.model.save_weights_if_loo_improved", fail)
    monkeypatch.setattr("model.linear_regression_train.train_ridge_for_benchmark", fail)

    result = save_watched_user_score("Dataset Key", 8.5)

    assert result.ok is True


def test_get_user_score_spin_value() -> None:
    from desktop.watched_view import get_user_score_spin_value

    assert get_user_score_spin_value({"user_score": 8.25}) == 8.3
    assert get_user_score_spin_value({"user_score": None}) == 0.0


def test_validate_score_edit_entry() -> None:
    from desktop.watched_view import validate_score_edit_entry

    assert validate_score_edit_entry(None) == (False, "Запись не выбрана")
    assert validate_score_edit_entry(("  ", {}, {})) == (False, "Запись не выбрана")
    assert validate_score_edit_entry(("Alpha", {}, {})) == (True, "")


def test_get_country_display() -> None:
    from desktop.watched_view import get_country_display

    assert get_country_display({"country": "Россия"}) == "Россия"
    assert get_country_display({"country": ""}) is None
    assert get_country_display({}) is None


def test_has_overview_text() -> None:
    from desktop.watched_view import get_overview_display, has_overview_text

    assert has_overview_text({"overview": "Короткое описание."}) is True
    assert get_overview_display({"overview": "  Текст  "}) == "Текст"
    assert has_overview_text({"overview": ""}) is False
    assert has_overview_text({"overview": "   "}) is False
    assert has_overview_text({}) is False


def test_format_watched_list_status() -> None:
    from desktop.watched_view import format_watched_list_status

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
    from desktop.watched_view import format_watched_list_counter

    assert format_watched_list_counter(12, 12, "") == "Всего 12"
    assert format_watched_list_counter(3, 12, "alpha") == "3 из 12"
    assert format_watched_list_counter(3, 12, "", True) == "3 из 12"
    assert format_watched_list_counter(0, 12, "missing") == "Ничего не найдено"
    assert format_watched_list_counter(0, 0, "") == "Список пуст"


def test_count_active_filters() -> None:
    from desktop.watched_view import count_active_filters

    assert count_active_filters() == 0
    assert count_active_filters(True, False, False) == 1
    assert count_active_filters(True, True, True) == 3


def test_score_filter_is_active() -> None:
    from desktop.watched_view import USER_SCORE_MAX, USER_SCORE_MIN, score_filter_is_active

    assert score_filter_is_active(USER_SCORE_MIN, USER_SCORE_MAX) is False
    assert score_filter_is_active(8.0, USER_SCORE_MAX) is True
    assert score_filter_is_active(USER_SCORE_MIN, 7.5) is True


def test_year_filter_is_active() -> None:
    from datetime import date

    from desktop.watched_view import (
        YEAR_FILTER_DEFAULT_FROM,
        YEAR_FILTER_DEFAULT_TO,
        year_filter_is_active,
    )

    current_year = date.today().year
    assert year_filter_is_active(YEAR_FILTER_DEFAULT_FROM, YEAR_FILTER_DEFAULT_TO) is False
    assert year_filter_is_active(2015, current_year) is True
    assert year_filter_is_active(YEAR_FILTER_DEFAULT_FROM, current_year - 1) is True


def test_genre_filter_is_active() -> None:
    from desktop.watched_view import GENRE_FILTER_ALL, genre_filter_is_active

    assert genre_filter_is_active(None) is False
    assert genre_filter_is_active(GENRE_FILTER_ALL) is False
    assert genre_filter_is_active("Триллер") is True


def test_watched_filters_are_active_from_ranges() -> None:
    from datetime import date

    from desktop.watched_view import (
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
    from desktop.watched_view import format_watched_filters_label

    assert format_watched_filters_label() == "▸ Фильтры"
    assert format_watched_filters_label(is_expanded=True) == "▾ Фильтры"
    assert format_watched_filters_label(has_score_filter=True) == "▸ Фильтры активны"
    assert format_watched_filters_label(has_year_filter=True, is_expanded=True) == "▾ Фильтры активны"
    assert format_watched_filters_label(has_genre_filter=True) == "▸ Фильтры активны"
    assert " (" not in format_watched_filters_label(has_score_filter=True)


def test_apply_view_after_default_filter_reset_respects_search() -> None:
    from desktop.watched_view import (
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

    import desktop.app as app_module

    source = inspect.getsource(app_module.WatchedMoviesWindow)

    assert "_build_filters_panel" in source
    assert "watchedFiltersPanel" in source
    assert "format_watched_filters_label" in source
    assert "watchedFilterResetAll" in source
    assert "WatchedListItemDelegate" in source
    assert "watchedListCounter" in source
    assert "watchedSortRow" in source
    assert "watchedSortLabel" in source
    assert "Сортировка" in source
    assert "_reset_all_filters" in source
    assert "watchedScoreReset" not in source
    assert "watchedYearReset" not in source
    assert "Удалить запись" in source
    assert "_delete_watched_entry" in source
    assert "execute_watched_delete" in source


def test_is_delete_confirmation_valid() -> None:
    from desktop.watched_delete import is_delete_confirmation_valid

    assert is_delete_confirmation_valid("DELETE") is True
    assert is_delete_confirmation_valid(" DELETE ") is True
    assert is_delete_confirmation_valid("delete") is False
    assert is_delete_confirmation_valid("") is False
    assert is_delete_confirmation_valid("REMOVE") is False


def test_format_delete_preview_lines() -> None:
    from desktop.watched_delete import format_delete_preview_lines

    lines = format_delete_preview_lines(
        {
            "title": "Alpha",
            "year": 2020,
            "user_score": 8.0,
            "kp_score": 7.5,
            "imdb_score": 8.1,
            "has_meta": True,
            "has_poster_cache": False,
        }
    )
    assert "Название: Alpha" in lines
    assert "Год: 2020" in lines
    assert "Моя оценка: 8.0" in lines
    assert "КП: 7.5" in lines
    assert "IMDb: 8.1" in lines
    assert "Meta: есть" in lines
    assert "Poster-cache: нет" in lines


def test_format_delete_preview_lines_handles_missing_fields() -> None:
    from desktop.watched_delete import format_delete_preview_lines

    lines = format_delete_preview_lines({"title": "No Meta"})
    joined = "\n".join(lines)
    assert "Название: No Meta" in joined
    assert "Meta: нет" in joined
    assert "Poster-cache: нет" in joined
    assert "КП:" not in joined
    assert "IMDb:" not in joined


def test_watched_delete_entry_uses_service_helper() -> None:
    import inspect

    import desktop.app as app_module

    source = inspect.getsource(app_module.WatchedMoviesWindow._delete_watched_entry)
    assert "load_delete_preview" in source
    assert "WatchedDeleteDialog" in source
    assert "execute_watched_delete" in source
    assert "storage_data.save_dataset" not in source


def test_watched_detail_card_layout_contract() -> None:
    import inspect

    import desktop.watched_view as watched_view_module

    source = inspect.getsource(watched_view_module.WatchedDetailCard)
    init_source = source.split("def _info_column_content_width", 1)[0]

    assert "info_column.addStretch" not in init_source
    assert "root.addStretch(1)" in init_source
    assert "QSizePolicy.Policy.Minimum" in init_source
    assert "setWordWrap(True)" in init_source
    assert "maximumHeight" not in init_source


def test_watched_detail_card_hides_overview_without_text() -> None:
    import inspect

    import desktop.watched_view as watched_view_module

    source = inspect.getsource(watched_view_module.WatchedDetailCard.show_entry)
    init_source = inspect.getsource(watched_view_module.WatchedDetailCard.__init__)
    assert "has_overview_text(card)" in source
    assert "_overview_frame.setVisible(False)" in source
    assert "overviewDivider" in init_source
    assert "OVERVIEW_SECTION_TOP_SPACING" in init_source


def test_build_score_count_html_smoke() -> None:
    from desktop.plotly_charts import build_score_count_html

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
    from desktop.plotly_charts import build_score_distribution_html

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


def test_analytics_distribution_uses_score_count_points() -> None:
    import inspect

    import desktop.analytics_view as analytics_view_module

    source = inspect.getsource(analytics_view_module.AnalyticsView.update_entries)
    assert 'analytics["score_count_points"]' in source
    fill_distribution_source = inspect.getsource(analytics_view_module.AnalyticsView._fill_distribution)
    assert "build_score_count_html" in fill_distribution_source
    assert "SCORE_CHART_HEIGHT" in fill_distribution_source


def test_score_count_chart_height_matches_plotly_constant() -> None:
    from desktop.plotly_charts import SCORE_CHART_HEIGHT, build_score_count_figure

    figure = build_score_count_figure([{"score": 8.5, "count": 2, "example_titles": ["A"], "extra_count": 0}])
    assert figure.layout.height == SCORE_CHART_HEIGHT

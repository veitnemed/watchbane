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


def test_apply_view_combines_title_score_filter_and_sort() -> None:
    from desktop.watched_view import apply_view

    entries = [
        *_make_entries(),
        ("Bravo Low", _make_movie("Bravo Low", 6.0, 2017, 7.0), {"title": "Bravo Low", "user_score": 6.0, "year": 2017}),
    ]

    filtered = apply_view(entries, "bravo", "user_score", 7.0, 10.0)

    assert [entry[0] for entry in filtered] == ["Bravo"]


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
    assert format_watched_list_status(0, 12, "missing") == "Ничего не найдено"
    assert format_watched_list_status(0, 12, "", True) == "Ничего не найдено"
    assert format_watched_list_status(0, 0, "") == "Список пуст"


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
    assert "has_overview_text(card)" in source
    assert "_overview_frame.setVisible(False)" in source


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

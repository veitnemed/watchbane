import copy
import ast
import inspect
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

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


def _flush_qt_deferred_deletes(qapp) -> None:
    from PyQt6.QtCore import QCoreApplication, QEvent

    qapp.processEvents()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    qapp.processEvents()


@pytest.fixture(autouse=True)
def _isolate_desktop_settings(monkeypatch, tmp_path):
    monkeypatch.setattr(constant, "APP_DATA_DIR", str(tmp_path / "data"))


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


def test_i18n_catalogs_have_same_keys() -> None:
    from desktop.i18n import SUPPORTED_LANGUAGES, TRANSLATIONS

    key_sets = {language: set(TRANSLATIONS[language]) for language in SUPPORTED_LANGUAGES}
    assert key_sets["ru"] == key_sets["en"]


def test_i18n_translator_defaults_and_fallbacks(monkeypatch) -> None:
    from desktop.settings.app_settings import AppSettings
    import desktop.i18n.translator as translator_module

    monkeypatch.setattr(
        translator_module,
        "load_app_settings",
        lambda: AppSettings(interface_language="ru", data_language="en"),
    )

    assert translator_module.tr("tabs.watched") == "Моё"

    monkeypatch.setattr(
        translator_module,
        "load_app_settings",
        lambda: AppSettings(interface_language="en", data_language="ru"),
    )
    monkeypatch.delitem(translator_module.TRANSLATIONS["en"], "tabs.watched")

    assert translator_module.tr("tabs.watched") == "Моё"
    assert translator_module.tr("missing.translation.key") == "missing.translation.key"


def test_i18n_translator_respects_interface_language_env(monkeypatch) -> None:
    import desktop.i18n.translator as translator_module

    monkeypatch.setenv("WATCHBANE_INTERFACE_LANGUAGE", "en")

    assert translator_module.get_interface_language() == "en"
    assert translator_module.tr("tabs.watched") == "My library"


def test_desktop_language_context_keeps_interface_and_data_independent(monkeypatch) -> None:
    from desktop.language_context import load_desktop_language_context

    monkeypatch.setenv("WATCHBANE_INTERFACE_LANGUAGE", "en")
    monkeypatch.setenv("WATCHBANE_DATA_LANGUAGE", "ru")

    context = load_desktop_language_context()

    assert context.interface_language == "en"
    assert context.data_language == "ru"
    assert context.tmdb_locale == "ru-RU"
    assert context.tr("tabs.settings") == "Settings"


def test_english_ui_labels_cover_sort_and_chip_controls(qapp) -> None:
    from desktop.settings.app_settings import AppSettings, save_app_settings

    save_app_settings(AppSettings(interface_language="en", data_language="en"))

    from desktop.candidates.presenters import candidate_sort_mode_label, format_candidate_metric_value
    from desktop.shared.widgets.country_chip_selector import CountryChipSelector
    from desktop.shared.widgets.genre_chip_selector import GenreChipSelector
    from desktop.watched.sidebar import _watched_sort_label

    assert _watched_sort_label("user_score", "fallback") == "My rating"
    assert candidate_sort_mode_label("final_score") == "Final"
    assert format_candidate_metric_value({"final_score": 9.2}, "final_score") == "Final 9.2"

    country_selector = CountryChipSelector([{"code": "US", "label": "United States"}])
    genre_selector = GenreChipSelector()
    genre_selector.set_options(["Drama"])

    assert country_selector._count_label.text() == "All countries"
    assert genre_selector._count_label.text() == "Selected: 0"


def test_english_data_language_formats_detail_values() -> None:
    from desktop.settings.app_settings import AppSettings, save_app_settings
    from desktop.shared.detail.additional_info import format_episode_runtime, format_seasons_episodes
    from desktop.shared.detail.main_info import (
        build_main_info_items,
        build_title_meta_text,
        format_air_date_display,
        format_votes_display,
        normalize_object_type,
    )

    save_app_settings(AppSettings(interface_language="en", data_language="en"))

    assert normalize_object_type("series", data_language="en") == "Series"
    assert format_air_date_display("2022-03-16", data_language="en") == "16 Mar 2022"
    assert format_seasons_episodes(6, 63, data_language="en") == "6 seasons / 63 episodes"
    assert format_episode_runtime([46], data_language="en") == "46 min"
    assert format_votes_display(3456, data_language="en") == "3.5k"
    assert build_title_meta_text(
        {"year": 2015, "number_of_seasons": 6, "number_of_episodes": 63},
        data_language="en",
    ) == "2015 • 6 seasons / 63 episodes"

    items = build_main_info_items(
        {
            "country": "US",
            "object_type": "series",
            "first_air_date": "2015-02-08",
            "last_air_date": "2022-08-15",
            "status": "Ended",
        },
        data_language="en",
    )

    assert {"label": "Type", "value": "Series"} in items
    assert {"label": "Country", "value": "United States"} in items
    assert {"label": "Premiere", "value": "8 Feb 2015"} in items
    assert {"label": "Last episode", "value": "15 Aug 2022"} in items
    assert {"label": "Status", "value": "Ended"} in items


def test_interface_and_data_language_are_independent() -> None:
    from desktop.candidates.presenters import build_candidate_readonly_card
    from desktop.i18n import tr
    from desktop.settings.app_settings import AppSettings, save_app_settings

    candidate = {
        "title": "Лучше звоните Солу",
        "description": "Русское описание",
        "localized": {
            "ru": {"title": "Лучше звоните Солу", "overview": "Русское описание"},
            "en": {"title": "Better Call Saul", "overview": "English overview"},
        },
    }

    save_app_settings(AppSettings(interface_language="en", data_language="ru"))
    assert tr("tabs.watched") == "My library"
    assert build_candidate_readonly_card(candidate, data_language="ru")["title"] == "Лучше звоните Солу"

    save_app_settings(AppSettings(interface_language="ru", data_language="en"))
    assert tr("tabs.watched") == "Моё"
    assert build_candidate_readonly_card(candidate, data_language="en")["title"] == "Better Call Saul"


def test_english_country_display_and_add_title_country_combo(qapp) -> None:
    from candidates.models.country_schema import candidate_country_for_display
    from desktop.settings.app_settings import AppSettings, save_app_settings
    from desktop.watched.add_title.search_dialog import AddTitleSearchDialog

    save_app_settings(AppSettings(interface_language="en", data_language="en"))

    assert candidate_country_for_display({"country": "US"}, language="en") == "United States"

    dialog = AddTitleSearchDialog(initial_country="US")

    assert dialog._country_combo.itemText(0) == "Any country"
    assert dialog._country_combo.currentText() == "United States"


def test_add_title_resolve_uses_data_language_for_tmdb_locale() -> None:
    from dataset.resolve import service as resolve_service

    calls = {"search_language": None, "details_language": None}

    def fake_search(title, *, language=None):
        calls["search_language"] = language
        return [{"id": 101, "name": title}]

    def fake_details(tmdb_id, *, language=None, **kwargs):
        calls["details_language"] = language
        assert kwargs["append_to_response"] == resolve_service.api_tmdb.DEFAULT_TV_DETAIL_APPENDS
        return {
            "id": tmdb_id,
            "name": "Better Call Saul",
            "original_name": "Better Call Saul",
            "first_air_date": "2015-02-08",
            "origin_country": ["US"],
            "production_countries": [{"iso_3166_1": "US", "name": "United States"}],
            "genres": [{"id": 18, "name": "Drama"}],
            "vote_average": 8.7,
            "vote_count": 6000,
            "popularity": 40.0,
            "overview": "English overview",
            "external_ids": {"imdb_id": "tt3032476"},
        }

    result = resolve_service.resolve_title_data_for_add(
        "Better Call Saul",
        "US",
        data_language="en",
        tmdb_search_func=fake_search,
        tmdb_choose_func=lambda results, **_kwargs: results[0],
        tmdb_details_func=fake_details,
    )

    assert calls == {"search_language": "en-US", "details_language": "en-US"}
    assert result["tmdb_language"] == "en-US"
    assert result["data_language"] == "en"
    assert result["defaults"]["localized"]["en"]["title"] == "Better Call Saul"
    assert result["defaults"]["localized"]["en"]["overview"] == "English overview"


def test_add_title_resolve_fallback_search_keeps_english_naruto_title() -> None:
    from dataset.resolve import service as resolve_service

    search_calls = []
    details_calls = []

    def fake_search(title, *, language=None):
        search_calls.append((title, language))
        if title == "Naruto" and language == "en-US":
            return [{"id": 46260, "name": "Naruto"}]
        return []

    def fake_details(tmdb_id, *, language=None, **kwargs):
        details_calls.append((tmdb_id, language))
        assert kwargs["append_to_response"] == resolve_service.api_tmdb.DEFAULT_TV_DETAIL_APPENDS
        return {
            "id": tmdb_id,
            "name": "Naruto",
            "original_name": "ナルト",
            "first_air_date": "2002-10-03",
            "origin_country": ["JP"],
            "production_countries": [{"iso_3166_1": "JP", "name": "Japan"}],
            "original_language": "ja",
            "genres": [{"id": 10759, "name": "Action & Adventure"}],
            "vote_average": 8.4,
            "vote_count": 5600,
            "popularity": 60.0,
            "overview": "Naruto Uzumaki wants to become the strongest ninja in his village.",
            "external_ids": {"imdb_id": "tt0409591"},
        }

    result = resolve_service.resolve_title_data_for_add(
        "Наруто",
        "JP",
        data_language="en",
        tmdb_search_func=fake_search,
        tmdb_choose_func=lambda results, **_kwargs: results[0] if results else None,
        tmdb_details_func=fake_details,
    )

    assert search_calls == [("Наруто", "en-US"), ("Наруто", "ru-RU"), ("Naruto", "en-US")]
    assert details_calls == [(46260, "en-US")]
    assert result["found"] is True
    assert result["defaults"]["main_info"]["title"] == "Naruto"
    assert result["defaults"]["localized"]["en"]["title"] == "Naruto"
    assert result["defaults"]["localized"]["en"]["title"] != "ナルト"
    assert result["defaults"]["localized"]["en"]["overview"].startswith("Naruto Uzumaki")


def test_add_title_resolve_builds_ru_and_en_localized_blocks_from_tmdb_details() -> None:
    from dataset.resolve import service as resolve_service

    def fake_search(title, *, language=None):
        assert language == "en-US"
        return [{"id": 46260, "name": "Naruto"}]

    def fake_details(tmdb_id, *, language=None, **kwargs):
        assert tmdb_id == 46260
        assert language == "en-US"
        assert kwargs["append_to_response"] == resolve_service.api_tmdb.DEFAULT_TV_DETAIL_APPENDS
        return {
            "id": 46260,
            "name": "Naruto",
            "original_name": "\u30ca\u30eb\u30c8",
            "first_air_date": "2002-10-03",
            "origin_country": ["JP"],
            "production_countries": [{"iso_3166_1": "JP", "name": "Japan"}],
            "original_language": "ja",
            "genres": [{"id": 10759, "name": "Action & Adventure"}],
            "vote_average": 8.4,
            "vote_count": 5600,
            "overview": "English Naruto overview.",
            "poster_path": "/naruto_en_top.jpg",
            "translations": {
                "translations": [
                    {
                        "iso_639_1": "ru",
                        "iso_3166_1": "RU",
                        "data": {
                            "name": "\u041d\u0430\u0440\u0443\u0442\u043e",
                            "overview": "\u0420\u0443\u0441\u0441\u043a\u043e\u0435 \u043e\u043f\u0438\u0441\u0430\u043d\u0438\u0435 \u041d\u0430\u0440\u0443\u0442\u043e.",
                        },
                    },
                    {
                        "iso_639_1": "en",
                        "iso_3166_1": "US",
                        "data": {
                            "name": "Naruto",
                            "overview": "English Naruto overview.",
                        },
                    },
                ],
            },
            "images": {
                "posters": [
                    {"file_path": "/naruto_ru.jpg", "iso_639_1": "ru", "vote_average": 8.0, "vote_count": 10},
                    {"file_path": "/naruto_en.jpg", "iso_639_1": "en", "vote_average": 7.5, "vote_count": 8},
                ],
            },
        }

    result = resolve_service.resolve_title_data_for_add(
        "\u041d\u0430\u0440\u0443\u0442\u043e",
        "JP",
        data_language="en",
        tmdb_search_func=fake_search,
        tmdb_choose_func=lambda results, **_kwargs: results[0],
        tmdb_details_func=fake_details,
    )

    localized = result["defaults"]["localized"]
    assert result["defaults"]["main_info"]["title"] == "Naruto"
    assert localized["en"]["title"] == "Naruto"
    assert localized["en"]["overview"] == "English Naruto overview."
    assert localized["en"]["poster_path"] == "/naruto_en.jpg"
    assert localized["ru"]["title"] == "\u041d\u0430\u0440\u0443\u0442\u043e"
    assert localized["ru"]["overview"].startswith("\u0420\u0443\u0441\u0441\u043a\u043e\u0435")
    assert localized["ru"]["poster_path"] == "/naruto_ru.jpg"


def test_add_dataset_record_preserves_localized_payload(monkeypatch) -> None:
    from dataset.records import add as add_module

    raw_scores = {
        "kp_score": 8.0,
        "kp_votes": 1000,
        "imdb_score": 8.1,
        "imdb_votes": 1000,
    }
    payload = {
        "main_info": {
            "title": "Naruto",
            "user_score": 8.5,
            "year": 2002,
            "country": "JP",
        },
        "raw_scores": raw_scores,
        constant.TAGS_VIBE_SECTION: {feature: 0 for feature in constant.TAGS_VIBE},
        constant.GENRE_SECTION: {feature: 0 for feature in constant.GENRE},
        "localized": {
            "ru": {
                "title": "\u041d\u0430\u0440\u0443\u0442\u043e",
                "overview": "\u0420\u0443\u0441\u0441\u043a\u043e\u0435 \u043e\u043f\u0438\u0441\u0430\u043d\u0438\u0435.",
            },
            "en": {
                "title": "Naruto",
                "overview": "English overview.",
            },
        },
    }
    saved = {}

    monkeypatch.setattr(add_module, "load_dataset", lambda: {})
    monkeypatch.setattr(add_module, "load_meta", lambda: {"Naruto": {"raw_scores": raw_scores}})
    monkeypatch.setattr(add_module, "save_dataset_and_meta", lambda data, _meta: saved.update(data))
    monkeypatch.setattr(add_module, "run_after_add_side_effects", lambda **_kwargs: [])

    result = add_module.add_dataset_record(payload)

    assert result.ok is True
    assert saved["Naruto"]["localized"]["ru"]["title"] == "\u041d\u0430\u0440\u0443\u0442\u043e"
    assert saved["Naruto"]["localized"]["en"]["overview"] == "English overview."


def test_tmdb_result_choice_matches_cyrillic_naruto_to_english_name() -> None:
    from dataset.resolve.sources import choose_best_tmdb_result

    selected = choose_best_tmdb_result(
        [
            {
                "id": 46260,
                "name": "Naruto",
                "original_name": "ナルト",
                "origin_country": ["JP"],
                "vote_count": 100,
                "popularity": 20.0,
            },
            {
                "id": 31910,
                "name": "Naruto Shippūden",
                "original_name": "ナルト 疾風伝",
                "origin_country": ["JP"],
                "vote_count": 10000,
                "popularity": 90.0,
            },
        ],
        title="Наруто",
        country="JP",
    )

    assert selected is not None
    assert selected["id"] == 46260
    assert selected["original_name"] == "ナルト"


def test_live_tmdb_naruto_english_locale_uses_display_name_not_original_japanese() -> None:
    if os.environ.get("WATCHBANE_RUN_TMDB_API_TESTS") != "1":
        pytest.skip("Set WATCHBANE_RUN_TMDB_API_TESTS=1 to run live TMDb API smoke.")

    from dataset.resolve import service as resolve_service

    result = resolve_service.resolve_title_data_for_add("Наруто", "JP", data_language="en")

    assert result["found"] is True
    assert result["tmdb_language"] == "en-US"
    assert result["defaults"]["main_info"]["title"] == "Naruto"
    assert result["defaults"]["localized"]["en"]["title"] == "Naruto"
    assert result["tmdb_data"]["original_title"] == "ナルト"


def test_tmdb_localized_backfill_uses_locale_name_not_original_japanese() -> None:
    from dataset.migrations.tmdb_localized import backfill_mapping_from_tmdb

    calls = []

    def fake_details(tmdb_id, *, language=None, **_kwargs):
        calls.append((tmdb_id, language))
        return {
            "id": tmdb_id,
            "name": "Naruto",
            "original_name": "ナルト",
            "overview": "Naruto Uzumaki wants to become the strongest ninja in his village.",
        }

    updated, report = backfill_mapping_from_tmdb(
        {
            "naruto": {
                "tmdb_id": 46260,
                "main_info": {"title": "Наруто", "year": 2002},
            }
        },
        data_language="en",
        details_func=fake_details,
    )

    assert calls == [(46260, "en-US")]
    assert report["changed_records"] == 1
    assert updated["naruto"]["localized"]["en"]["title"] == "Naruto"
    assert updated["naruto"]["localized"]["en"]["title"] != "ナルト"
    assert updated["naruto"]["localized"]["en"]["overview"].startswith("Naruto Uzumaki")


def test_tmdb_localized_backfill_uses_translation_block_when_top_level_empty() -> None:
    from dataset.migrations.tmdb_localized import localized_block_from_tmdb_details

    block = localized_block_from_tmdb_details(
        {
            "name": "Fallback Name",
            "overview": "",
            "translations": {
                "translations": [
                    {
                        "iso_3166_1": "US",
                        "iso_639_1": "en",
                        "data": {
                            "name": "Translated Name",
                            "overview": "Translated overview.",
                        },
                    }
                ]
            },
        },
        "en",
    )

    assert block == {
        "title": "Translated Name",
        "overview": "Translated overview.",
    }


def test_add_title_worker_passes_data_language(monkeypatch, qapp) -> None:
    from types import SimpleNamespace

    from desktop.watched.add_title.worker import AddTitleResolveWorker

    captured = {}

    def fake_resolve_title_for_add(title, country, *, on_progress=None, data_language="ru"):
        captured["title"] = title
        captured["country"] = country
        captured["data_language"] = data_language
        if on_progress is not None:
            on_progress(1, 1, "done")
        return SimpleNamespace(found=True)

    monkeypatch.setattr(
        "desktop.watched.add_title.worker.service.resolve_title_for_add",
        fake_resolve_title_for_add,
    )

    results = []
    worker = AddTitleResolveWorker("Trigger", "US", data_language="en")
    worker.finished_with_result.connect(results.append)
    worker.run()

    assert captured == {"title": "Trigger", "country": "US", "data_language": "en"}
    assert results[0].found is True


def test_add_title_worker_does_not_mask_service_type_error(monkeypatch, qapp) -> None:
    from desktop.watched.add_title.worker import AddTitleResolveWorker

    def broken_resolve_title_for_add(title, country, *, on_progress=None, data_language="ru", media_type="tv"):
        raise TypeError("internal service bug")

    monkeypatch.setattr(
        "desktop.watched.add_title.worker.service.resolve_title_for_add",
        broken_resolve_title_for_add,
    )

    errors = []
    worker = AddTitleResolveWorker("Trigger", "US", data_language="en", media_type="movie")
    worker.failed.connect(errors.append)
    worker.run()

    assert errors == ["internal service bug"]


def test_tmdb_builder_uses_passed_data_language_locale(monkeypatch) -> None:
    from candidates.sources.tmdb import builder
    from desktop.settings.app_settings import language_to_tmdb_locale

    discover_languages = []
    detail_languages = []

    monkeypatch.setattr(builder.api_tmdb, "load_tmdb_token", lambda: "token")
    monkeypatch.setattr(builder, "load_candidate_pool", lambda: {})
    monkeypatch.setattr(builder, "remove_watched_discover", lambda items: (list(items), 0))
    monkeypatch.setattr(
        builder,
        "build_discovery_slices",
        lambda *args, **kwargs: [
            {
                "slice_name": "test",
                "query": {"sort_by": "vote_count.desc", "with_origin_country": "US"},
                "pages_per_slice": 1,
            }
        ],
    )

    def fake_tmdb_get(_path, params=None, token=None):
        discover_languages.append((params or {}).get("language"))
        return {
            "page": 1,
            "total_pages": 1,
            "results": [
                {
                    "id": 3032476,
                    "name": "Better Call Saul",
                    "original_name": "Better Call Saul",
                    "first_air_date": "2015-02-08",
                    "vote_average": 8.7,
                    "vote_count": 6000,
                    "popularity": 40.0,
                }
            ],
        }

    def fake_details(tmdb_id, *, language=None, **_kwargs):
        detail_languages.append(language)
        return {
            "id": tmdb_id,
            "name": "Better Call Saul",
            "original_name": "Better Call Saul",
            "first_air_date": "2015-02-08",
            "origin_country": ["US"],
            "production_countries": [{"iso_3166_1": "US", "name": "United States"}],
            "original_language": "en",
            "genres": [{"id": 18, "name": "Drama"}],
            "vote_average": 8.7,
            "vote_count": 6000,
            "popularity": 40.0,
            "overview": "English overview",
            "external_ids": {"imdb_id": "tt3032476"},
            "aggregate_credits": {},
            "keywords": {"results": []},
        }

    monkeypatch.setattr(builder.api_tmdb, "tmdb_get", fake_tmdb_get)
    monkeypatch.setattr(builder.api_tmdb, "get_tv_details", fake_details)

    locale = language_to_tmdb_locale("en")
    result = builder.build_candidate_pool("US", pages=1, details_limit=1, language=locale)

    assert discover_languages == ["en-US"]
    assert detail_languages == ["en-US"]
    assert result["query"]["language"] == "en-US"
    assert result["settings"]["language"] == "en-US"
    assert result["candidates"][0]["source_query"]["language"] == "en-US"
    assert result["candidates"][0]["localized"]["en"]["title"] == "Better Call Saul"


def test_data_language_migration_adds_localized_without_renaming_keys(tmp_path) -> None:
    import json

    from dataset.migrations.data_language import migrate_data_language_files

    dataset_path = tmp_path / "watched" / "titles.json"
    meta_path = tmp_path / "watched" / "meta.json"
    pool_path = tmp_path / "candidates" / "pool.json"
    dataset_path.parent.mkdir(parents=True)
    pool_path.parent.mkdir(parents=True)

    original_dataset = {
        "Триггер": {
            "main_info": {"title": "Триггер", "year": 2020, "user_score": 8.0},
            "description": "Русское описание",
            "original_title": "Trigger",
        }
    }
    original_meta = {
        "Триггер": {
            "main_info": {"title": "Триггер"},
            "description": "Описание из meta",
        }
    }
    original_pool = {
        "better-call-saul-2015": {
            "title": "Лучше звоните Солу",
            "original_title": "Better Call Saul",
            "description": "Русское описание кандидата",
            "overview_en": "English candidate overview",
            "genre_keys": ["drama"],
        }
    }

    dataset_path.write_text(json.dumps(original_dataset, ensure_ascii=False), encoding="utf-8")
    meta_path.write_text(json.dumps(original_meta, ensure_ascii=False), encoding="utf-8")
    pool_path.write_text(json.dumps(original_pool, ensure_ascii=False), encoding="utf-8")

    report = migrate_data_language_files(
        dataset_path=dataset_path,
        meta_path=meta_path,
        pool_path=pool_path,
        timestamp="test",
    )

    migrated_dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    migrated_pool = json.loads(pool_path.read_text(encoding="utf-8"))

    assert list(migrated_dataset) == ["Триггер"]
    assert migrated_dataset["Триггер"]["main_info"]["title"] == "Триггер"
    assert migrated_dataset["Триггер"]["description"] == "Русское описание"
    assert migrated_dataset["Триггер"]["localized"]["ru"]["title"] == "Триггер"
    assert migrated_dataset["Триггер"]["localized"]["ru"]["overview"] == "Русское описание"
    assert migrated_dataset["Триггер"]["localized"]["en"]["title"] == "Trigger"
    assert "overview" not in migrated_dataset["Триггер"]["localized"]["en"]
    assert list(migrated_pool) == ["better-call-saul-2015"]
    assert migrated_pool["better-call-saul-2015"]["localized"]["en"]["title"] == "Better Call Saul"
    assert migrated_pool["better-call-saul-2015"]["localized"]["en"]["overview"] == "English candidate overview"
    assert Path(report["files"]["watched_dataset"]["backup_path"]).exists()
    assert json.loads(Path(report["files"]["watched_dataset"]["backup_path"]).read_text(encoding="utf-8")) == original_dataset


def test_candidate_migration_en_title_falls_back_to_title() -> None:
    from dataset.migrations.data_language import migrate_candidate_record

    migrated, changed = migrate_candidate_record({"title": "Только русский"})

    assert changed is True
    assert migrated["localized"]["ru"]["title"] == "Только русский"
    assert migrated["localized"]["en"]["title"] == "Только русский"


def test_data_language_helpers_choose_genre_labels() -> None:
    from dataset.language import choose_genre_labels

    assert choose_genre_labels(["has_drama"], "ru") == ["Драма"]
    assert choose_genre_labels(["has_drama"], "en") == ["Drama"]
    assert choose_genre_labels(["drama"], "en") == ["Drama"]
    assert choose_genre_labels(["has_action"], "en") == ["Action", "Adventure"]
    assert choose_genre_labels(["has_fantasy"], "en") == ["Sci-Fi", "Fantasy"]
    assert choose_genre_labels(["action_adventure"], "en") == ["Action", "Adventure"]


def test_candidate_filter_genre_labels_localize_to_data_language() -> None:
    from candidates.models.genre_schema import normalize_genre_filter_list
    from desktop.candidates.filters_view import _genre_labels_for_language

    labels = _genre_labels_for_language(
        ["Боевик/приключения", "Фантастика/фэнтези", "Драма"],
        "en",
    )

    assert labels == ["Action", "Adventure", "Sci-Fi", "Fantasy", "Drama"]
    assert normalize_genre_filter_list(labels) == ["action_adventure", "sci_fi_fantasy", "drama"]


def test_chip_expand_control_uses_interface_language(qapp) -> None:
    from PyQt6.QtWidgets import QPushButton

    from desktop.settings.app_settings import AppSettings, save_app_settings
    from desktop.shared.widgets.collapsible_chip_helpers import ChipExpandControl

    save_app_settings(AppSettings(interface_language="en", data_language="en"))

    control = ChipExpandControl(visible_count=1)
    button = control.create_button()
    chips = [QPushButton("A"), QPushButton("B"), QPushButton("C")]

    control.apply_visibility(chips)

    assert button.text() == "Show more (2) ▼"

    control.toggle()
    control.apply_visibility(chips)

    assert button.text() == "Collapse ▲"


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
    assert 'tr("watched.add_title.button")' in sidebar_source
    assert "run_add_title_flow" in handler_source
    assert "reload_entries" in handler_source
    assert "_show_add_title_stub" not in handler_source
    assert "class AddTitleSearchDialog" in search_source
    assert "class AddTitlePreviewDialog" in preview_source
    assert "run_add_title_flow" in handler_source
    assert 'tr("add_title.search_again")' in preview_source


def test_add_title_preview_dialog_uses_readonly_year_and_score_only_save() -> None:
    import desktop.watched.add_title.dialog as dialog_module

    source = inspect.getsource(dialog_module.AddTitlePreviewDialog)
    assert "_year_label" in source
    assert "QSpinBox" not in source
    assert "year=" not in source.replace("resolved_year", "")
    assert "save_add_title_record" in source
    assert "AddTitleCompactPreviewCard" in source
    assert "WatchedDetailCard" not in source


def _make_add_title_preview_bundle(*, extra_fields: bool = True):
    from dataset.add_flow.bundle import AddTitleResolveBundle

    card = {
        "title": "Наруто",
        "year": 2002,
        "object_type": "tv",
        "country": "Япония",
        "watch_providers": "Crunchyroll",
        "tmdb_score": 8.4,
        "tmdb_votes": 5600,
        "final_score": 0.72,
        "genres": ["Боевик", "Фантастика", "Приключения", "Аниме"],
        "overview": (
            "Мальчик-ниндзя мечтает стать сильнейшим в деревне и постепенно "
            "находит друзей, соперников и собственный путь."
        ),
    }
    if extra_fields:
        card.update({"status": "Ended", "episode_run_time": 24})

    return AddTitleResolveBundle(
        title="Наруто",
        country="",
        defaults={
            "main_info": {"title": "Наруто", "year": 2002, "country": "Япония"},
            "raw_scores": {},
            "genre": {},
        },
        meta_payload={},
        poster_hints={},
        preview_movie={"main_info": {"title": "Наруто", "year": 2002}},
        preview_card=card,
        found=True,
        statuses={"tmdb_api": "найдено"},
    )


def test_add_title_preview_dialog_uses_compact_preview_card(qapp) -> None:
    from PyQt6.QtWidgets import QWidget

    from desktop.watched.add_title.preview_dialog import AddTitlePreviewDialog

    dialog = AddTitlePreviewDialog(_make_add_title_preview_bundle())
    dialog.show()
    qapp.processEvents()

    compact_card = dialog.findChild(QWidget, "addTitleCompactPreviewCard")
    assert compact_card is not None
    assert hasattr(dialog, "_preview_card")
    assert hasattr(dialog, "_detail_card") is False
    assert dialog.findChild(QWidget, "addTitleCompactMainInfoSection") is None
    assert dialog.findChild(QWidget, "addTitleCompactOverviewSection") is None

    dialog.close()


def test_add_title_preview_status_uses_interface_language(qapp) -> None:
    from desktop.settings.app_settings import AppSettings, save_app_settings
    from desktop.watched.add_title.preview_dialog import AddTitlePreviewDialog

    save_app_settings(AppSettings(interface_language="en", data_language="en"))

    dialog = AddTitlePreviewDialog(_make_add_title_preview_bundle())
    dialog.show()
    qapp.processEvents()

    assert dialog._warning_label.text() == "TMDb API: found"

    dialog.close()


def test_add_title_preview_score_input_uses_english_locale(qapp) -> None:
    from desktop.settings.app_settings import AppSettings, save_app_settings
    from desktop.watched.add_title.preview_dialog import AddTitlePreviewDialog

    save_app_settings(AppSettings(interface_language="en", data_language="en"))

    dialog = AddTitlePreviewDialog(_make_add_title_preview_bundle())
    dialog.show()
    qapp.processEvents()

    assert dialog._score_input.text() == "0.0"

    dialog.close()


def test_candidate_transfer_preview_accepts_friends_1994_year(qapp) -> None:
    from PyQt6.QtWidgets import QPushButton

    from dataset.add_flow.transfer import build_candidate_transfer_bundle
    from desktop.watched.add_title.preview_dialog import AddTitlePreviewDialog

    bundle = build_candidate_transfer_bundle(
        {
            "title": "Friends",
            "year": 1994,
            "country_codes": ["US"],
            "tmdb_id": 1668,
            "tmdb_score": 8.4,
            "tmdb_votes": 8000,
            "tmdb_popularity": 80.0,
            "genre_keys": ["comedy"],
        },
        data_language="en",
    )

    dialog = AddTitlePreviewDialog(bundle, transfer_mode=True)
    dialog.show()
    qapp.processEvents()

    confirm_button = dialog.findChild(QPushButton, "addTitleConfirmButton")
    assert dialog._resolved_year(bundle) == 1994
    assert confirm_button is not None and confirm_button.isEnabled() is True

    dialog.close()


def test_add_title_compact_preview_renders_only_summary_content(qapp) -> None:
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QLabel, QWidget

    from desktop.watched.add_title.preview_dialog import AddTitlePreviewDialog

    dialog = AddTitlePreviewDialog(_make_add_title_preview_bundle(extra_fields=True))
    dialog.show()
    qapp.processEvents()
    card = dialog._preview_card

    assert card._poster_label.isVisible()
    assert card._title_label.text() == "Наруто"
    assert card._meta_label.text() == "2002"
    assert dialog.findChild(QWidget, "addTitleCompactMainInfoPanel") is None
    assert dialog.findChild(QLabel, "addTitleCompactOverviewText") is None
    assert len(dialog.findChildren(QLabel, "addTitleCompactGenrePill")) == 3
    assert card._title_label.alignment() & Qt.AlignmentFlag.AlignHCenter
    assert card._meta_label.alignment() & Qt.AlignmentFlag.AlignHCenter

    dialog.close()


def test_add_title_compact_preview_stays_short_for_dialog(qapp) -> None:
    from desktop.watched.add_title.preview_dialog import AddTitlePreviewDialog

    dialog = AddTitlePreviewDialog(_make_add_title_preview_bundle(extra_fields=True))
    dialog.show()
    qapp.processEvents()
    card = dialog._preview_card

    assert card.widget.height() <= card._poster_label.height() + 8

    dialog.close()


def test_add_title_compact_preview_dialog_centers_card_shell(qapp) -> None:
    from PyQt6.QtWidgets import QFrame

    from desktop.watched.add_title.preview_dialog import AddTitlePreviewDialog

    dialog = AddTitlePreviewDialog(_make_add_title_preview_bundle(extra_fields=True))
    dialog.show()
    qapp.processEvents()

    shell = dialog.findChild(QFrame, "addTitlePreviewCard")
    assert shell is not None
    dialog_center_x = dialog.rect().center().x()
    shell_center_x = shell.geometry().center().x()

    assert abs(shell_center_x - dialog_center_x) <= 2
    assert shell.width() < dialog.width() - 20

    dialog.close()


def test_add_title_search_progress_uses_interface_language(qapp) -> None:
    from desktop.settings.app_settings import AppSettings, save_app_settings
    from desktop.watched.add_title.search_dialog import AddTitleSearchDialog

    save_app_settings(AppSettings(interface_language="en", data_language="en"))

    dialog = AddTitleSearchDialog(initial_title="Naruto")
    dialog._active_request_id = 1
    dialog._set_search_active(True)
    dialog._on_progress(1, 1, 4, "TMDb Search: Поиск")

    assert dialog._status_label.text() == "TMDb Search: searching"

    dialog.close()


def test_add_title_search_dialog_enter_starts_search_without_default_cancel(qapp) -> None:
    from PyQt6.QtCore import Qt
    from PyQt6.QtTest import QTest
    from PyQt6.QtWidgets import QPushButton

    from desktop.watched.add_title.search_dialog import AddTitleSearchDialog

    dialog = AddTitleSearchDialog(initial_title="Триггер")
    calls = []
    dialog._start_search = lambda *, trigger="unknown": calls.append(trigger)

    assert hasattr(dialog, "_cancel_button") is False
    assert all(button.text() != "Отмена" for button in dialog.findChildren(QPushButton))

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


def test_build_watched_movie_card_respects_data_language() -> None:
    from common.cards import build_watched_movie_card

    movie = {
        "main_info": {"title": "Триггер", "year": 2020, "user_score": 8.0},
        "localized": {
            "ru": {"title": "Триггер", "overview": "Русское описание"},
            "en": {"title": "Trigger"},
        },
        "country_codes": ["RU"],
        "genre": {"has_drama": 1},
    }

    ru_card = build_watched_movie_card(movie, poster_cache={}, data_language="ru")
    en_card = build_watched_movie_card(movie, poster_cache={}, data_language="en")

    assert ru_card["title"] == "Триггер"
    assert ru_card["overview"] == "Русское описание"
    assert ru_card["country"] == "Россия"
    assert ru_card["genres"] == ["Драма"]
    assert en_card["title"] == "Trigger"
    assert en_card["overview"] == "Русское описание"
    assert en_card["country"] == "Russia"
    assert en_card["genres"] == ["Drama"]


def test_build_watched_movie_card_switches_added_title_localized_both_ways() -> None:
    from common.cards import build_watched_movie_card

    movie = {
        "main_info": {"title": "Naruto", "year": 2002, "user_score": 8.5},
        "localized": {
            "ru": {
                "title": "\u041d\u0430\u0440\u0443\u0442\u043e",
                "overview": "\u0420\u0443\u0441\u0441\u043a\u043e\u0435 \u043e\u043f\u0438\u0441\u0430\u043d\u0438\u0435 \u041d\u0430\u0440\u0443\u0442\u043e.",
            },
            "en": {
                "title": "Naruto",
                "overview": "English Naruto overview.",
            },
        },
        "country_codes": ["JP"],
        "genre_keys": ["action_adventure"],
    }

    ru_card = build_watched_movie_card(movie, poster_cache={}, data_language="ru")
    en_card = build_watched_movie_card(movie, poster_cache={}, data_language="en")

    assert ru_card["title"] == "\u041d\u0430\u0440\u0443\u0442\u043e"
    assert ru_card["overview"].startswith("\u0420\u0443\u0441\u0441\u043a\u043e\u0435")
    assert en_card["title"] == "Naruto"
    assert en_card["overview"] == "English Naruto overview."


def test_build_watched_movie_card_uses_localized_poster_for_data_language(tmp_path) -> None:
    from common.cards import build_watched_movie_card
    from posters.cache import poster_identity_key

    stale_local = tmp_path / "ru-poster.jpg"
    stale_local.write_bytes(b"poster")
    identity = poster_identity_key("Naruto", 2002)
    movie = {
        "main_info": {"title": "Naruto", "year": 2002, "user_score": 8.5},
        "poster_url": "https://image.tmdb.org/t/p/w342/naruto_ru.jpg",
        "localized": {
            "en": {
                "title": "Naruto",
                "poster_path": "/naruto_en.jpg",
                "poster_url": "https://image.tmdb.org/t/p/w342/naruto_en.jpg",
            }
        },
    }
    poster_cache = {
        identity: {
            "status": "found",
            "poster_url": "https://image.tmdb.org/t/p/w342/naruto_ru.jpg",
            "local_path": str(stale_local),
        }
    }

    card = build_watched_movie_card(movie, poster_cache=poster_cache, data_language="en")

    assert card["poster_url"] == "https://image.tmdb.org/t/p/w342/naruto_en.jpg"
    assert card["poster_src"] == "https://image.tmdb.org/t/p/w342/naruto_en.jpg"
    assert card["poster_src"] != str(stale_local)


def test_poster_cache_preserves_previous_local_path_until_language_download(monkeypatch, tmp_path) -> None:
    from posters import cache as poster_cache_module

    monkeypatch.setattr(poster_cache_module, "DEFAULT_POSTER_IMAGES_DIR", tmp_path)
    stale_local = tmp_path / "naruto-2002.jpg"
    stale_local.write_bytes(b"old")
    identity = poster_cache_module.poster_identity_key("Naruto", 2002)
    cache = {
        identity: {
            "title": "Naruto",
            "year": 2002,
            "status": "found",
            "poster_url": "https://image.tmdb.org/t/p/w342/naruto_ru.jpg",
            "local_path": str(stale_local),
        }
    }
    movie = {
        "main_info": {"title": "Naruto", "year": 2002},
        "localized": {
            "en": {
                "poster_path": "/naruto_en.jpg",
                "poster_url": "https://image.tmdb.org/t/p/w342/naruto_en.jpg",
            },
        },
    }

    entry = poster_cache_module.sync_poster_cache_from_meta_and_sources(
        "Naruto",
        2002,
        movie=movie,
        cache=cache,
        persist=False,
        data_language="en",
    )

    assert entry["poster_url"] == "https://image.tmdb.org/t/p/w342/naruto_en.jpg"
    assert entry["poster_path"] == "/naruto_en.jpg"
    assert entry["local_path"] == str(stale_local)
    assert stale_local.exists() is True


def test_watched_card_keeps_local_poster_fallback_after_language_cache_switch(tmp_path) -> None:
    from common.cards import build_watched_movie_card
    from posters.cache import poster_identity_key

    fallback_local = tmp_path / "naruto-2002.jpg"
    fallback_local.write_bytes(b"old")
    movie = {
        "main_info": {"title": "Naruto", "year": 2002, "user_score": 8.0},
        "localized": {
            "en": {
                "poster_path": "/naruto_en.jpg",
                "poster_url": "https://image.tmdb.org/t/p/w342/naruto_en.jpg",
            },
        },
    }
    poster_cache = {
        poster_identity_key("Naruto", 2002): {
            "title": "Naruto",
            "year": 2002,
            "status": "found",
            "poster_url": "https://image.tmdb.org/t/p/w342/naruto_en.jpg",
            "local_path": str(fallback_local),
        }
    }

    card = build_watched_movie_card(movie, poster_cache=poster_cache, data_language="en")

    assert card["poster_url"] == "https://image.tmdb.org/t/p/w342/naruto_en.jpg"
    assert card["poster_src"] == str(fallback_local)


def test_sync_poster_for_display_fetches_missing_language_poster_from_tmdb(monkeypatch, tmp_path) -> None:
    from dataset.read_models import watched as watched_read_model
    from posters import cache as poster_cache_module

    monkeypatch.setattr(poster_cache_module, "DEFAULT_POSTER_IMAGES_DIR", tmp_path)
    movie = {"main_info": {"title": "Naruto", "year": 2002, "user_score": 8.5}}
    meta_store = {
        "Naruto": {
            "tmdb_id": 46260,
            "poster_url": "https://image.tmdb.org/t/p/w342/naruto_ru.jpg",
        }
    }
    poster_cache = {
        poster_cache_module.poster_identity_key("Naruto", 2002): {
            "title": "Naruto",
            "year": 2002,
            "status": "found",
            "poster_url": "https://image.tmdb.org/t/p/w342/naruto_ru.jpg",
            "local_path": None,
        }
    }
    details_calls = []
    download_calls = []

    monkeypatch.setattr(watched_read_model.storage_data, "get_meta_obj", lambda _title: meta_store["Naruto"])
    monkeypatch.setattr(watched_read_model.storage_data, "load_meta", lambda: copy.deepcopy(meta_store))
    monkeypatch.setattr(watched_read_model.storage_data, "save_meta", lambda meta: meta_store.update(meta))
    monkeypatch.setattr(watched_read_model, "_get_poster_cache", lambda: poster_cache)
    monkeypatch.setattr(watched_read_model, "reload_poster_cache", lambda: poster_cache)
    monkeypatch.setattr(poster_cache_module, "load_poster_cache", lambda: poster_cache)
    monkeypatch.setattr(poster_cache_module, "save_poster_cache", lambda cache: poster_cache.update(cache))

    def fake_get_tv_details(tmdb_id, *, language=None, append_to_response=None, **_kwargs):
        details_calls.append((tmdb_id, language, append_to_response))
        return {
            "id": 46260,
            "name": "Naruto",
            "overview": "English Naruto overview.",
            "images": {
                "posters": [
                    {
                        "file_path": "/naruto_en.jpg",
                        "iso_639_1": "en",
                        "vote_average": 8.0,
                        "vote_count": 10,
                    }
                ],
            },
        }

    def fake_download(title, year, **kwargs):
        download_calls.append((title, year, kwargs))
        return {"ok": True, "reason": "downloaded", "local_path": str(tmp_path / "naruto.jpg")}

    monkeypatch.setattr("apis.tmdb_api.get_tv_details", fake_get_tv_details)
    monkeypatch.setattr("posters.download_images.download_poster_for_title", fake_download)

    result = watched_read_model.sync_poster_for_display(movie, data_language="en")

    assert result["meta_updated"] is True
    assert details_calls[0][0:2] == (46260, "en-US")
    assert meta_store["Naruto"]["localized"]["en"]["poster_path"] == "/naruto_en.jpg"
    assert result["entry"]["poster_url"] == "https://image.tmdb.org/t/p/original/naruto_en.jpg"
    assert download_calls == [("Naruto", 2002, {"force": True})]


def test_build_watched_movie_card_uses_localized_meta_fallback_for_english() -> None:
    from common.cards import build_watched_movie_card

    movie = {
        "main_info": {"title": "Наруто", "year": 2002, "user_score": 8.0},
        "raw_scores": {},
    }
    meta = {
        "localized": {
            "en": {
                "title": "Naruto",
                "overview": "Naruto Uzumaki wants to become the strongest ninja in his village.",
            }
        },
        "genre_keys": ["action_adventure", "sci_fi_fantasy"],
        "country_codes": ["JP"],
    }

    card = build_watched_movie_card(
        movie,
        poster_cache={},
        lookup_cache={"meta_by_title": {}, "pool_by_identity": {}},
        meta_obj=meta,
        data_language="en",
    )

    assert card["title"] == "Naruto"
    assert card["overview"].startswith("Naruto Uzumaki")
    assert card["genres"] == ["Action", "Adventure", "Sci-Fi", "Fantasy"]
    assert card["country"] == "Japan"


def test_prepare_card_for_display_accepts_data_language() -> None:
    from desktop.watched import prepare_card_for_display

    movie = _make_movie("Лучше звоните Солу", 9.0, 2015)
    movie["original_title"] = "Better Call Saul"

    card = prepare_card_for_display(movie, data_language="en")

    assert card["title"] == "Better Call Saul"


def test_watched_load_model_uses_dataset_read_facade_only() -> None:
    import inspect

    import desktop.watched.model.load as watched_load_module

    source = inspect.getsource(watched_load_module)
    assert "dataset.read_models.watched" in source
    assert "from storage" not in source
    assert "import storage" not in source
    assert "from web" not in source
    assert "import web" not in source


def test_watched_model_does_not_reexport_shared_detail_presenters() -> None:
    import desktop.watched.model as watched_model

    shared_detail_symbols = {
        "build_main_info_items",
        "build_meta_pill_items",
        "build_score_ring_item",
        "format_user_score_display",
        "normalize_final_score",
        "resolve_local_poster_path",
    }

    assert shared_detail_symbols.isdisjoint(watched_model.__all__)
    for symbol in shared_detail_symbols:
        assert hasattr(watched_model, symbol) is False


def test_desktop_storage_web_import_boundary_uses_documented_whitelist() -> None:
    # TODO: replace the remaining storage adapters with dataset/platform facades.
    documented_whitelist = {
        (
            "desktop/shell/bootstrap.py",
            "from storage.runtime import ensure_runtime_data_layout",
        ),
        (
            "desktop/shared/detail/posters.py",
            "from storage.files import open_file",
        ),
    }
    findings = set()

    for path in Path("desktop").rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        normalized_path = path.as_posix()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".", 1)[0] in {"storage", "web"}:
                        findings.add((normalized_path, f"import {alias.name}"))
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module.split(".", 1)[0] in {"storage", "web"}:
                    imported = ", ".join(alias.name for alias in node.names)
                    findings.add((normalized_path, f"from {module} import {imported}"))

    assert findings == documented_whitelist


def test_watched_read_facade_returns_desktop_entry_shape(monkeypatch) -> None:
    from dataset.read_models import watched as watched_read_model

    movie = _make_movie("Facade Shape", 7.7, 2021)
    poster_cache = {"Facade Shape": "poster.jpg"}
    lookup_cache = {"meta_by_title": {}, "pool_by_identity": {}}

    def fake_build_card(movie_obj, *, poster_cache=None, lookup_cache=None, data_language="ru"):
        assert movie_obj is movie
        assert poster_cache is poster_cache_value
        assert lookup_cache is lookup_cache_value
        assert data_language == "en"
        return {"title": movie_obj["main_info"]["title"], "year": 2021}

    poster_cache_value = poster_cache
    lookup_cache_value = lookup_cache
    monkeypatch.setattr(watched_read_model.storage_data, "load_dataset", lambda: {"Facade Shape": movie})
    monkeypatch.setattr(watched_read_model, "reload_poster_cache", lambda: poster_cache_value)
    monkeypatch.setattr(watched_read_model, "_get_lookup_cache", lambda: lookup_cache_value)
    monkeypatch.setattr(watched_read_model, "build_watched_movie_card", fake_build_card)

    entries = watched_read_model.load_watched_entries(data_language="en")

    assert entries == [("Facade Shape", movie, {"title": "Facade Shape", "year": 2021})]


def test_shared_poster_helper_has_no_web_export_dependency() -> None:
    import inspect

    import desktop.shared.detail.posters as posters_module

    source = inspect.getsource(posters_module)
    assert "web.export" not in source
    assert "build_watched_movie_card" not in source


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
    from desktop.shared.detail import profiles as detail_profiles
    from desktop.shared.detail.rating_indicator import RatingCircleIndicator
    from desktop.theme import (
        FILM_ACCENT_HOVER,
        FILM_RATING_TRACK,
        FILM_RATING_VALUE,
        FILM_SURFACE_0,
        FILM_TEXT,
        FILM_TEXT_SUBTLE,
    )

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
    assert ring.width() == detail_profiles.RATING_CIRCLE_WIDGET_SIZE
    assert ring.height() == detail_profiles.RATING_CIRCLE_WIDGET_SIZE
    assert ring._is_tmdb_ring is True
    assert ring._accent == FILM_RATING_VALUE
    assert ring._accent_secondary == FILM_ACCENT_HOVER
    assert ring._track_color == FILM_RATING_TRACK
    assert ring._surface_color == FILM_SURFACE_0
    assert ring._value_color == FILM_TEXT
    assert ring._label_color == FILM_TEXT_SUBTLE


def test_rating_circle_indicator_keeps_fixed_circle_size(qapp) -> None:
    from desktop.shared.detail import profiles as detail_profiles
    from desktop.shared.detail.rating_indicator import RatingCircleIndicator

    ring = RatingCircleIndicator("моя")
    original_height = ring.height()

    ring.set_score(9.0)

    assert ring.width() == detail_profiles.RATING_CIRCLE_WIDGET_SIZE
    assert ring.height() == original_height
    assert ring.height() == detail_profiles.RATING_CIRCLE_WIDGET_SIZE


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
    import desktop.settings.app_settings  # noqa: F401
    from desktop.shared.detail.main_info import build_main_info_items

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
        {"label": "Где смотреть", "value": "Неизвестно"},
        {"label": "Голоса TMDb", "value": "3.5к"},
    ]


def test_format_votes_display_uses_compact_tmdb_votes() -> None:
    from desktop.shared.detail.main_info import format_votes_display

    assert format_votes_display(8) == "Крайне мало"
    assert format_votes_display(12) == "0.1к"
    assert format_votes_display(99) == "0.1к"
    assert format_votes_display(777) == "0.8к"
    assert format_votes_display(1200) == "1.2к"
    assert format_votes_display(12000) == "12к"


def test_build_main_info_items_formats_air_dates() -> None:
    from desktop.shared.detail.main_info import build_main_info_items, format_air_date_display

    assert format_air_date_display("2022-03-16") == "16 мар 2022"
    items = build_main_info_items(
        {
            "object_type": "series",
            "first_air_date": "2015-02-08",
            "last_air_date": "2022-08-15",
            "last_episode_to_air": {"air_date": "2022-08-15", "name": "Финал"},
        }
    )

    assert {"label": "Премьера", "value": "8 фев 2015"} in items
    assert {"label": "Последний эпизод", "value": "15 авг 2022"} in items


def test_build_main_info_items_uses_last_air_date_fallback() -> None:
    from desktop.shared.detail.main_info import build_main_info_items

    items = build_main_info_items(
        {
            "object_type": "series",
            "first_air_date": "2020-02-10",
            "last_air_date": "2024-11-07",
        }
    )

    assert {"label": "Премьера", "value": "10 фев 2020"} in items
    assert {"label": "Последний эпизод", "value": "7 ноя 2024"} in items


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


def test_build_title_meta_text_formats_movie_runtime_next_to_year() -> None:
    from desktop.shared.detail import build_title_meta_text

    assert build_title_meta_text({"media_type": "movie", "year": 2025, "runtime": 135}) == "2025 • 2 ч 15 мин"
    assert build_title_meta_text({"media_type": "movie", "runtime": 45}) == "45 мин"


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
        {"label": "Где смотреть", "value": "Неизвестно"},
    ]


def test_build_main_info_items_compacts_watch_provider_overflow() -> None:
    from desktop.watched import build_main_info_items

    provider_item = next(
        item
        for item in build_main_info_items(
            {
                "object_type": "series",
                "watch_providers": ["premier", "Kinopoisk", "Okko", "Ivi"],
            }
        )
        if item["label"] == "Где смотреть"
    )

    assert provider_item == {
        "label": "Где смотреть",
        "value": "Premier, Kinopoisk +2",
        "tooltip": "Okko, Ivi",
    }


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
        {"label": "Статус", "value": "Завершен"},
        {"label": "Длительность серии", "value": "52 мин"},
    ]


def test_build_main_info_items_includes_former_additional_fields() -> None:
    from desktop.watched import build_main_info_items

    items = build_main_info_items(
        {
            "object_type": "series",
            "status": "Ended",
            "episode_run_time": [52],
        }
    )

    assert {"label": "Статус", "value": "Завершен"} in items
    assert {"label": "Длительность серии", "value": "52 мин"} in items


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
                "first_air_date": "2015-02-08",
                "last_air_date": "2022-08-15",
                "last_episode_to_air": {"air_date": "2022-08-15", "episode_number": 13},
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
    assert card["first_air_date"] == "2015-02-08"
    assert card["last_air_date"] == "2022-08-15"
    assert card["last_episode_to_air"] == {"air_date": "2022-08-15", "episode_number": 13}
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
    assert count_active_filters(has_media_type_filter=True) == 1


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
    assert watched_filters_are_active_from_ranges(media_type="movie") is True
    assert watched_filters_are_active_from_ranges(media_type="unexpected") is False
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
    assert format_watched_filters_label(has_media_type_filter=True) == "▸ Фильтры активны"
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
    assert 'tr("common.sort")' in sidebar_source
    assert "reset_all" in filters_source
    assert "watchedScoreReset" not in filters_source
    assert "watchedYearReset" not in filters_source
    assert 'tr("watched.context.delete_record")' in actions_source
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

    import desktop.shared.detail.card_layout as card_layout_module

    layout_source = inspect.getsource(card_layout_module.build_detail_card_layout)

    assert "info_column.addStretch" not in layout_source
    assert "content_layout.addStretch(1)" in layout_source
    assert "root.addStretch(1)" not in layout_source
    assert "QSizePolicy.Policy.Minimum" in layout_source
    assert "setWordWrap(True)" in layout_source
    assert "maximumHeight" not in layout_source


def test_detail_card_rename_keeps_backward_compatibility() -> None:
    from desktop.shared.detail import DetailCard, WatchedDetailCard

    assert DetailCard is WatchedDetailCard


@pytest.mark.parametrize(
    "profile_name",
    [
        "DETAIL_CARD_LAYOUT_PROFILE",
        "CANDIDATE_DETAIL_CARD_PROFILE",
        "ADD_TITLE_PREVIEW_CARD_PROFILE",
    ],
)
def test_detail_card_builds_layout_for_supported_profiles(qapp, profile_name) -> None:
    from PyQt6.QtWidgets import QLabel, QFrame, QPushButton, QWidget

    from desktop.shared.detail import DetailCard
    from desktop.shared.detail import profiles as detail_profiles

    profile = getattr(detail_profiles, profile_name)
    detail = DetailCard(profile=profile)
    hero = detail.widget
    poster = hero.findChild(QFrame, "detailPosterShell")
    title = hero.findChild(QLabel, "detailTitle")
    overview = hero.findChild(QLabel, "detailOverviewText")
    main_info = hero.findChild(QWidget, "detailMainInfoSection")
    toggle = hero.findChild(QPushButton, "detailMainInfoToggleButton")

    assert hero.objectName() == "detailHeroCard"
    assert poster is not None
    assert poster.minimumWidth() == profile.detail_poster_width
    assert poster.minimumHeight() == profile.detail_poster_height
    assert title is not None and title.wordWrap() is True
    assert overview is not None and overview.wordWrap() is True
    assert main_info is not None and main_info.isHidden() is False
    assert toggle is not None and toggle.isHidden() is True

    mark_button = hero.findChild(QPushButton, "candidateMarkWatchedButton")
    hide_button = hero.findChild(QPushButton, "candidateHideButton")
    if profile.show_mark_watched_button:
        assert mark_button is not None
    else:
        assert mark_button is None
    if profile.show_hide_candidate_button:
        assert hide_button is not None
    else:
        assert hide_button is None


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
    assert info_column.layout().contentsMargins().top() == DETAIL_CARD_LAYOUT_PROFILE.detail_info_top_offset
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
    assert all(chip.testAttribute(Qt.WidgetAttribute.WA_StyledBackground) for chip in chips)


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
    chip_score_gap = info_layout.itemAt(info_layout.indexOf(chips) + 1).spacerItem()
    assert chip_score_gap.sizeHint().height() == DETAIL_CARD_LAYOUT_PROFILE.detail_micro_spacing


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
    row_count = chips.layout().count()
    expected_height = (
        row_count * DETAIL_CARD_LAYOUT_PROFILE.detail_chip_height
        + max(0, row_count - 1) * DETAIL_CARD_LAYOUT_PROFILE.detail_chip_row_gap
    )

    assert 1 <= row_count <= DETAIL_CARD_LAYOUT_PROFILE.detail_chip_max_rows
    assert chips.height() == expected_height


def test_watched_detail_card_hides_overview_without_text() -> None:
    import inspect

    import desktop.shared.detail.card_layout as card_layout_module
    import desktop.shared.detail.card as watched_view_module

    source = inspect.getsource(watched_view_module.WatchedDetailCard.show_entry)
    layout_source = inspect.getsource(card_layout_module.build_detail_card_layout)
    assert "has_overview_text(card)" in source
    assert "_overview_frame.setVisible(False)" in source
    assert "detailOverviewDivider" in layout_source
    assert "detail_overview_top_gap" in layout_source


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
                "overview": "   ",
            },
        )
    )
    qapp.processEvents()

    section = detail.widget.findChild(QFrame, "detailOverviewSection")
    gap = detail.widget.findChild(QWidget, "detailOverviewTopGap")

    assert section is not None
    assert section.isHidden() is True
    assert gap is not None
    assert gap.isHidden() is True


def test_detail_overview_section_uses_space_below_poster(qapp) -> None:
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

    poster_column = detail.widget.findChild(QWidget, "detailPosterColumn")
    poster = detail.widget.findChild(QFrame, "detailPosterShell")
    section = detail.widget.findChild(QFrame, "detailOverviewSection")
    gap = detail.widget.findChild(QWidget, "detailOverviewTopGap")

    assert poster_column is not None
    assert poster is not None
    assert section is not None
    assert gap is not None
    poster_layout = poster_column.layout()
    assert poster_layout.indexOf(poster) < poster_layout.indexOf(gap) < poster_layout.indexOf(section)
    assert gap.height() == DETAIL_CARD_LAYOUT_PROFILE.detail_overview_top_gap


def test_detail_card_uses_profile_composition_widths(qapp) -> None:
    from PyQt6.QtWidgets import QFrame, QWidget

    from desktop.shared.detail import DETAIL_CARD_LAYOUT_PROFILE, WatchedDetailCard

    detail = WatchedDetailCard(profile=DETAIL_CARD_LAYOUT_PROFILE)

    content = detail.widget.findChild(QWidget, "detailContentContainer")
    info_column = detail.widget.findChild(QWidget, "detailInfoColumn")
    overview = detail.widget.findChild(QFrame, "detailOverviewSection")
    main_info = detail.widget.findChild(QWidget, "detailMainInfoSection")

    assert content.maximumWidth() == DETAIL_CARD_LAYOUT_PROFILE.detail_content_max_width
    assert info_column.maximumWidth() == DETAIL_CARD_LAYOUT_PROFILE.detail_info_column_max_width
    assert overview.maximumWidth() == DETAIL_CARD_LAYOUT_PROFILE.detail_poster_width
    assert overview.minimumWidth() == DETAIL_CARD_LAYOUT_PROFILE.detail_poster_width
    assert main_info.maximumWidth() == DETAIL_CARD_LAYOUT_PROFILE.detail_section_max_width


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


def test_detail_overview_width_is_fixed_to_poster_width(qapp) -> None:
    from PyQt6.QtWidgets import QFrame

    from desktop.shared.detail import DETAIL_CARD_LAYOUT_PROFILE, WatchedDetailCard

    detail = WatchedDetailCard(profile=DETAIL_CARD_LAYOUT_PROFILE)
    section = detail.widget.findChild(QFrame, "detailOverviewSection")

    assert section is not None
    assert section.minimumWidth() == DETAIL_CARD_LAYOUT_PROFILE.detail_poster_width
    assert section.maximumWidth() == DETAIL_CARD_LAYOUT_PROFILE.detail_poster_width


def test_detail_overview_has_no_absolute_positioning() -> None:
    import inspect

    import desktop.shared.detail.card_layout as card_layout_module

    layout_source = inspect.getsource(card_layout_module.build_detail_card_layout)
    overview_source = layout_source[
        layout_source.index('setObjectName("detailOverviewSection")') :
        layout_source.index("info_column.addWidget")
    ]

    assert ".move(" not in overview_source
    assert "setGeometry(" not in overview_source


def test_watched_detail_card_renders_main_info_block() -> None:
    import inspect

    import desktop.shared.detail.card_layout as card_layout_module
    import desktop.shared.detail.card as watched_view_module

    layout_source = inspect.getsource(card_layout_module.build_detail_card_layout)
    show_source = inspect.getsource(watched_view_module.WatchedDetailCard.show_entry)
    empty_source = inspect.getsource(watched_view_module.WatchedDetailCard.show_empty)

    assert 'tr("detail.main_info.title")' in layout_source
    assert 'setObjectName("detailMainInfoSection")' in layout_source
    assert 'setObjectName("detailMainInfoPanel")' in layout_source
    assert 'setObjectName("detailMainInfoHeader")' in layout_source
    assert 'setObjectName("detailMainInfoToggleButton")' in layout_source
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
    assert section.layout().spacing() == DETAIL_CARD_LAYOUT_PROFILE.detail_main_info_header_panel_gap
    assert panel is not None
    assert panel.layout().verticalSpacing() == DETAIL_CARD_LAYOUT_PROFILE.detail_main_info_row_gap
    assert labels == ["Тип", "Страна", "Где смотреть", "Голоса TMDb"]
    assert "Сериал" in values
    assert "США" in values
    assert "12.9к" in values


def test_detail_main_info_header_does_not_share_row_with_toggle(qapp) -> None:
    from PyQt6.QtWidgets import QLabel, QPushButton, QSizePolicy

    from desktop.shared.detail import DETAIL_CARD_LAYOUT_PROFILE, WatchedDetailCard

    detail = WatchedDetailCard(profile=DETAIL_CARD_LAYOUT_PROFILE)
    detail.show_entry(
        (
            "Alpha",
            {},
            {
                "title": "Alpha",
                "runtime_status": "watched",
                "country": "US",
                "object_type": "movie",
                "watch_providers": None,
                "tmdb_votes": 2600,
                "status": "Released",
            },
        )
    )
    detail.widget.resize(900, 700)
    detail.widget.show()
    _flush_qt_deferred_deletes(qapp)

    header = detail.widget.findChild(QLabel, "detailMainInfoHeader")
    toggle = detail.widget.findChild(QPushButton, "detailMainInfoToggleButton")

    assert header is not None
    assert toggle is not None
    assert toggle.isHidden() is False
    assert header.wordWrap() is True
    assert header.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Expanding
    assert toggle.geometry().top() >= header.geometry().bottom()
    assert toggle.geometry().left() <= header.geometry().left() + DETAIL_CARD_LAYOUT_PROFILE.detail_small_spacing
    assert toggle.geometry().right() <= header.geometry().right()


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


def test_detail_main_info_panel_renders_former_additional_rows(qapp) -> None:
    from PyQt6.QtWidgets import QLabel, QFrame, QPushButton

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
    _flush_qt_deferred_deletes(qapp)

    panel = detail.widget.findChild(QFrame, "detailMainInfoPanel")
    toggle = detail.widget.findChild(QPushButton, "detailMainInfoToggleButton")
    labels = [item.text() for item in panel.findChildren(QLabel, "detailMainInfoLabel")]
    values = [item.text() for item in panel.findChildren(QLabel, "detailMainInfoValue")]

    assert "Статус" in labels
    assert "Длительность серии" not in labels
    assert "Завершен" in values
    assert toggle is not None
    assert toggle.isHidden() is False
    assert toggle.text() == "Показать больше"

    toggle.click()
    _flush_qt_deferred_deletes(qapp)

    labels = [item.text() for item in panel.findChildren(QLabel, "detailMainInfoLabel")]
    values = [item.text() for item in panel.findChildren(QLabel, "detailMainInfoValue")]

    assert "Длительность серии" in labels
    assert "52 мин" in values
    assert toggle.text() == "Скрыть"


def test_detail_main_info_toggle_is_hidden_for_four_or_fewer_rows(qapp) -> None:
    from PyQt6.QtWidgets import QLabel, QFrame, QPushButton

    from desktop.shared.detail import DETAIL_CARD_LAYOUT_PROFILE, WatchedDetailCard

    detail = WatchedDetailCard(profile=DETAIL_CARD_LAYOUT_PROFILE)
    detail.show_entry(
        (
            "Alpha",
            {},
            {
                "title": "Alpha",
                "runtime_status": "watched",
                "country": "US",
                "object_type": "series",
                "watch_providers": ["Kinopoisk"],
                "tmdb_votes": 12850,
            },
        )
    )
    _flush_qt_deferred_deletes(qapp)

    panel = detail.widget.findChild(QFrame, "detailMainInfoPanel")
    toggle = detail.widget.findChild(QPushButton, "detailMainInfoToggleButton")
    labels = [item.text() for item in panel.findChildren(QLabel, "detailMainInfoLabel")]

    assert labels == ["Тип", "Страна", "Где смотреть", "Голоса TMDb"]
    assert toggle is not None
    assert toggle.isHidden() is True


def test_detail_main_info_values_are_single_line_with_provider_tooltip(qapp) -> None:
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
                "country": "RU",
                "object_type": "series",
                "watch_providers": ["premier", "Kinopoisk", "Okko", "Ivi"],
                "tmdb_votes": 777,
            },
        )
    )
    _flush_qt_deferred_deletes(qapp)

    panel = detail.widget.findChild(QFrame, "detailMainInfoPanel")
    values = panel.findChildren(QLabel, "detailMainInfoValue")
    provider_value = next(item for item in values if item.text().startswith("Premier, Kinopoisk"))

    assert all(item.wordWrap() is False for item in values)
    assert all(item.minimumHeight() == item.maximumHeight() for item in values)
    assert provider_value.text() == "Premier, Kinopoisk +2"
    assert provider_value.toolTip() == "Okko, Ivi"


def test_detail_main_info_toggle_collapses_and_expands_rows(qapp) -> None:
    from PyQt6.QtWidgets import QLabel, QFrame, QPushButton

    from desktop.shared.detail import DETAIL_CARD_LAYOUT_PROFILE, WatchedDetailCard

    detail = WatchedDetailCard(profile=DETAIL_CARD_LAYOUT_PROFILE)
    detail.show_entry(
        (
            "Alpha",
            {},
            {
                "title": "Alpha",
                "runtime_status": "watched",
                "country": "RU",
                "object_type": "series",
                "watch_providers": ["Premier", "Kinopoisk"],
                "tmdb_votes": 417,
                "status": "Returning Series",
                "episode_run_time": [48],
            },
        )
    )
    _flush_qt_deferred_deletes(qapp)

    panel = detail.widget.findChild(QFrame, "detailMainInfoPanel")
    toggle = detail.widget.findChild(QPushButton, "detailMainInfoToggleButton")
    labels = [item.text() for item in panel.findChildren(QLabel, "detailMainInfoLabel")]

    assert labels == ["Тип", "Страна", "Где смотреть", "Голоса TMDb"]
    assert toggle is not None
    assert toggle.text() == "Показать больше"

    toggle.click()
    _flush_qt_deferred_deletes(qapp)
    labels = [item.text() for item in panel.findChildren(QLabel, "detailMainInfoLabel")]

    assert labels == [
        "Тип",
        "Страна",
        "Где смотреть",
        "Голоса TMDb",
        "Статус",
        "Длительность серии",
    ]
    assert toggle.text() == "Скрыть"

    toggle.click()
    _flush_qt_deferred_deletes(qapp)
    labels = [item.text() for item in panel.findChildren(QLabel, "detailMainInfoLabel")]

    assert labels == ["Тип", "Страна", "Где смотреть", "Голоса TMDb"]
    assert toggle.text() == "Показать больше"


def test_detail_main_info_resets_to_collapsed_for_new_entry(qapp) -> None:
    from PyQt6.QtWidgets import QLabel, QFrame, QPushButton

    from desktop.shared.detail import DETAIL_CARD_LAYOUT_PROFILE, WatchedDetailCard

    detail = WatchedDetailCard(profile=DETAIL_CARD_LAYOUT_PROFILE)
    first_card = {
        "title": "Alpha",
        "runtime_status": "watched",
        "country": "RU",
        "object_type": "series",
        "watch_providers": ["Premier"],
        "tmdb_votes": 417,
        "status": "Returning Series",
        "episode_run_time": [48],
    }
    second_card = {
        "title": "Bravo",
        "runtime_status": "watched",
        "country": "US",
        "object_type": "series",
        "watch_providers": ["HBO"],
        "tmdb_votes": 12850,
        "status": "Ended",
        "episode_run_time": [52],
    }

    detail.show_entry(("Alpha", {}, first_card))
    _flush_qt_deferred_deletes(qapp)
    toggle = detail.widget.findChild(QPushButton, "detailMainInfoToggleButton")
    toggle.click()
    _flush_qt_deferred_deletes(qapp)

    detail.show_entry(("Bravo", {}, second_card))
    _flush_qt_deferred_deletes(qapp)

    panel = detail.widget.findChild(QFrame, "detailMainInfoPanel")
    labels = [item.text() for item in panel.findChildren(QLabel, "detailMainInfoLabel")]

    assert labels == ["Тип", "Страна", "Где смотреть", "Голоса TMDb"]
    assert toggle.text() == "Показать больше"


def test_detail_card_does_not_create_additional_info_section(qapp) -> None:
    from PyQt6.QtWidgets import QWidget

    from desktop.shared.detail import DETAIL_CARD_LAYOUT_PROFILE, WatchedDetailCard

    detail = WatchedDetailCard(profile=DETAIL_CARD_LAYOUT_PROFILE)
    section = detail.widget.findChild(QWidget, "detailAdditionalInfoSection")

    assert section is None


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
    score_info_gap = info_layout.itemAt(info_layout.indexOf(score_row) + 1).spacerItem()
    assert score_info_gap.sizeHint().height() == DETAIL_CARD_LAYOUT_PROFILE.detail_micro_spacing


def test_watched_detail_card_does_not_render_my_score_ring() -> None:
    import inspect

    import desktop.shared.detail.card_layout as card_layout_module

    layout_source = inspect.getsource(card_layout_module.build_detail_card_layout)

    assert 'score_summary_widget.setObjectName("detailScoreSummaryRow")' in layout_source
    assert 'owner._final_score_stars_block.setObjectName("detailFinalScoreStars")' in layout_source
    assert 'owner._final_score_stars_lane.setObjectName("detailFinalScoreStarsLane")' in layout_source
    assert 'RatingCircleIndicator("моя"' not in layout_source
    assert "owner._metrics_row.addWidget(owner._score_indicator" not in layout_source
    assert "StarRatingIndicator(" in layout_source
    assert "star_size=profile.detail_star_size" in layout_source
    assert "star_gap=profile.detail_star_gap" in layout_source
    assert "_rating_stars_row" not in layout_source
    assert "_tmdb_ring_slot.setFixedSize(" in layout_source
    assert "profile.detail_rating_widget_size," in layout_source
    assert "owner._score_summary_row.addWidget" in layout_source


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


def test_final_score_stars_are_centered_between_tmdb_ring_and_main_info(qapp) -> None:
    import desktop.settings.app_settings  # noqa: F401 — preload before theme.shared imports
    from PyQt6.QtCore import QPoint
    from PyQt6.QtWidgets import QWidget

    from desktop.shared.detail import DETAIL_CARD_LAYOUT_PROFILE, WatchedDetailCard

    detail = WatchedDetailCard(profile=DETAIL_CARD_LAYOUT_PROFILE)
    frame = detail.widget
    frame.show()
    frame.resize(1200, 800)
    detail.show_entry(
        (
            "Alpha",
            {},
            {
                "title": "Alpha",
                "runtime_status": "watched",
                "tmdb_score": 7.8,
                "final_score": 0.78,
                "country": "RU",
                "object_type": "series",
                "genres": ["Thriller"],
            },
        )
    )
    qapp.processEvents()

    hero = detail.widget
    ring = hero.findChild(QWidget, "detailTmdbRingSlot")
    stars = hero.findChild(QWidget, "detailFinalScoreStars")
    main_info = hero.findChild(QWidget, "detailMainInfoSection")

    assert ring is not None
    assert stars is not None
    assert main_info is not None

    def right_edge(widget: QWidget) -> int:
        top_right = widget.mapTo(hero, QPoint(widget.width(), 0))
        return top_right.x()

    def left_edge(widget: QWidget) -> int:
        return widget.mapTo(hero, QPoint(0, 0)).x()

    ring_right = right_edge(ring)
    main_right = right_edge(main_info)
    stars_left = left_edge(stars)
    stars_right = right_edge(stars)
    corridor = main_right - ring_right
    stars_center = (stars_left + stars_right) / 2
    target_center = ring_right + corridor / 2

    assert corridor > stars.width()
    assert abs(stars_center - target_center) <= 2.0


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
    from PyQt6.QtWidgets import QLabel, QFrame, QWidget

    from desktop.shared.detail import DETAIL_CARD_LAYOUT_PROFILE, WatchedDetailCard

    def is_descendant(child: QWidget, parent: QWidget) -> bool:
        current = child
        while current is not None:
            if current is parent:
                return True
            current = current.parent()
        return False

    detail = WatchedDetailCard(profile=DETAIL_CARD_LAYOUT_PROFILE)
    detail.widget.resize(1200, 800)
    detail.widget.show()
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
    assert is_descendant(badge, shell)
    assert badge.text() == "★ 9.0"
    assert badge.isHidden() is False
    assert badge.testAttribute(Qt.WidgetAttribute.WA_StyledBackground) is True
    badge_position = badge.mapTo(shell, badge.rect().topLeft())
    assert abs(badge_position.x() - DETAIL_CARD_LAYOUT_PROFILE.detail_user_score_badge_left) <= 1
    assert abs(badge_position.y() - DETAIL_CARD_LAYOUT_PROFILE.detail_user_score_badge_top) <= 1


def test_watched_user_score_badge_has_readable_background() -> None:
    import inspect

    import desktop.shared.detail.card_layout as card_layout_module
    from desktop.theme import COLOR_TEXT, COLOR_TEXT_INVERTED, FILM_MOVIE_BADGE_BG, FILM_MOVIE_BADGE_BORDER
    from desktop.theme.styles.detail_card import build_detail_card_style

    style = build_detail_card_style()
    layout_source = inspect.getsource(card_layout_module.build_detail_card_layout)

    assert "QLabel#detailUserScoreBadge" in style
    assert f"background-color: {COLOR_TEXT}" in style
    assert f"border: 1px solid {COLOR_TEXT}" in style
    assert f"color: {COLOR_TEXT_INVERTED}" in style
    assert f"background-color: {FILM_MOVIE_BADGE_BG}" in style
    assert f"border: 1px solid {FILM_MOVIE_BADGE_BORDER}" in style
    assert "class UserScoreBadgeLabel(QLabel)" in layout_source
    assert "drawRoundedRect" in layout_source
    assert "border_color = COLOR_TEXT" in layout_source
    assert "fill_color = COLOR_TEXT" in layout_source
    assert "border_color = FILM_MOVIE_BADGE_BORDER" in layout_source
    assert "fill_color = FILM_MOVIE_BADGE_BG" in layout_source


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
    from PyQt6.QtWidgets import QLabel

    from desktop.shared.detail import CANDIDATE_DETAIL_CARD_PROFILE, WatchedDetailCard

    detail = WatchedDetailCard(profile=CANDIDATE_DETAIL_CARD_PROFILE)
    detail.show_entry(("Candidate", {}, {"title": "Candidate", "user_score": 9, "tmdb_score": 7.2}))
    qapp.processEvents()

    badge = detail.widget.findChild(QLabel, "detailUserScoreBadge")

    assert badge is not None
    assert badge.text() == ""
    assert badge.isHidden() is True


def test_candidate_detail_actions_are_icon_only_under_poster() -> None:
    import inspect

    import desktop.shared.detail.card_layout as card_layout_module

    layout_source = inspect.getsource(card_layout_module.build_detail_card_layout)

    assert 'QPushButton("👁")' not in layout_source
    assert 'QPushButton("Hide")' not in layout_source
    assert 'QPushButton()' in layout_source
    assert 'make_detail_action_icon("eye"' in layout_source
    assert 'make_detail_action_icon("hide"' in layout_source
    assert "owner._poster_actions_layout.addWidget" in layout_source
    assert "poster_column.addWidget(owner._poster_actions_widget)" in layout_source
    assert "title_row.addWidget(owner._poster_actions_widget" not in layout_source
    assert "owner._metrics_row.addWidget(owner._mark_watched_button" not in layout_source
    assert "owner._metrics_row.addWidget(owner._hide_button" not in layout_source


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
        "DETAIL_HERO_CARD_PADDING_TOP": 12,
        "DETAIL_HERO_MIN_WIDTH": 980,
        "DETAIL_HERO_PREFERRED_MIN_WIDTH": 1200,
        "DETAIL_CONTENT_MAX_WIDTH": 1120,
        "DETAIL_POSTER_WIDTH": 360,
        "DETAIL_POSTER_HEIGHT": 530,
        "DETAIL_POSTER_RADIUS": 16,
        "DETAIL_POSTER_BORDER_WIDTH": 1,
        "DETAIL_POSTER_RIGHT_GAP": 42,
        "DETAIL_INFO_MIN_WIDTH": 350,
        "DETAIL_INFO_MAX_WIDTH": 760,
        "DETAIL_INFO_COLUMN_MAX_WIDTH": 700,
        "DETAIL_INFO_TOP_OFFSET": 18,
        "DETAIL_TITLE_FONT_FAMILY": "Segoe UI",
        "DETAIL_TITLE_FONT_FALLBACK": "Arial, sans-serif",
        "DETAIL_TITLE_FONT_SIZE": 34,
        "FONT_DETAIL_MAIN_INFO_HEADER": 17,
        "FONT_DETAIL_MAIN_INFO_LABEL": 17,
        "FONT_DETAIL_MAIN_INFO_VALUE": 18,
        "FONT_DETAIL_OVERVIEW_TEXT": 19,
        "DETAIL_TITLE_LINE_HEIGHT": 42,
        "DETAIL_TITLE_MAX_LINES": 2,
        "DETAIL_CHIP_HEIGHT": 42,
        "DETAIL_CHIP_RADIUS": 21,
        "DETAIL_CHIP_H_PADDING": 18,
        "DETAIL_CHIP_FONT_SIZE": 16,
        "DETAIL_CHIP_ROW_GAP": 10,
        "DETAIL_CHIP_COL_GAP": 14,
        "DETAIL_CHIP_MAX_ROWS": 2,
        "DETAIL_CHIP_MAX_WIDTH": 210,
        "DETAIL_SCORE_ROW_TOP_GAP": 34,
        "DETAIL_RATING_WIDGET_SIZE": 136,
        "DETAIL_RATING_CIRCLE_DIAMETER": 122,
        "DETAIL_STARS_LEFT_GAP": 52,
        "DETAIL_STAR_SIZE": 36,
        "DETAIL_STAR_GAP": 9,
        "DETAIL_USER_SCORE_BADGE_MIN_WIDTH": 72,
        "DETAIL_USER_SCORE_BADGE_HEIGHT": 40,
        "DETAIL_USER_SCORE_BADGE_RADIUS": 20,
        "DETAIL_USER_SCORE_BADGE_FONT_SIZE": 16,
        "DETAIL_USER_SCORE_BADGE_TOP": 16,
        "DETAIL_USER_SCORE_BADGE_LEFT": 16,
        "DETAIL_USER_SCORE_BADGE_PADDING_X": 10,
        "DETAIL_MAIN_INFO_TOP_GAP": 38,
        "DETAIL_MAIN_INFO_PANEL_RADIUS": 16,
        "DETAIL_MAIN_INFO_PANEL_PADDING_X": 34,
        "DETAIL_MAIN_INFO_PANEL_PADDING_Y": 22,
        "DETAIL_MAIN_INFO_ROW_HEIGHT": 54,
        "DETAIL_MAIN_INFO_ROW_GAP": 12,
        "DETAIL_MAIN_INFO_HEADER_PANEL_GAP": 28,
        "DETAIL_MAIN_INFO_LABEL_WIDTH": 230,
        "DETAIL_OVERVIEW_TOP_GAP": 14,
        "DETAIL_OVERVIEW_LEFT_INSET": 0,
        "DETAIL_OVERVIEW_TITLE_TOP_GAP": 14,
        "DETAIL_OVERVIEW_TEXT_TOP_GAP": 20,
        "DETAIL_OVERVIEW_MAX_LINES_COLLAPSED": 4,
        "DETAIL_OVERVIEW_MAX_WIDTH": 360,
        "DETAIL_TITLE_CHIPS_GAP": 42,
        "DETAIL_SCORE_MAIN_INFO_GAP": 30,
        "DETAIL_SECTION_MAX_WIDTH": 920,
    }

    for token_name, expected_value in expected_tokens.items():
        assert getattr(theme, token_name) == expected_value

    assert DETAIL_CARD_LAYOUT_PROFILE.detail_poster_width == theme.DETAIL_POSTER_WIDTH
    assert DETAIL_CARD_LAYOUT_PROFILE.detail_poster_border_width == theme.DETAIL_POSTER_BORDER_WIDTH
    assert DETAIL_CARD_LAYOUT_PROFILE.detail_poster_content_width == theme.DETAIL_POSTER_WIDTH - 2
    assert DETAIL_CARD_LAYOUT_PROFILE.detail_poster_content_radius == theme.DETAIL_POSTER_RADIUS - 1
    assert DETAIL_CARD_LAYOUT_PROFILE.detail_hero_card_padding_top == theme.DETAIL_HERO_CARD_PADDING_TOP
    assert DETAIL_CARD_LAYOUT_PROFILE.detail_rating_widget_size == theme.DETAIL_RATING_WIDGET_SIZE
    assert DETAIL_CARD_LAYOUT_PROFILE.detail_user_score_badge_height == theme.DETAIL_USER_SCORE_BADGE_HEIGHT
    assert DETAIL_CARD_LAYOUT_PROFILE.detail_overview_left_inset == theme.DETAIL_OVERVIEW_LEFT_INSET
    assert DETAIL_CARD_LAYOUT_PROFILE.detail_overview_max_width == DETAIL_CARD_LAYOUT_PROFILE.detail_poster_width
    assert DETAIL_CARD_LAYOUT_PROFILE.detail_content_max_width == theme.DETAIL_CONTENT_MAX_WIDTH
    assert DETAIL_CARD_LAYOUT_PROFILE.detail_info_column_max_width == theme.DETAIL_INFO_COLUMN_MAX_WIDTH
    assert DETAIL_CARD_LAYOUT_PROFILE.detail_info_top_offset == theme.DETAIL_INFO_TOP_OFFSET
    assert DETAIL_CARD_LAYOUT_PROFILE.detail_overview_max_width == theme.DETAIL_OVERVIEW_MAX_WIDTH
    assert DETAIL_CARD_LAYOUT_PROFILE.detail_section_max_width == theme.DETAIL_SECTION_MAX_WIDTH
    assert DETAIL_CARD_LAYOUT_PROFILE.detail_title_chips_gap == theme.DETAIL_TITLE_CHIPS_GAP
    assert DETAIL_CARD_LAYOUT_PROFILE.detail_micro_spacing == theme.DETAIL_SCORE_MAIN_INFO_GAP
    assert DETAIL_CARD_LAYOUT_PROFILE.detail_section_spacing == theme.DETAIL_SCORE_MAIN_INFO_GAP


def test_film_theme_tokens_match_visual_brief() -> None:
    from desktop import theme

    expected = {
        "window_bg": "#050B14",
        "surface_0": "#071322",
        "surface_1": "#0A182A",
        "surface_2": "#0B1A2D",
        "border_weak": "#17314F",
        "border": "#1E4B78",
        "border_strong": "#2EA8FF",
        "accent": "#2EA8FF",
        "accent_hover": "#35D7F2",
        "accent_pressed": "#477DFF",
        "accent_dim": "#0B3558",
        "text": "#F4F8FF",
        "text_subtle": "#C9D6EA",
        "text_muted": "#8798B3",
        "chip_bg": "#0B1E34",
        "chip_border": "#22517F",
        "chip_text": "#DCEAFF",
        "movie_badge_bg": "#0B2542",
        "movie_badge_border": "#2EA8FF",
        "movie_badge_text": "#EAF6FF",
        "rating_track": "#17314F",
        "rating_value": "#2EA8FF",
        "star_on": "#35AFFF",
        "star_off": "#2A374A",
        "scrollbar_bg": "#071322",
        "scrollbar_handle": "#1E4B78",
        "scrollbar_handle_hover": "#2EA8FF",
    }

    assert theme.FILM_COLORS == expected
    assert theme.FILM_WINDOW_BG == expected["window_bg"]
    assert theme.FILM_ACCENT == expected["accent"]
    assert theme.FILM_STAR_ON == expected["star_on"]


def test_detail_card_style_uses_requested_font_sizes() -> None:
    from desktop.theme import tokens
    from desktop.theme.scaling import detail_px, font_px, set_ui_scale
    from desktop.theme.styles.detail_card import build_detail_card_style

    set_ui_scale(1.0)
    style = build_detail_card_style()

    assert "QLabel#detailTitle" in style
    assert f"font-size: {font_px(tokens.DETAIL_TITLE_FONT_SIZE)}px;" in style
    assert "QLabel#detailTitleMeta" in style
    assert f"font-size: {font_px(tokens.FONT_SMALL + 4)}px;" in style
    assert "QLabel#detailMainInfoHeader" in style
    assert f"font-size: {font_px(tokens.FONT_DETAIL_MAIN_INFO_HEADER)}px;" in style
    assert f"font-size: {font_px(tokens.FONT_DETAIL_MAIN_INFO_VALUE)}px;" in style
    assert "QPushButton#detailMainInfoToggleButton" in style
    assert "QLabel#detailOverviewText" in style
    assert f"font-size: {font_px(tokens.FONT_DETAIL_OVERVIEW_TEXT)}px;" in style
    assert f"font-size: {font_px(tokens.FONT_OVERVIEW_TITLE)}px;" in style
    assert "detailAdditionalInfo" not in style
    assert "QLabel#detailUserScoreBadge" in style
    assert f"font-size: {font_px(tokens.DETAIL_USER_SCORE_BADGE_FONT_SIZE)}px;" in style
    assert f"min-width: {detail_px(tokens.DETAIL_USER_SCORE_BADGE_MIN_WIDTH)}px;" in style
    assert "QLabel#genrePill" in style
    assert f"font-size: {font_px(tokens.DETAIL_CHIP_FONT_SIZE)}px;" in style
    assert f"padding: 0 {detail_px(tokens.DETAIL_CHIP_H_PADDING)}px;" in style
    assert f"border-radius: {detail_px(tokens.DETAIL_CHIP_RADIUS)}px;" in style
    assert f"background-color: {tokens.FILM_CHIP_BG};" in style
    assert f"border: 1px solid {tokens.FILM_CHIP_BORDER};" in style
    assert f"color: {tokens.FILM_CHIP_TEXT};" in style


def test_detail_card_movie_mode_sets_film_theme_properties(qapp) -> None:
    from PyQt6.QtWidgets import QFrame, QLabel

    from desktop.i18n import tr
    from desktop.shared.detail import DETAIL_CARD_LAYOUT_PROFILE, WatchedDetailCard

    detail = WatchedDetailCard(profile=DETAIL_CARD_LAYOUT_PROFILE)
    detail.show_entry(
        (
            "Movie",
            {"main_info": {"media_type": "movie"}},
            {
                "title": "Movie",
                "media_type": "movie",
                "runtime_status": "watched",
                "genres": ["Drama"],
                "user_score": 8,
            },
        )
    )

    hero = detail.widget
    poster = hero.findChild(QFrame, "detailPosterShell")
    badge = hero.findChild(QLabel, "detailUserScoreBadge")
    media_badge = hero.findChild(QLabel, "detailMediaTypeBadge")
    chips = hero.findChildren(QLabel, "genrePill")

    assert hero.property("mediaType") == "movie"
    assert poster.property("mediaType") == "movie"
    assert badge.property("mediaType") == "movie"
    assert media_badge.property("mediaType") == "movie"
    assert media_badge.text() == tr("media_type.movie").upper()
    assert media_badge.isHidden() is False
    assert chips
    assert {chip.property("mediaType") for chip in chips} == {"movie"}

    detail.show_entry(("Fallback", {}, {"title": "Fallback", "media_type": "unexpected"}))

    assert hero.property("mediaType") == "tv"
    assert poster.property("mediaType") == "tv"
    assert media_badge.property("mediaType") == "tv"
    assert media_badge.text() == tr("media_type.tv").upper()
    assert media_badge.isHidden() is False

    detail.show_empty()

    assert media_badge.isHidden() is True


def test_detail_card_movie_style_uses_film_tokens() -> None:
    from desktop.theme import tokens
    from desktop.theme.styles.detail_card import build_detail_card_style

    style = build_detail_card_style()

    assert 'QFrame#detailHeroCard[mediaType="movie"]' in style
    assert tokens.FILM_WINDOW_BG in style
    assert tokens.FILM_SURFACE_0 in style
    assert tokens.FILM_BORDER in style
    assert tokens.FILM_CHIP_BG in style
    assert tokens.FILM_MOVIE_BADGE_BG in style
    assert "QLabel#detailMediaTypeBadge" in style


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

    import desktop.shared.detail.card_layout as card_layout_module
    import desktop.shared.detail.card as watched_view_module

    layout_source = inspect.getsource(card_layout_module.build_detail_card_layout)
    assert "CustomContextMenu" in layout_source
    assert "_show_poster_context_menu" in layout_source

    menu_source = inspect.getsource(watched_view_module.WatchedDetailCard._show_poster_context_menu)
    assert 'tr("detail.poster.open")' in menu_source
    assert 'tr("detail.poster.cache_folder")' in menu_source

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


def test_watched_list_delegate_uses_film_selection_palette() -> None:
    import inspect

    import desktop.shared.detail.list_delegate as watched_view_module

    source = inspect.getsource(watched_view_module.WatchedListItemDelegate.__new__)

    assert "FILM_ACCENT_DIM" in source
    assert "FILM_ACCENT_HOVER" in source
    assert "FILM_BORDER_WEAK" in source
    assert "glow.setAlpha(110)" in source


def test_watched_list_scrollbar_uses_film_tokens() -> None:
    from desktop.theme import FILM_SCROLLBAR_BG, FILM_SCROLLBAR_HANDLE, FILM_SCROLLBAR_HANDLE_HOVER
    from desktop.theme.styles.watched_shell import build_watched_shell_style

    style = build_watched_shell_style()

    assert "QListWidget#watchedList QScrollBar:vertical" in style
    assert f"background: {FILM_SCROLLBAR_BG};" in style
    assert f"background: {FILM_SCROLLBAR_HANDLE};" in style
    assert f"background: {FILM_SCROLLBAR_HANDLE_HOVER};" in style


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
    assert "_load_entries_for_actions" in source
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
    assert 'tr("watched.context.delete_record")' in source
    assert "_delete_watched_entry" in source
    assert 'tr("watched.context.edit_score")' in source


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
            "first_air_date": "2015-02-08",
            "last_air_date": "2022-08-15",
            "last_episode_to_air": {"air_date": "2022-08-15", "episode_number": 13},
            "tmdb_score": 8.1,
            "tmdb_votes": 12000,
            "imdb_id": "tt123",
            "user_score": 9.0,
        }
    )

    assert card["country"] == "Россия"
    assert card["object_type"] == "series"
    assert card["first_air_date"] == "2015-02-08"
    assert card["last_air_date"] == "2022-08-15"
    assert card["last_episode_to_air"] == {"air_date": "2022-08-15", "episode_number": 13}
    assert card["tmdb_score"] == 8.1
    assert card["tmdb_votes"] == 12000
    assert card["imdb_id"] == "tt123"
    assert "kp_votes" not in card
    assert build_user_score_badge_item(card) is None
    assert "user_score_badge" not in card
    assert "imdb_votes" not in card


def test_build_candidate_readonly_card_respects_data_language(monkeypatch) -> None:
    from desktop.candidates.presenters import build_candidate_readonly_card

    monkeypatch.setattr(
        "desktop.candidates.presenters.resolve_local_poster_path_for_candidate",
        lambda candidate: None,
    )

    candidate = {
        "title": "Лучше звоните Солу",
        "original_title": "Better Call Saul",
        "description": "Русское описание",
        "overview_en": "English overview",
        "genre_keys": ["drama"],
        "year": 2015,
    }

    ru_card = build_candidate_readonly_card(candidate, data_language="ru")
    en_card = build_candidate_readonly_card(candidate, data_language="en")

    assert ru_card["title"] == "Лучше звоните Солу"
    assert ru_card["overview"] == "Русское описание"
    assert ru_card["genres"] == ["Драма"]
    assert en_card["title"] == "Better Call Saul"
    assert en_card["overview"] == "English overview"
    assert en_card["genres"] == ["Drama"]


def test_build_candidate_readonly_card_uses_localized_poster_for_data_language(monkeypatch) -> None:
    from desktop.candidates.presenters import build_candidate_readonly_card

    monkeypatch.setattr(
        "desktop.candidates.presenters.resolve_local_poster_path_for_candidate",
        lambda candidate, data_language="ru": None,
    )
    candidate = {
        "title": "Pool Show",
        "year": 2020,
        "poster_url": "https://image.tmdb.org/t/p/original/ru.jpg",
        "localized": {
            "en": {
                "title": "Pool Show",
                "poster_path": "/en.jpg",
                "poster_url": "https://image.tmdb.org/t/p/original/en.jpg",
            }
        },
    }

    card = build_candidate_readonly_card(candidate, data_language="en")

    assert card["poster_url"] == "https://image.tmdb.org/t/p/original/en.jpg"
    assert card["poster_path"] == "/en.jpg"


def test_candidate_poster_url_for_download_uses_data_language_localized_url(monkeypatch) -> None:
    from desktop.candidates.presenters import candidate_poster_url_for_download

    monkeypatch.setattr(
        "desktop.candidates.presenters.resolve_local_poster_path_for_candidate",
        lambda candidate, data_language="ru": None,
    )
    candidate = {
        "title": "Pool Show",
        "year": 2020,
        "poster_url": "https://image.tmdb.org/t/p/original/ru.jpg",
        "localized": {
            "en": {
                "poster_path": "/en.jpg",
                "poster_url": "https://image.tmdb.org/t/p/original/en.jpg",
            }
        },
    }

    assert (
        candidate_poster_url_for_download(candidate, data_language="en")
        == "https://image.tmdb.org/t/p/original/en.jpg"
    )


def test_candidate_localized_poster_enrichment_persists_pool(monkeypatch) -> None:
    from candidates.pool import localized_posters

    pool = {
        "pool show|2020": {
            "pool_entry_key": "pool show|2020",
            "title": "Pool Show",
            "year": 2020,
            "tmdb_id": 101,
            "poster_url": "https://image.tmdb.org/t/p/original/ru.jpg",
        }
    }
    saved = {}

    monkeypatch.setattr(localized_posters.pool_repository, "load_candidate_pool", lambda: copy.deepcopy(pool))
    monkeypatch.setattr(localized_posters.pool_repository, "save_candidate_pool", lambda data: saved.update(data))

    def fake_details(tmdb_id, *, language=None, append_to_response=None):
        assert (tmdb_id, language) == (101, "en-US")
        return {
            "id": 101,
            "name": "Pool Show",
            "images": {
                "posters": [
                    {
                        "file_path": "/en.jpg",
                        "iso_639_1": "en",
                        "vote_average": 8.0,
                        "vote_count": 10,
                    }
                ],
            },
        }

    updated, changed = localized_posters.ensure_candidate_localized_poster(
        pool["pool show|2020"],
        data_language="en",
        details_func=fake_details,
    )

    assert changed is True
    assert updated["localized"]["en"]["poster_path"] == "/en.jpg"
    assert saved["pool show|2020"]["localized"]["en"]["poster_url"] == "https://image.tmdb.org/t/p/original/en.jpg"


def test_candidate_list_model_resets_poster_cache_on_data_language_change(monkeypatch, qapp) -> None:
    from desktop.candidates.list_model import CandidateListModel

    calls = []

    def fake_resolve(candidate, data_language="ru"):
        calls.append(data_language)
        return f"{data_language}.jpg"

    monkeypatch.setattr(
        "desktop.candidates.list_model.resolve_local_poster_path_for_candidate",
        fake_resolve,
    )
    candidate = {"title": "Pool Show", "year": 2020}
    model = CandidateListModel([candidate], data_language="ru")

    assert model.poster_path_for_candidate(candidate) == "ru.jpg"
    assert model.poster_path_for_candidate(candidate) == "ru.jpg"
    model.set_data_language("en")

    assert model.poster_path_for_candidate(candidate) == "en.jpg"
    assert calls == ["ru", "en"]


def test_candidate_list_model_re_resolves_poster_after_lazy_invalidation(monkeypatch, qapp) -> None:
    from desktop.candidates.list_model import CandidateListModel

    candidate = {"title": "Pool Show", "year": 2020}
    calls = []

    def fake_resolve(candidate_arg, data_language="ru"):
        calls.append((dict(candidate_arg), data_language))
        localized = candidate_arg.get("localized") if isinstance(candidate_arg.get("localized"), dict) else {}
        if localized.get("en", {}).get("poster_path") == "/en.jpg":
            return "en.jpg"
        return "ru.jpg"

    monkeypatch.setattr(
        "desktop.candidates.list_model.resolve_local_poster_path_for_candidate",
        fake_resolve,
    )
    model = CandidateListModel([candidate], data_language="en")

    assert model.poster_path_for_candidate(candidate) == "ru.jpg"

    candidate["localized"] = {"en": {"poster_path": "/en.jpg"}}
    model.update_poster_path("Pool Show", None)

    assert model.poster_path_for_candidate(candidate) == "en.jpg"
    assert [call[1] for call in calls] == ["en", "en"]


def test_candidate_selection_does_not_fetch_localized_poster_synchronously() -> None:
    import inspect

    from desktop.candidates.list_view import CandidateListView

    source = inspect.getsource(CandidateListView._on_result_selected)

    assert "ensure_candidate_localized_poster" not in source
    assert "_start_localized_poster_enrichment" in source


def test_candidate_list_view_starts_localized_poster_worker(monkeypatch) -> None:
    import desktop.candidates.list_view as list_view_module
    from desktop.candidates.list_view import CandidateListView

    candidate = {"title": "Pool Show", "year": 2020, "tmdb_id": 101}
    view = CandidateListView.__new__(CandidateListView)
    view._data_language = "en"
    view._widget = object()
    view._localized_poster_workers = []
    view._localized_poster_inflight = set()
    created = {}

    class FakeSignal:
        def __init__(self) -> None:
            self.callbacks = []

        def connect(self, callback) -> None:
            self.callbacks.append(callback)

    class FakeWorker:
        def __init__(self, identity, candidate_arg, data_language, parent=None) -> None:
            created["args"] = (identity, candidate_arg, data_language, parent)
            self.finished_with_candidate = FakeSignal()
            self.finished = FakeSignal()
            created["worker"] = self

        def start(self) -> None:
            created["started"] = True

        def deleteLater(self) -> None:
            created["deleted"] = True

    monkeypatch.setattr(list_view_module, "CandidateLocalizedPosterWorker", FakeWorker)

    view._start_localized_poster_enrichment(candidate, "Pool Show", 7)

    assert created["args"] == ("Pool Show", candidate, "en", view._widget)
    assert created["started"] is True
    assert view._localized_poster_workers == [created["worker"]]
    assert view._localized_poster_inflight == {"en:Pool Show"}
    assert len(created["worker"].finished_with_candidate.callbacks) == 1

    view._start_localized_poster_enrichment(candidate, "Pool Show", 8)

    assert view._localized_poster_workers == [created["worker"]]


def test_candidate_list_view_applies_localized_poster_worker_result(monkeypatch) -> None:
    from desktop.candidates.list_view import CandidateListView

    candidate = {"title": "Pool Show", "year": 2020, "tmdb_id": 101}
    updated_candidate = {
        **candidate,
        "localized": {
            "en": {
                "poster_url": "https://image.tmdb.org/t/p/original/en.jpg",
            }
        },
    }
    calls = {}

    class FakeModel:
        def update_poster_path(self, identity, path):
            calls["model"] = (identity, path)

    class FakeViewport:
        def update(self) -> None:
            calls["viewport"] = True

    class FakeResultsList:
        def viewport(self):
            return FakeViewport()

    view = CandidateListView.__new__(CandidateListView)
    view._data_language = "en"
    view._all_candidates = [candidate]
    view._candidates = [candidate]
    view._selected_identity = "Pool Show"
    view._selected_candidate = candidate
    view._poster_request_seq = 3
    view._detail_entries = {"Pool Show": ("old", {}, {})}
    view._model = FakeModel()
    view._results_list = FakeResultsList()
    view._show_detail_entry = lambda entry: calls.update({"entry": entry})
    view._start_poster_download = lambda url, identity, seq: calls.update(
        {"download": (url, identity, seq)}
    )
    monkeypatch.setattr(
        "desktop.candidates.list_view.candidate_poster_url_for_download",
        lambda candidate_arg, data_language="ru": candidate_arg["localized"][data_language]["poster_url"],
    )

    view._on_localized_poster_enriched(3, "Pool Show", updated_candidate, True)

    assert candidate["localized"]["en"]["poster_url"].endswith("/en.jpg")
    assert calls["model"] == ("Pool Show", None)
    assert calls["viewport"] is True
    assert calls["entry"][2]["poster_url"].endswith("/en.jpg")
    assert calls["download"] == ("https://image.tmdb.org/t/p/original/en.jpg", "Pool Show", 3)


def test_candidate_detail_entry_resets_detail_scroll() -> None:
    from desktop.candidates.list_view import CandidateListView

    class FakeScrollBar:
        def __init__(self) -> None:
            self.value = 120

        def minimum(self) -> int:
            return 0

        def setValue(self, value: int) -> None:
            self.value = value

    class FakeScrollArea:
        def __init__(self, bar: FakeScrollBar) -> None:
            self._bar = bar

        def verticalScrollBar(self) -> FakeScrollBar:
            return self._bar

    class FakeDetailCard:
        def __init__(self) -> None:
            self.shown = None

        def show_entry(self, entry) -> None:
            self.shown = entry

    entry = ("Candidate", {}, {"title": "Candidate"})
    bar = FakeScrollBar()
    detail = FakeDetailCard()
    view = CandidateListView.__new__(CandidateListView)
    view._detail_scroll = FakeScrollArea(bar)
    view._detail_card = detail

    view._show_detail_entry(entry)

    assert detail.shown == entry
    assert bar.value == 0


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
    import desktop.settings.app_settings  # noqa: F401 — preload before theme.shared imports
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
    import desktop.settings.app_settings  # noqa: F401 — preload before theme.shared imports
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


def test_filter_chip_selectors_do_not_show_local_reset_buttons(qapp) -> None:
    from PyQt6.QtWidgets import QPushButton

    from desktop.shared.widgets.country_chip_selector import CountryChipSelector
    from desktop.shared.widgets.genre_chip_selector import GenreChipSelector

    country_selector = CountryChipSelector([{"code": "RU", "label": "Россия"}])
    genre_selector = GenreChipSelector()

    assert country_selector.findChild(QPushButton, "countryChipClear") is None
    assert genre_selector.findChild(QPushButton, "genreChipClear") is None


def test_candidate_filter_sections_define_visual_hierarchy() -> None:
    from desktop.theme.scaling import font_px
    from desktop.theme.styles.candidates_shell import build_candidates_shell_style
    from desktop.theme.tokens import FONT_SECTION

    style = build_candidates_shell_style()

    assert "QFrame#candidateFilterSection" in style
    assert "QLabel#candidateFilterSectionTitle" in style
    assert "QFrame#candidateFilterDivider" in style
    assert f"font-size: {font_px(FONT_SECTION + 2)}px;" in style
    assert "QLabel#candidateSearchFieldLabel" in style
    assert f"font-size: {font_px(FONT_SECTION)}px;" in style
    assert "font-weight: 700;" in style


def test_candidate_list_search_matches_watched_search_scale() -> None:
    from desktop.theme.layout import INPUT_PADDING_X, INPUT_PADDING_Y
    from desktop.theme.scaling import font_px, layout_px
    from desktop.theme.styles.candidates_shell import build_candidates_shell_style
    from desktop.theme.styles.watched_shell import build_watched_shell_style
    from desktop.theme.tokens import FONT_SECTION

    candidate_style = build_candidates_shell_style()
    watched_style = build_watched_shell_style()
    expected_font = f"font-size: {font_px(FONT_SECTION)}px;"
    expected_padding = f"padding: {layout_px(INPUT_PADDING_Y + 1)}px {layout_px(INPUT_PADDING_X + 2)}px;"
    expected_min_height = f"min-height: {layout_px(34)}px;"

    assert "QLineEdit#candidateListSearch" in candidate_style
    assert "QLineEdit#watchedSearch" in watched_style
    assert expected_font in candidate_style
    assert expected_padding in candidate_style
    assert expected_min_height in candidate_style
    assert expected_font in watched_style
    assert expected_padding in watched_style
    assert expected_min_height in watched_style


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
    import desktop.settings.app_settings  # noqa: F401 — preload before theme.shared imports
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


def test_candidate_filters_view_before_apply_seam(monkeypatch, qapp) -> None:
    from desktop.candidates.filters_view import CandidateFiltersView
    from desktop.candidates.session import CandidateSearchSession

    class ServiceStub:
        def get_search_overview_view(self):
            return {
                "is_empty": False,
                "stats": {"unique_total": 1, "ready_total": 1, "incomplete_total": 0},
            }

        def get_search_filter_defaults_view(self):
            return {"defaults": {}}

        def get_search_filter_chip_options_view(self):
            return {"genres": [], "countries": []}

    captured = {}
    session = CandidateSearchSession(service=ServiceStub())
    view = CandidateFiltersView(
        session,
        service=session.service,
        on_before_apply=lambda filters: {**filters, "criteria_name": "seam"},
    )
    monkeypatch.setattr(
        session,
        "apply_filters_async",
        lambda filters, *, parent=None: captured.update({"filters": filters, "parent": parent}) or 1,
    )

    view._apply_filters()

    assert captured["filters"]["criteria_name"] == "seam"
    assert captured["parent"] is view.widget


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


def test_candidate_filters_form_uses_grouped_sections() -> None:
    import inspect

    import desktop.candidates.filters_form as form_module

    source = inspect.getsource(form_module.build_filters_form)

    assert "add_section" in source
    assert "add_divider" in source
    assert "candidateFilterSection" in source
    assert "candidateFilterDivider" in source
    assert 'tr("candidates.filters.basic")' in source
    assert 'tr("candidates.filters.genres")' in source
    assert 'tr("candidates.filters.tmdb")' in source
    assert 'tr("candidates.filters.visibility")' in source


def test_candidate_filters_view_places_apply_button_in_top_bar() -> None:
    import inspect

    import desktop.candidates.filters_view as module

    source = inspect.getsource(module.CandidateFiltersView.__init__)
    assert "top_bar" in source
    assert "_update_apply_button_width" in source
    assert "control_px(40)" in inspect.getsource(module)
    assert "form.addWidget(self._apply_button)" not in source


def test_watched_window_includes_candidate_tabs() -> None:
    import inspect

    import desktop.shell.main_window as app_module
    import desktop.shell.tabs as tabs_module

    init_source = inspect.getsource(app_module.WatchedMoviesWindow.__init__)
    factory_source = inspect.getsource(tabs_module.build_main_tabs)
    assert "build_main_tabs" in init_source
    assert "WatchedTabView" in factory_source
    assert "AnalyticsView" not in factory_source
    assert "CandidateFiltersView" in factory_source
    assert "CandidateListView" in factory_source
    assert "SettingsTabView" in factory_source
    assert "load_desktop_language_context" in factory_source
    assert 'languages.tr("tabs.filters")' in factory_source
    assert 'languages.tr("tabs.candidates")' in factory_source
    assert 'languages.tr("tabs.watched")' in factory_source
    assert 'languages.tr("tabs.settings")' in factory_source
    assert '"Информация"' not in factory_source
    assert '"Watched"' not in factory_source
    assert '"Analytics"' not in factory_source
    assert '"Search"' not in factory_source
    assert "MainTabRegistry" in factory_source
    assert "ShellTabSpec" in factory_source
    assert "_tab_registry.register" not in init_source
    assert "registry.register" in factory_source
    assert "registry.focus" in factory_source


def test_build_main_tabs_registers_active_shell_tabs(monkeypatch, qapp) -> None:
    from PyQt6.QtWidgets import QTabWidget, QWidget

    from desktop.settings.app_settings import AppSettings
    import desktop.i18n.translator as translator_module
    import desktop.shell.tabs as tabs_module

    class FakeWatchedTabView:
        def __init__(
            self,
            *,
            parent=None,
            on_status_message=None,
            on_entries_changed=None,
        ) -> None:
            self.widget = QWidget(parent)
            self.entries = [("Alpha", {"main_info": {"title": "Alpha"}}, {"title": "Alpha"})]
            self._on_entries_changed = on_entries_changed

        def reload_entries(self, added_key: str | None = None) -> None:
            return None

    class FakeCandidateSearchSession:
        pass

    class FakeCandidateListView:
        def __init__(self, *args, **kwargs) -> None:
            self.widget = QWidget()
            self.activation_count = 0

        def on_tab_activated(self) -> None:
            self.activation_count += 1

    class FakeSimpleTabView:
        def __init__(self, *args, **kwargs) -> None:
            self.widget = QWidget()

    monkeypatch.setattr(tabs_module, "WatchedTabView", FakeWatchedTabView)
    monkeypatch.setattr(tabs_module, "CandidateSearchSession", FakeCandidateSearchSession)
    monkeypatch.setattr(tabs_module, "CandidateFiltersView", FakeSimpleTabView)
    monkeypatch.setattr(tabs_module, "CandidateListView", FakeCandidateListView)
    monkeypatch.setattr(tabs_module, "SettingsTabView", FakeSimpleTabView)
    monkeypatch.setattr(
        translator_module,
        "load_app_settings",
        lambda: AppSettings(interface_language="ru", data_language="ru"),
    )

    tabs = QTabWidget()
    parent = QWidget()
    registry, context = tabs_module.build_main_tabs(
        tabs,
        parent,
        on_status_message=lambda _message, _timeout_ms: None,
    )

    assert tabs.count() == 4
    assert [tabs.tabText(index) for index in range(tabs.count())] == [
        "Моё",
        "Фильтры",
        "Кандидаты",
        "Настройки",
    ]
    assert hasattr(context, "analytics_tab_view") is False
    assert len(registry._specs) == 4
    assert len(registry._specs) == len(set(registry._specs))
    assert set(registry._specs) == {"watched", "filters", "candidates", "settings"}
    assert all(hasattr(spec.view, "widget") for spec in registry._specs.values())

    for index in range(tabs.count()):
        registry.on_current_changed(index)

    assert registry._specs["candidates"].view.activation_count == 1


def test_build_main_tabs_uses_english_interface_language(monkeypatch, qapp) -> None:
    from PyQt6.QtWidgets import QTabWidget, QWidget

    from desktop.language_context import DesktopLanguageContext
    import desktop.shell.tabs as tabs_module

    class FakeWatchedTabView:
        def __init__(self, *args, **kwargs) -> None:
            self.widget = QWidget()
            self.entries = []

        def reload_entries(self, added_key: str | None = None) -> None:
            return None

    class FakeCandidateSearchSession:
        pass

    class FakeSimpleTabView:
        def __init__(self, *args, **kwargs) -> None:
            self.widget = QWidget()

    monkeypatch.setattr(tabs_module, "WatchedTabView", FakeWatchedTabView)
    monkeypatch.setattr(tabs_module, "CandidateSearchSession", FakeCandidateSearchSession)
    monkeypatch.setattr(tabs_module, "CandidateFiltersView", FakeSimpleTabView)
    monkeypatch.setattr(tabs_module, "CandidateListView", FakeSimpleTabView)
    monkeypatch.setattr(tabs_module, "SettingsTabView", FakeSimpleTabView)
    tabs = QTabWidget()
    registry, _context = tabs_module.build_main_tabs(
        tabs,
        QWidget(),
        on_status_message=lambda _message, _timeout_ms: None,
        language_context=DesktopLanguageContext(
            interface_language="en",
            data_language="ru",
            tmdb_locale="ru-RU",
        ),
    )

    assert [tabs.tabText(index) for index in range(tabs.count())] == [
        "My library",
        "Filters",
        "Candidates",
        "Settings",
    ]
    assert set(registry._specs) == {"watched", "filters", "candidates", "settings"}


def test_cross_tab_wiring_stays_in_shell_tabs() -> None:
    shell_tabs_path = Path("desktop/shell/tabs.py")
    shell_source = shell_tabs_path.read_text(encoding="utf-8")

    assert "ShellTabSpec(" in shell_source
    assert "on_candidate_moved_to_watched" in shell_source
    assert "watched_tab_view.reload_entries" in shell_source
    assert "on_watched_added=on_candidate_moved_to_watched" in shell_source
    assert "on_applied=lambda: registry.focus(\"candidates\")" in shell_source

    forbidden_snippets = {
        "ShellTabSpec(",
        "registry.focus(",
        "watched_tab_view.reload_entries",
        "on_watched_added=",
        "on_entries_changed=",
    }
    forbidden_tab_imports = {
        "from desktop.watched.tab import WatchedTabView": "desktop/watched/",
        "from desktop.candidates.filters_view import CandidateFiltersView": "desktop/candidates/",
        "from desktop.candidates.list_view import CandidateListView": "desktop/candidates/",
        "from desktop.settings.tab_view import SettingsTabView": "desktop/settings/",
    }
    findings = set()

    for path in Path("desktop").rglob("*.py"):
        normalized_path = path.as_posix()
        if normalized_path == shell_tabs_path.as_posix():
            continue
        source = path.read_text(encoding="utf-8")
        for snippet in forbidden_snippets:
            if snippet in source:
                findings.add((normalized_path, snippet))
        for snippet, allowed_prefix in forbidden_tab_imports.items():
            if snippet in source and not normalized_path.startswith(allowed_prefix):
                findings.add((normalized_path, snippet))

    assert findings == set()


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


def test_candidate_search_text_includes_both_localized_titles() -> None:
    from desktop.candidates.presenters import candidate_search_text, filter_candidates_by_title

    candidate = {
        "title": "Better Call Saul",
        "localized": {
            "ru": {"title": "Лучше звоните Солу"},
            "en": {"title": "Better Call Saul"},
        },
        "original_title": "Better Call Saul",
    }

    haystack = candidate_search_text(candidate)

    assert "лучше звоните солу" in haystack
    assert "better call saul" in haystack
    assert filter_candidates_by_title([candidate], "лучше") == [candidate]


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


def test_watched_search_haystack_includes_localized_titles() -> None:
    from desktop.watched.model.load import watched_entry_search_haystack

    entry = (
        "better-call-saul",
        {
            "main_info": {"title": "Лучше звоните Солу"},
            "localized": {
                "ru": {"title": "Лучше звоните Солу"},
                "en": {"title": "Better Call Saul"},
            },
            "original_title": "Better Call Saul",
        },
        {"title": "Better Call Saul"},
    )

    haystack = watched_entry_search_haystack(entry)

    assert "лучше звоните солу" in haystack
    assert "better call saul" in haystack


def test_watched_tab_reload_entries_rereads_data_language(monkeypatch, qapp) -> None:
    from desktop.settings.app_settings import AppSettings, save_app_settings
    from desktop.watched.tab import WatchedTabView

    calls = []

    def fake_load_watched_entries(*, data_language="ru"):
        calls.append(data_language)
        return [
            (
                data_language,
                {"main_info": {"title": data_language, "year": 2020, "user_score": 8.0}},
                {"title": data_language, "year": 2020, "user_score": 8.0},
            )
        ]

    monkeypatch.setattr("desktop.watched.tab.load_watched_entries", fake_load_watched_entries)
    save_app_settings(AppSettings(interface_language="ru", data_language="ru"))

    view = WatchedTabView(on_status_message=lambda _message, _timeout_ms=0: None)
    assert calls[-1] == "ru"

    save_app_settings(AppSettings(interface_language="ru", data_language="en"))
    view.reload_entries()

    assert calls[-1] == "en"


def test_watched_tab_selection_resets_detail_scroll() -> None:
    from desktop.watched.tab import WatchedTabView

    class FakeScrollBar:
        def __init__(self) -> None:
            self.value = 80

        def minimum(self) -> int:
            return 0

        def setValue(self, value: int) -> None:
            self.value = value

    class FakeScrollArea:
        def __init__(self, bar: FakeScrollBar) -> None:
            self._bar = bar

        def verticalScrollBar(self) -> FakeScrollBar:
            return self._bar

    class FakeDetailCard:
        def __init__(self) -> None:
            self.shown = None

        def show_entry(self, entry) -> None:
            self.shown = entry

    entries = [
        ("Alpha", {}, {"title": "Alpha"}),
        ("Bravo", {}, {"title": "Bravo"}),
    ]
    bar = FakeScrollBar()
    detail = FakeDetailCard()
    view = WatchedTabView.__new__(WatchedTabView)
    view._visible_entries = entries
    view._detail_scroll = FakeScrollArea(bar)
    view._detail_card = detail
    view._entry_with_current_language_poster = lambda row: view._visible_entries[row]

    view._on_selection_changed(1)

    assert detail.shown == entries[1]
    assert bar.value == 0


def test_watched_tab_selection_lazily_syncs_current_language_poster(monkeypatch) -> None:
    from desktop.watched.tab import WatchedTabView

    movie = {"main_info": {"title": "Naruto", "year": 2002, "user_score": 8.5}}
    item_data = {}

    class FakeItem:
        def setData(self, role, value):
            item_data["data"] = (role, value)

        def setToolTip(self, value):
            item_data["tooltip"] = value

    class FakeListWidget:
        def count(self):
            return 1

        def item(self, row):
            return FakeItem() if row == 0 else None

        def viewport(self):
            return self

        def update(self):
            item_data["updated"] = True

    view = WatchedTabView.__new__(WatchedTabView)
    view._data_language = "en"
    view._visible_entries = [("Naruto", movie, {"title": "Naruto", "poster_src": "ru.jpg"})]
    view._entries = list(view._visible_entries)
    view._list_widget = FakeListWidget()
    calls = {}

    def fake_sync(movie_arg, *, data_language="ru"):
        calls["sync"] = (movie_arg, data_language)
        return {"updated": True}

    def fake_prepare(movie_arg, *, data_language="ru"):
        calls["prepare"] = (movie_arg, data_language)
        return {"title": "Naruto", "poster_src": "en.jpg"}

    monkeypatch.setattr("desktop.watched.tab.sync_poster_for_display", fake_sync)
    monkeypatch.setattr("desktop.watched.tab.prepare_card_for_display", fake_prepare)

    updated = view._entry_with_current_language_poster(0)

    assert calls["sync"] == (movie, "en")
    assert calls["prepare"] == (movie, "en")
    assert updated[2]["poster_src"] == "en.jpg"
    assert view._visible_entries[0] == updated
    assert view._entries[0] == updated
    assert item_data["data"][1] == updated
    assert item_data["updated"] is True


def test_watched_tab_selection_clears_replaced_poster_pixmap_cache(monkeypatch) -> None:
    from desktop.watched.tab import WatchedTabView

    movie = {"main_info": {"title": "Naruto", "year": 2002, "user_score": 8.5}}

    class FakeItem:
        def setData(self, _role, _value):
            pass

        def setToolTip(self, _value):
            pass

    class FakeListWidget:
        def count(self):
            return 1

        def item(self, row):
            return FakeItem() if row == 0 else None

        def viewport(self):
            return self

        def update(self):
            pass

    view = WatchedTabView.__new__(WatchedTabView)
    view._data_language = "en"
    view._visible_entries = [("Naruto", movie, {"title": "Naruto", "poster_src": "ru.jpg"})]
    view._entries = list(view._visible_entries)
    view._list_widget = FakeListWidget()
    cleared = []

    monkeypatch.setattr(
        "desktop.watched.tab.sync_poster_for_display",
        lambda movie_arg, *, data_language="ru": {
            "updated": True,
            "download": {"local_path": "poster.jpg"},
            "entry": {"local_path": "poster.jpg"},
        },
    )
    monkeypatch.setattr(
        "desktop.watched.tab.prepare_card_for_display",
        lambda movie_arg, *, data_language="ru": {"title": "Naruto", "poster_src": "poster.jpg"},
    )
    monkeypatch.setattr(
        "desktop.watched.tab.clear_detail_poster_source_cache",
        lambda path=None: cleared.append(("detail", path)),
    )
    monkeypatch.setattr(
        "desktop.watched.tab.clear_list_thumb_pixmap_cache",
        lambda path=None: cleared.append(("list", path)),
    )

    view._entry_with_current_language_poster(0)

    assert ("detail", "poster.jpg") in cleared
    assert ("list", "poster.jpg") in cleared


def test_poster_pixmap_cache_clear_helpers() -> None:
    from desktop.shared.detail import card_poster, list_delegate

    card_poster._detail_poster_source_cache["poster.jpg"] = object()
    list_delegate._thumb_pixmap_cache["poster.jpg"] = object()

    card_poster.clear_detail_poster_source_cache("poster.jpg")
    list_delegate.clear_list_thumb_pixmap_cache("poster.jpg")

    assert "poster.jpg" not in card_poster._detail_poster_source_cache
    assert "poster.jpg" not in list_delegate._thumb_pixmap_cache


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

    import desktop.candidates.list_actions as actions_module
    import desktop.candidates.list_view as module

    view_source = inspect.getsource(module.CandidateListView)
    actions_source = inspect.getsource(actions_module.CandidateListActionsMixin)
    assert "CandidateListActionsMixin" in view_source
    assert "set_mark_watched_handler" in view_source
    assert "run_candidate_transfer_flow" not in view_source
    assert "run_candidate_transfer_flow" in actions_source
    assert "on_watched_added" in actions_source
    assert "reload_from_pool(force=True)" in actions_source


def test_candidate_list_actions_transfer_refreshes_pool_and_notifies(monkeypatch, qapp) -> None:
    from types import SimpleNamespace

    from PyQt6.QtWidgets import QWidget

    from desktop.candidates.list_actions import CandidateListActionsMixin

    class FakeSession:
        filters = {"only_unwatched": True}

        def __init__(self) -> None:
            self.reload_calls: list[bool] = []

        def reload_from_pool(self, *, force: bool = False) -> None:
            self.reload_calls.append(force)

    class FakeView(CandidateListActionsMixin):
        pass

    candidate = {"title": "Alpha"}
    result = SimpleNamespace(ok=True)
    added_results = []
    session = FakeSession()
    view = FakeView()
    view._selected_candidate = candidate
    view._session = session
    view._on_watched_added = added_results.append
    view._widget = QWidget()

    monkeypatch.setattr(
        "desktop.watched.add_title.run_candidate_transfer_flow",
        lambda parent, selected_candidate: result if selected_candidate is candidate else None,
    )

    view._transfer_selected_to_watched()

    assert view._selected_candidate is None
    assert session.reload_calls == [True]
    assert added_results == [result]


def test_candidate_list_view_starts_async_poster_download() -> None:
    import inspect

    import desktop.candidates.list_actions as actions_module
    import desktop.candidates.list_view as module

    view_source = inspect.getsource(module.CandidateListView)
    actions_source = inspect.getsource(actions_module.CandidateListActionsMixin)
    assert "CandidatePosterDownloadWorker" not in view_source
    assert "candidate_poster_url_for_download" in view_source
    assert "_start_poster_download" in view_source
    assert "CandidatePosterDownloadWorker" in actions_source
    assert "apply_local_poster_path" in actions_source


def test_candidate_session_reload_from_pool_reapplies_filters() -> None:
    import inspect

    import desktop.candidates.session as session_module

    source = inspect.getsource(session_module.CandidateSearchSession.reload_from_pool)
    assert "apply_filters" in source
    assert "_notify_listeners" in source

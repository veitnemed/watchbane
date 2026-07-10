"""Tests for TMDb-only add-title resolve orchestration."""

from config import scheme
from dataset.add_flow.bundle import build_add_title_resolve_bundle
from dataset.resolve import service as resolve_service


def _tmdb_details() -> dict:
    return {
        "id": 123,
        "name": "TMDb Show",
        "original_name": "TMDb Show",
        "first_air_date": "2024-01-01",
        "origin_country": ["RU"],
        "production_countries": [{"iso_3166_1": "RU", "name": "Россия"}],
        "genres": [{"id": 18, "name": "Drama"}],
        "vote_average": 7.8,
        "vote_count": 456,
        "popularity": 12.3,
        "overview": "TMDb overview",
        "poster_path": "/poster.jpg",
        "external_ids": {"imdb_id": "tt123"},
    }


def test_resolve_title_data_for_add_tmdb_search_details_returns_defaults() -> None:
    details_calls = []

    def fake_details(tmdb_id, **kwargs):
        details_calls.append((tmdb_id, kwargs))
        return _tmdb_details()

    result = resolve_service.resolve_title_data_for_add(
        "Input Title",
        "Россия",
        tmdb_search_func=lambda title: [{"id": 123, "name": title}],
        tmdb_choose_func=lambda results: results[0],
        tmdb_details_func=fake_details,
    )

    assert result["found"] is True
    assert result["statuses"] == {"tmdb_api": "найдено"}
    assert result["tmdb_data"]["tmdb_id"] == 123
    assert result["tmdb_data"]["imdb_id"] == "tt123"
    assert result["defaults"][scheme.MAIN_INFO]["title"] == "TMDb Show"
    assert result["defaults"][scheme.MAIN_INFO]["year"] == 2024
    assert result["defaults"][scheme.RAW_SCORES] == {
        "tmdb_score": 7.8,
        "tmdb_votes": 456,
        "tmdb_popularity": 12.3,
    }
    assert details_calls[0][1]["append_to_response"] == resolve_service.api_tmdb.DEFAULT_TV_DETAIL_APPENDS


def test_resolve_title_data_for_add_movie_returns_movie_defaults() -> None:
    details_calls = []

    def fake_details(tmdb_id, **kwargs):
        details_calls.append((tmdb_id, kwargs))
        return {
            "id": tmdb_id,
            "title": "Watchmen",
            "original_title": "Watchmen",
            "release_date": "2009-03-06",
            "production_countries": [{"iso_3166_1": "US", "name": "United States"}],
            "genres": [{"id": 18, "name": "Drama"}],
            "vote_average": 7.3,
            "vote_count": 9000,
            "popularity": 55.5,
            "overview": "Movie overview",
            "external_ids": {"imdb_id": "tt0409459"},
        }

    result = resolve_service.resolve_title_data_for_add(
        "Watchmen",
        "US",
        media_type="movie",
        tmdb_search_func=lambda title: [{"id": 202, "title": title, "release_date": "2009-03-06"}],
        tmdb_choose_func=lambda results: results[0],
        tmdb_details_func=fake_details,
    )

    assert result["found"] is True
    assert result["media_type"] == "movie"
    assert result["tmdb_data"]["media_type"] == "movie"
    assert result["defaults"][scheme.MAIN_INFO]["title"] == "Watchmen"
    assert result["defaults"][scheme.MAIN_INFO]["year"] == 2009
    assert result["defaults"][scheme.MAIN_INFO]["media_type"] == "movie"
    assert result["defaults"][scheme.RAW_SCORES] == {
        "tmdb_score": 7.3,
        "tmdb_votes": 9000,
        "tmdb_popularity": 55.5,
    }
    assert details_calls[0][1]["append_to_response"] == resolve_service.api_tmdb.DEFAULT_MOVIE_DETAIL_APPENDS


def test_resolve_title_data_for_add_not_found_and_manual_bundle_defaults() -> None:
    result = resolve_service.resolve_title_data_for_add(
        "Missing",
        "RU",
        tmdb_search_func=lambda title: [],
        tmdb_choose_func=lambda results: None,
    )
    bundle = build_add_title_resolve_bundle(result)

    assert result["found"] is False
    assert result["defaults"] is None
    assert result["statuses"] == {"tmdb_api": "не найдено"}
    assert bundle.defaults[scheme.MAIN_INFO]["title"] == "Missing"
    assert bundle.defaults[scheme.RAW_SCORES] == {}


def test_resolve_title_data_for_add_result_has_no_sql_kp_contract_fields() -> None:
    result = resolve_service.resolve_title_data_for_add(
        "Input Title",
        "RU",
        tmdb_search_func=lambda title: [{"id": 123}],
        tmdb_choose_func=lambda results: results[0],
        tmdb_details_func=lambda tmdb_id, **kwargs: _tmdb_details(),
    )

    forbidden_result_keys = {
        "sql_result",
        "sql_data",
        "sql_merge_data",
        "sql_merge_source",
        "sql_second_pass_result",
        "api_data",
        "api_error",
    }
    forbidden_tmdb_keys = {
        "kp_id",
        "kp_score",
        "kp_votes",
        "kp_rating",
        "kp_status",
        "imdb_score",
        "imdb_rating",
        "imdb_votes",
        "imdb_genres",
        "imdb_start_year",
    }

    assert forbidden_result_keys.isdisjoint(result)
    assert "kp_api" not in result["statuses"]
    assert "sql" not in result["statuses"]
    assert forbidden_tmdb_keys.isdisjoint(result["tmdb_data"])
    assert "imdb_id" in result["tmdb_data"]


def test_resolve_title_data_for_add_does_not_call_kp_or_imdb_modules(monkeypatch) -> None:
    import importlib

    apis_package = importlib.import_module("apis")
    assert not hasattr(apis_package, "kp_api")
    assert not hasattr(apis_package, "imdb_sql")

    result = resolve_service.resolve_title_data_for_add(
        "Input Title",
        "RU",
        tmdb_search_func=lambda title: [{"id": 123}],
        tmdb_choose_func=lambda results: results[0],
        tmdb_details_func=lambda tmdb_id, **kwargs: _tmdb_details(),
    )

    assert result["found"] is True


def test_resolve_title_data_for_add_reports_four_tmdb_progress_steps() -> None:
    progress_messages = []

    resolve_service.resolve_title_data_for_add(
        "Input Title",
        "RU",
        on_progress=lambda step, total, message: progress_messages.append((step, total, message)),
        tmdb_search_func=lambda title: [{"id": 123}],
        tmdb_choose_func=lambda results: results[0],
        tmdb_details_func=lambda tmdb_id, **kwargs: _tmdb_details(),
    )

    assert progress_messages == [
        (1, 4, "TMDb Search: Поиск"),
        (2, 4, "TMDb Details: Успешно"),
        (3, 4, "Подготовка defaults: TMDb"),
        (4, 4, "Готово: найдено"),
    ]

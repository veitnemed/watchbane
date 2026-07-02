import inspect

from dataset.resolve import sources


def _details(**overrides) -> dict:
    payload = {
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
    payload.update(overrides)
    return payload


def test_search_tmdb_defaults_data_found() -> None:
    details_calls = []

    def fake_details(tmdb_id, **kwargs):
        details_calls.append((tmdb_id, kwargs))
        return _details()

    result = sources.search_tmdb_defaults_data(
        [{"title": "TMDb Show", "year": 2024, "country": "Россия"}],
        search_func=lambda title: [
            {"id": 1, "name": "Other", "first_air_date": "2024-01-01", "origin_country": ["US"]},
            {"id": 123, "name": title, "first_air_date": "2024-01-01", "origin_country": ["RU"]},
        ],
        details_func=fake_details,
    )

    assert result["status"] == "найдено"
    assert result["error"] is None
    assert result["data"]["tmdb_id"] == 123
    assert result["data"]["title"] == "TMDb Show"
    assert result["data"]["tmdb_score"] == 7.8
    assert result["data"]["tmdb_votes"] == 456
    assert result["data"]["tmdb_popularity"] == 12.3
    assert result["data"]["genres_tmdb"] == ["Drama"]
    assert result["data"]["imdb_id"] == "tt123"
    assert "kp_score" not in result["data"]
    assert "imdb_score" not in result["data"]
    assert details_calls[0][0] == 123
    assert details_calls[0][1]["append_to_response"] == sources.api_tmdb.DEFAULT_TV_DETAIL_APPENDS


def test_search_tmdb_defaults_data_not_found() -> None:
    result = sources.search_tmdb_defaults_data(
        ["Missing"],
        search_func=lambda title: [],
    )

    assert result == {
        "data": None,
        "error": {"ok": False, "error": "not_found", "details": "TMDb не нашёл объект: Missing"},
        "status": "не найдено",
    }


def test_search_tmdb_defaults_data_network_error() -> None:
    def broken_search(_title):
        raise RuntimeError("network down")

    result = sources.search_tmdb_defaults_data(["Show"], search_func=broken_search)

    assert result["data"] is None
    assert result["status"] == "ошибка"
    assert result["error"]["error"] == "network_error"
    assert "network down" in result["error"]["details"]


def test_resolve_sources_has_no_kp_imports_or_legacy_tmdb_normalizer() -> None:
    source_text = inspect.getsource(sources)

    assert "kp_api" not in source_text
    assert "find_series_raw" not in source_text
    assert "format_series_lines" not in source_text
    assert "normalize_tmdb_tv" not in source_text

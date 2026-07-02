import inspect

from config import constant
from config import scheme


FORBIDDEN_RATING_FIELDS = {"kp_score", "kp_votes", "imdb_score", "imdb_votes"}


def _tmdb_details(tmdb_id: int = 123, title: str = "Show") -> dict:
    return {
        "id": tmdb_id,
        "name": title,
        "original_name": title,
        "first_air_date": "2020-01-01",
        "origin_country": ["RU"],
        "production_countries": [{"iso_3166_1": "RU", "name": "Россия"}],
        "original_language": "ru",
        "genres": [{"id": 18, "name": "Drama"}],
        "vote_average": 7.8,
        "vote_count": 456,
        "popularity": 12.3,
        "overview": "TMDb overview",
        "external_ids": {"imdb_id": "tt123"},
        "aggregate_credits": {},
        "keywords": {"results": []},
    }


def test_candidate_build_public_flow_has_no_kp_imdb_imports_or_rating_fields(monkeypatch) -> None:
    from candidates.sources.tmdb import builder

    source = inspect.getsource(builder)
    assert "apis.imdb_sql" not in source
    assert "candidates.sources.kp" not in source
    assert "retry_kp_enrichment" not in source

    monkeypatch.setattr(builder.api_tmdb, "load_tmdb_token", lambda: "token")
    monkeypatch.setattr(
        builder,
        "build_discovery_slices",
        lambda *args, **kwargs: [{"slice_name": "test", "query": {"sort_by": "vote_count.desc"}, "pages_per_slice": 1}],
    )
    monkeypatch.setattr(builder, "load_candidate_pool", lambda: {})
    monkeypatch.setattr(builder, "remove_watched_discover", lambda items: (list(items), 0))
    monkeypatch.setattr(
        builder.api_tmdb,
        "tmdb_get",
        lambda *args, **kwargs: {
            "page": 1,
            "total_pages": 1,
            "results": [{
                "id": 123,
                "name": "Show",
                "original_name": "Show",
                "first_air_date": "2020-01-01",
                "vote_average": 7.8,
                "vote_count": 456,
                "popularity": 12.3,
            }],
        },
    )
    monkeypatch.setattr(builder.api_tmdb, "get_tv_details", lambda tmdb_id, **kwargs: _tmdb_details(tmdb_id))

    result = builder.build_candidate_pool("RU", pages=1, details_limit=1)

    assert result["candidates"]
    assert FORBIDDEN_RATING_FIELDS.isdisjoint(result["candidates"][0])


def test_add_title_public_flow_uses_only_tmdb(monkeypatch) -> None:
    from apis import imdb_sql, kp_api
    from dataset.resolve import service as resolve_service

    monkeypatch.setattr(
        imdb_sql,
        "search_title_in_sql",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("IMDb SQL must not be called")),
    )
    monkeypatch.setattr(
        kp_api,
        "find_series_raw",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("KP API must not be called")),
    )

    result = resolve_service.resolve_title_data_for_add(
        "Show",
        "Россия",
        tmdb_search_func=lambda title: [{"id": 123, "name": title, "first_air_date": "2020-01-01"}],
        tmdb_choose_func=lambda results: results[0],
        tmdb_details_func=lambda tmdb_id, **kwargs: _tmdb_details(tmdb_id),
    )

    assert result["statuses"] == {"tmdb_api": "найдено"}
    assert "sql" not in result["statuses"]
    assert "kp_api" not in result["statuses"]
    assert set(result["defaults"][scheme.RAW_SCORES]) == {"tmdb_score", "tmdb_votes", "tmdb_popularity"}
    assert FORBIDDEN_RATING_FIELDS.isdisjoint(result["defaults"][scheme.RAW_SCORES])


def test_console_public_flow_import_and_copy_are_tmdb_only(monkeypatch, capsys) -> None:
    import start_console  # noqa: F401
    from ui.console import request

    request.print_autofill_status(
        {
            "title": "Show",
            "defaults": {scheme.RAW_SCORES: {"tmdb_score": 7.8, "tmdb_votes": 456, "tmdb_popularity": 12.3}},
            "sources": {"tmdb_score": "tmdb_api", "tmdb_votes": "tmdb_api", "tmdb_popularity": "tmdb_api"},
            "source_values": {"genres": ["Drama"], "description": "Overview"},
            "statuses": {"tmdb_api": "найдено"},
        },
        manual_mode=False,
    )
    output = capsys.readouterr().out
    assert "SQL" not in output
    assert "KP" not in output
    assert "IMDb" not in output

    monkeypatch.setattr(request, "loop_input_with_default", lambda *args, **kwargs: "8.0")
    monkeypatch.setattr(request.service, "build_movie_record_from_defaults", lambda defaults, score: {"score": score})
    request.request_user_score({scheme.MAIN_INFO: {"title": "Show", "year": 2020, "user_score": 8.0}})
    output = capsys.readouterr().out
    assert "TMDb-метаданные" in output
    assert "рейтинги" not in output


def test_dataset_schema_active_raw_scores_are_tmdb_only() -> None:
    assert scheme.get_fields(scheme.RAW_SCORES) == ["tmdb_score", "tmdb_votes", "tmdb_popularity"]
    assert constant.FIELD_LABELS["tmdb_score"] == "Рейтинг TMDb"
    assert constant.FIELD_LABELS["tmdb_votes"] == "Голоса TMDb"
    assert constant.FIELD_LABELS["tmdb_popularity"] == "Популярность TMDb"
    assert {
        "kp_score",
        "imdb_score",
        "kp_popularity",
        "imdb_popularity",
    }.isdisjoint(constant.FEATURES)


def test_candidate_transfer_to_watched_uses_tmdb_raw_scores_only() -> None:
    from dataset.transfer.candidate import build_candidate_transfer_payload

    payload = build_candidate_transfer_payload({
        "title": "Show",
        "year": 2020,
        "tmdb_score": 7.8,
        "tmdb_votes": 456,
        "tmdb_popularity": 12.3,
        "kp_score": 9.9,
        "kp_votes": 1000,
        "imdb_score": 8.8,
        "imdb_votes": 2000,
    })

    assert payload["defaults"][scheme.RAW_SCORES] == {
        "tmdb_score": 7.8,
        "tmdb_votes": 456,
        "tmdb_popularity": 12.3,
    }
    assert FORBIDDEN_RATING_FIELDS.isdisjoint(payload["defaults"][scheme.RAW_SCORES])

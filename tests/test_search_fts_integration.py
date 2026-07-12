from __future__ import annotations

import pytest

from candidates import service as candidate_service
from storage.sqlite import candidate_repository


def _candidate(**overrides):
    base = {
        "title": "Бригада",
        "year": 2002,
        "countries": ["Россия"],
        "country_codes": ["RU"],
        "genres_tmdb": ["Crime", "Drama"],
        "genre_keys": ["crime", "drama"],
        "localized": {"ru": {"overview": "Криминальная драма о банде."}},
        "final_score": 8.0,
        "is_complete": True,
    }
    base.update(overrides)
    return base


@pytest.fixture
def fts_pool(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    monkeypatch.setattr("config.constant.APP_DATA_DIR", str(data_dir))
    monkeypatch.setattr("storage.data.load_dataset", lambda: {})
    db_path = data_dir / "watchbane.sqlite3"
    pool = {
        "brigada|2002": _candidate(),
        "comedy|2010": _candidate(
            title="Одноклассники",
            year=2010,
            genres_tmdb=["Comedy"],
            genre_keys=["comedy"],
            localized={"ru": {"overview": "Комедия про выпускников."}},
            final_score=5.0,
        ),
    }
    candidate_repository.save_candidate_pool_dict(pool, path=db_path)
    return list(pool.values())


def test_empty_query_uses_legacy_filter_path(fts_pool, monkeypatch) -> None:
    monkeypatch.setenv(candidate_service.FTS_SEARCH_ENV, "1")
    result = candidate_service.search_candidate_pool_text(
        fts_pool,
        {},
        text_query="",
    )
    assert result.get("fts_enabled") is not True
    assert len(result["candidates"]) == 2


def test_fts_disabled_keeps_legacy_behavior(fts_pool, monkeypatch) -> None:
    monkeypatch.setenv(candidate_service.FTS_SEARCH_ENV, "0")
    result = candidate_service.search_candidate_pool_text(
        fts_pool,
        {},
        text_query="бригада",
    )
    assert result.get("fts_enabled") is not True
    assert len(result["candidates"]) == 2


def test_fts_query_filters_by_text_and_country(fts_pool, monkeypatch) -> None:
    monkeypatch.setenv(candidate_service.FTS_SEARCH_ENV, "1")
    result = candidate_service.search_candidate_pool_text(
        fts_pool,
        {"country": ["RU"]},
        text_query="криминал",
    )
    assert result.get("fts_enabled") is True
    assert len(result["candidates"]) == 1
    assert result["candidates"][0]["title"] == "Бригада"
    assert result["candidates"][0].get("text_relevance_score") is not None
    assert result["candidates"][0].get("matched_fields")


def test_fts_enabled_from_persisted_setting(fts_pool, monkeypatch, tmp_path) -> None:
    from config import app_settings_store, constant

    data_dir = tmp_path / "data"
    monkeypatch.setattr(constant, "APP_DATA_DIR", str(data_dir))
    monkeypatch.delenv(candidate_service.FTS_SEARCH_ENV, raising=False)
    app_settings_store.save_sqlite_settings_dict({"fts_search_enabled": True})

    result = candidate_service.search_candidate_pool_text(
        fts_pool,
        {},
        text_query="бригада",
    )
    assert result.get("fts_enabled") is True
    assert len(result["candidates"]) == 1


def test_fts_disabled_from_persisted_setting_uses_legacy_path(fts_pool, monkeypatch) -> None:
    from config import app_settings_store

    monkeypatch.delenv(candidate_service.FTS_SEARCH_ENV, raising=False)
    app_settings_store.save_sqlite_settings_dict({"fts_search_enabled": False})

    result = candidate_service.search_candidate_pool_text(
        fts_pool,
        {},
        text_query="бригада",
    )

    assert candidate_service.is_fts_search_enabled() is False
    assert result.get("fts_enabled") is not True
    assert len(result["candidates"]) == 2


def test_relevance_sort_mode_orders_by_combined_score(fts_pool, monkeypatch) -> None:
    monkeypatch.setenv(candidate_service.FTS_SEARCH_ENV, "1")
    search_view = candidate_service.search_candidate_pool_text(fts_pool, {}, text_query="бригада")
    sort_view = candidate_service.sort_search_candidates(
        search_view["candidates"],
        "relevance",
    )
    titles = [item["title"] for item in sort_view["candidates"]]
    assert titles == ["Бригада"]


def test_calibrated_rerank_weights() -> None:
    from candidates.search import rerank

    assert rerank.W_BM25 == 0.5
    assert rerank.W_FINAL == 0.5


def test_phrase_alias_expands_game_of_thrones() -> None:
    import candidates.search.query_expand as query_expand

    query_expand._ALIASES_CACHE = None
    groups = query_expand.expand_query_token_groups("игра престолов")
    assert groups
    flat = {token for group in groups for token in group}
    assert "game of thrones" in flat


def test_calibrated_brigada_query_regression(fts_pool, monkeypatch) -> None:
    monkeypatch.setenv(candidate_service.FTS_SEARCH_ENV, "1")
    result = candidate_service.search_candidate_pool_text(fts_pool, {}, text_query="бригада")
    titles = [item["title"] for item in result["candidates"]]
    assert titles == ["Бригада"]
    sort_view = candidate_service.sort_search_candidates(result["candidates"], "relevance")
    assert sort_view["candidates"][0]["title"] == "Бригада"


def test_sql_path_parity_with_legacy_intersect(fts_pool, monkeypatch, tmp_path) -> None:
    from candidates import search_service
    from candidates.search.fts_index import search_fts
    from storage.sqlite.connection import connect

    monkeypatch.setenv(candidate_service.FTS_SEARCH_ENV, "1")
    filters = {"media_type": "tv", "year_min": 2000, "year_max": 2015}
    sql_result = candidate_service.search_candidate_pool_text(
        fts_pool,
        filters,
        text_query="криминал",
    )

    db_path = tmp_path / "data" / "watchbane.sqlite3"
    conn = connect(db_path)
    try:
        fts_hits = search_fts(conn, "криминал")
    finally:
        conn.close()
    legacy_result = search_service._search_candidate_pool_text_legacy(
        fts_pool,
        search_service._prepare_text_search_criteria(filters),
        normalized_query="криминал",
        fts_hits=fts_hits,
    )
    sql_keys = [
        search_service._candidate_pool_key(item) for item in sql_result["candidates"]
    ]
    legacy_keys = [
        search_service._candidate_pool_key(item) for item in legacy_result["candidates"]
    ]
    assert sql_keys == legacy_keys


@pytest.mark.parametrize(
    "corruption",
    ("missing_table", "empty", "stale", "orphan", "missing_row"),
)
def test_corrupt_fts_falls_back_to_canonical_pool(fts_pool, monkeypatch, corruption) -> None:
    from storage.sqlite.connection import connect

    monkeypatch.setenv(candidate_service.FTS_SEARCH_ENV, "1")
    conn = connect()
    try:
        brigada_key = str(
            conn.execute(
                "SELECT pool_key FROM candidate_records WHERE title_normalized = 'бригада'"
            ).fetchone()[0]
        )
        if corruption == "missing_table":
            conn.execute("DROP TABLE candidate_fts")
        elif corruption == "empty":
            conn.execute("DELETE FROM candidate_fts")
        elif corruption == "stale":
            conn.execute(
                "UPDATE candidate_fts SET document = 'outdated document' WHERE pool_key = ?",
                (brigada_key,),
            )
        elif corruption == "orphan":
            conn.execute(
                "INSERT INTO candidate_fts(pool_key, document) VALUES ('ghost|1999', 'криминал')"
            )
        else:
            conn.execute("DELETE FROM candidate_fts WHERE pool_key = ?", (brigada_key,))
        conn.commit()
    finally:
        conn.close()

    result = candidate_service.search_candidate_pool_text(
        fts_pool,
        {"country": ["RU"], "year_min": 2000, "year_max": 2005},
        text_query="криминал",
    )

    assert result["fts_enabled"] is True
    assert result["fts_fallback"] is True
    assert [item["title"] for item in result["candidates"]] == ["Бригада"]
    assert result.get("error") is None


def test_fts_orphan_never_returns_deleted_pool_record(fts_pool, monkeypatch) -> None:
    from storage.sqlite.connection import connect

    monkeypatch.setenv(candidate_service.FTS_SEARCH_ENV, "1")
    conn = connect()
    try:
        conn.execute("DELETE FROM candidate_records WHERE title_normalized = 'одноклассники'")
        conn.commit()
    finally:
        conn.close()

    result = candidate_service.search_candidate_pool_text(
        fts_pool,
        {},
        text_query="комедия",
    )

    assert result["fts_fallback"] is True
    assert result["candidates"] == []


@pytest.mark.parametrize(
    ("query", "expected"),
    (
        ("l'amour", "L'Amour"),
        ("spider-man 2", "Spider-Man 2"),
        ("ё", "Ёлки"),
        ("очень длинное описание с цифрами 2024", "Длинный запрос"),
    ),
)
def test_fallback_handles_unicode_punctuation_short_and_long_queries(
    fts_pool,
    monkeypatch,
    query,
    expected,
) -> None:
    from storage.sqlite.connection import connect

    pool = {
        "amour|2020": _candidate(title="L'Amour", year=2020),
        "spider|2021": _candidate(title="Spider-Man 2", year=2021),
        "yolki|2022": _candidate(title="Ёлки", year=2022),
        "long|2024": _candidate(
            title="Длинный запрос",
            year=2024,
            localized={"ru": {"overview": "Очень длинное описание с цифрами 2024."}},
        ),
    }
    candidate_repository.save_candidate_pool_dict(pool)
    monkeypatch.setenv(candidate_service.FTS_SEARCH_ENV, "1")
    conn = connect()
    try:
        conn.execute("DELETE FROM candidate_fts")
        conn.commit()
    finally:
        conn.close()

    result = candidate_service.search_candidate_pool_text(
        list(pool.values()),
        {},
        text_query=query,
    )

    assert [item["title"] for item in result["candidates"]] == [expected]

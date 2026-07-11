from __future__ import annotations

from candidates.search.fts_index import rebuild_fts_index, search_fts
from storage.sqlite import candidate_repository
from storage.sqlite.connection import connect
from storage.sqlite.migrations import apply_migrations, get_current_schema_version


def _save_pool(tmp_path, monkeypatch, pool: dict) -> str:
    monkeypatch.setattr("storage.data.load_dataset", lambda: {})
    db_path = tmp_path / "watchbane.sqlite3"
    candidate_repository.save_candidate_pool_dict(pool, path=db_path)
    return str(db_path)


def test_migration_v3_creates_candidate_fts(tmp_path) -> None:
    conn = connect(tmp_path / "watchbane.sqlite3")
    try:
        version = apply_migrations(conn)
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE name = 'candidate_fts'"
        ).fetchone()
        assert version == 4
        assert row is not None
    finally:
        conn.close()


def test_rebuild_and_search_by_title_genre_overview(tmp_path, monkeypatch) -> None:
    db_path = _save_pool(
        tmp_path,
        monkeypatch,
        {
            "brigada|2002": {
                "title": "Бригада",
                "year": 2002,
                "genres_tmdb": ["Crime", "Drama"],
                "genre_keys": ["crime", "drama"],
                "localized": {"ru": {"overview": "Криминальная драма о банде 90-х."}},
                "final_score": 8.0,
            },
            "comedy|2010": {
                "title": "Одноклассники",
                "year": 2010,
                "genres_tmdb": ["Comedy"],
                "genre_keys": ["comedy"],
                "localized": {"ru": {"overview": "Лёгкая комедия про выпускников."}},
                "final_score": 5.0,
            },
        },
    )

    conn = connect(db_path)
    try:
        assert rebuild_fts_index(conn) == 2
        loaded = candidate_repository.load_candidate_pool_dict(path=db_path)
        brigada_key = next(key for key, value in loaded.items() if value.get("year") == 2002)
        title_hits = search_fts(conn, "бригада")
        genre_hits = search_fts(conn, "криминал")
        overview_hits = search_fts(conn, "банда")
        assert [pool_key for pool_key, _ in title_hits] == [brigada_key]
        assert [pool_key for pool_key, _ in genre_hits] == [brigada_key]
        assert [pool_key for pool_key, _ in overview_hits] == [brigada_key]
    finally:
        conn.close()


def test_bm25_ordering_prefers_stronger_match(tmp_path, monkeypatch) -> None:
    db_path = _save_pool(
        tmp_path,
        monkeypatch,
        {
            "exact|2020": {
                "title": "Метод",
                "year": 2020,
                "localized": {"ru": {"overview": "Метод следствия детективный сериал."}},
                "final_score": 7.0,
            },
            "weak|2021": {
                "title": "Другой сериал",
                "year": 2021,
                "localized": {"ru": {"overview": "Упоминание метода вскрытия."}},
                "final_score": 9.0,
            },
        },
    )

    conn = connect(db_path)
    try:
        rebuild_fts_index(conn)
        loaded = candidate_repository.load_candidate_pool_dict(path=db_path)
        exact_key = next(key for key, value in loaded.items() if value.get("year") == 2020)
        hits = search_fts(conn, "метод")
        assert hits[0][0] == exact_key
        assert hits[0][1] <= hits[1][1]
    finally:
        conn.close()


def test_save_candidate_pool_rebuilds_fts_index(tmp_path, monkeypatch) -> None:
    db_path = _save_pool(
        tmp_path,
        monkeypatch,
        {"dark|2017": {"title": "Dark", "year": 2017, "localized": {"en": {"overview": "Time travel mystery."}}}},
    )
    conn = connect(db_path)
    try:
        assert get_current_schema_version(conn) == 4
        hits = search_fts(conn, "dark")
        assert hits and hits[0][0] == "dark|2017"
    finally:
        conn.close()


def test_multi_token_fts_match_query(tmp_path, monkeypatch) -> None:
    from candidates.search.fts_index import build_fts_match_query

    assert build_fts_match_query("one piece") == '"one piece"* OR "wan pisu"*'
    assert build_fts_match_query("сериал про") == '"сериал"* "про"*'

    db_path = _save_pool(
        tmp_path,
        monkeypatch,
        {
            "one piece|1999": {
                "title": "One Piece",
                "year": 1999,
                "localized": {"en": {"overview": "Pirate adventure anime."}},
                "final_score": 8.0,
            },
        },
    )
    conn = connect(db_path)
    try:
        import candidates.search.query_expand as query_expand

        query_expand._ALIASES_CACHE = None
        rebuild_fts_index(conn)
        hits = search_fts(conn, "one piece")
        assert hits and hits[0][0] == "one piece|1999"
    finally:
        conn.close()


def test_rebuild_script_smoke(tmp_path, monkeypatch, capsys) -> None:
    data_dir = tmp_path / "data"
    monkeypatch.setattr("config.constant.APP_DATA_DIR", str(data_dir))
    monkeypatch.setattr("storage.data.load_dataset", lambda: {})
    candidate_repository.save_candidate_pool_dict(
        {"show|2024": {"title": "Show", "year": 2024, "localized": {"en": {"overview": "A show."}}}},
        path=data_dir / "watchbane.sqlite3",
    )

    from scripts.reports import rebuild_candidate_fts_index

    assert rebuild_candidate_fts_index.main([]) == 0
    output = capsys.readouterr().out
    assert '"count": 1' in output


def test_search_fts_prefiltered_media_type_subset(tmp_path, monkeypatch) -> None:
    from candidates.search.fts_index import search_fts_prefiltered
    from candidates.search.structural_sql import build_structural_sql_filters

    db_path = _save_pool(
        tmp_path,
        monkeypatch,
        {
            "tv|2020": {
                "title": "TV Show",
                "year": 2020,
                "media_type": "tv",
                "localized": {"en": {"overview": "A detective mystery."}},
                "final_score": 7.0,
            },
            "movie|2020": {
                "title": "Movie Show",
                "year": 2020,
                "media_type": "movie",
                "localized": {"en": {"overview": "A detective mystery film."}},
                "final_score": 7.0,
            },
        },
    )
    conn = connect(db_path)
    try:
        rebuild_fts_index(conn)
        plain_hits = search_fts(conn, "detective")
        assert len(plain_hits) == 2
        clauses, params = build_structural_sql_filters({"media_type": "tv"})
        filtered_hits = search_fts_prefiltered(
            conn,
            "detective",
            structural_clauses=clauses,
            structural_params=params,
        )
        assert len(filtered_hits) == 1
        loaded = candidate_repository.load_candidate_pool_dict(path=db_path)
        tv_key = next(key for key, value in loaded.items() if value.get("title") == "TV Show")
        assert filtered_hits[0][0] == tv_key
    finally:
        conn.close()


def test_load_candidate_records_by_pool_keys_preserves_order(tmp_path, monkeypatch) -> None:
    from storage.sqlite.candidate_query_repository import load_candidate_records_by_pool_keys

    db_path = _save_pool(
        tmp_path,
        monkeypatch,
        {
            "a|2001": {"title": "A", "year": 2001, "final_score": 1.0},
            "b|2002": {"title": "B", "year": 2002, "final_score": 2.0},
            "c|2003": {"title": "C", "year": 2003, "final_score": 3.0},
        },
    )
    conn = connect(db_path)
    try:
        loaded = load_candidate_records_by_pool_keys(["c|2003", "a|2001"], conn=conn)
        assert [item["title"] for item in loaded] == ["C", "A"]
    finally:
        conn.close()

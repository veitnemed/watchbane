from __future__ import annotations

from datetime import datetime, timezone

from candidates import title_state_service
from candidates.recommendation_deck_service import RecommendationDeckService
from storage.sqlite.connection import connect
from storage.sqlite.json_codec import loads_json
from storage.sqlite.migrations import apply_migrations


NOW = datetime(2026, 7, 11, 12, 0, tzinfo=timezone.utc)


def _candidate(
    title: str,
    tmdb_id: int,
    *,
    media_type: str = "tv",
    year: int = 2015,
    tmdb_score: float = 8.0,
) -> dict:
    return {
        "title": title,
        "year": year,
        "media_type": media_type,
        "tmdb_id": tmdb_id,
        "tmdb_score": tmdb_score,
        "tmdb_votes": 1_000,
        "tmdb_popularity": 40.0,
        "countries": ["RU"],
        "country_codes": ["RU"],
        "origin_country": ["RU"],
        "genres": ["Crime"],
        "genres_tmdb": ["Crime"],
        "genre_keys": ["crime"],
        "final_score": 0.82,
    }


def _build_deck(pool: dict[str, dict], db_path, *, media_type: str | None = "tv") -> dict:
    preferences = {
        "country": ["RU"],
        "include_genres": ["crime"],
    }
    if media_type is not None:
        preferences["media_type"] = media_type
    service = RecommendationDeckService(pool_loader=lambda: pool, db_path=db_path)
    return service.build_deck(
        preferences,
        NOW,
        limit_active=10,
        reserve_size=10,
    )


def _shown(deck: dict) -> list[dict]:
    return list(deck["active"]) + list(deck["reserve"])


def test_watched_localized_alias_with_same_tv_tmdb_id_is_excluded(tmp_path) -> None:
    db_path = tmp_path / "watched-alias.sqlite3"
    localized = _candidate("Метод", 100_001)
    original = _candidate("The Method", 100_001)
    title_state_service.mark_watched(localized, path=db_path)

    deck = _build_deck({"original": original}, db_path)

    assert _shown(deck) == []
    assert deck["excluded"]["watched"] == 1


def test_hidden_localized_alias_with_same_tv_tmdb_id_is_excluded(tmp_path) -> None:
    db_path = tmp_path / "hidden-alias.sqlite3"
    localized = _candidate("Трасса", 100_002, year=2024)
    original = _candidate("The Highway", 100_002, year=2024)
    title_state_service.hide_candidate(localized, path=db_path)

    deck = _build_deck({"original": original}, db_path)

    assert _shown(deck) == []
    assert deck["excluded"]["actioned"] == 1


def test_localized_duplicates_with_same_media_and_tmdb_id_are_emitted_once(tmp_path) -> None:
    db_path = tmp_path / "duplicate-alias.sqlite3"
    localized = _candidate("Лихие", 100_003, year=2024)
    original = _candidate("Outrageous", 100_003, year=2024)

    deck = _build_deck(
        {
            "localized": localized,
            "original": original,
        },
        db_path,
    )
    shown = _shown(deck)

    assert len(shown) == 1
    assert [(item["media_type"], item["tmdb_id"]) for item in shown] == [("tv", 100_003)]
    assert deck["excluded"]["duplicate"] == 1


def test_same_tmdb_id_for_movie_and_tv_remains_distinct(tmp_path) -> None:
    db_path = tmp_path / "media-scoped-tmdb.sqlite3"
    tv = _candidate("Shared TV", 100_004, media_type="tv", year=2020)
    movie = _candidate("Shared Movie", 100_004, media_type="movie", year=2020)

    deck = _build_deck(
        {
            "tv": tv,
            "movie": movie,
        },
        db_path,
        media_type=None,
    )
    shown = _shown(deck)

    assert len(shown) == 2
    assert {(item["media_type"], item["tmdb_id"]) for item in shown} == {
        ("tv", 100_004),
        ("movie", 100_004),
    }
    assert deck["excluded"]["duplicate"] == 0


def test_mark_watched_without_score_persists_neutral_user_score(tmp_path) -> None:
    db_path = tmp_path / "neutral-watched.sqlite3"
    candidate = _candidate("Нейтральный просмотр", 100_005, tmdb_score=9.8)

    transition = title_state_service.mark_watched(candidate, path=db_path)

    conn = connect(db_path)
    try:
        apply_migrations(conn)
        row = conn.execute(
            """
            SELECT media_type, tmdb_id, user_score, payload_json
            FROM watched_records
            WHERE payload_json != '{}'
            """
        ).fetchone()
    finally:
        conn.close()

    assert transition["state"] == title_state_service.STATE_WATCHED
    assert row is not None
    assert row["media_type"] == "tv"
    assert row["tmdb_id"] == 100_005
    assert row["user_score"] is None
    payload = loads_json(row["payload_json"], {})
    assert payload["main_info"]["user_score"] is None
    assert payload["raw_scores"]["tmdb_score"] == 9.8

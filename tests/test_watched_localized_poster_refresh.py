from contextlib import closing

from dataset.read_models import watched
from storage import data
from storage.sqlite.connection import connect
from storage.sqlite.watched_write import upsert_watched_row


def _movie(title="Alpha", year=2020, tmdb_id=101, media_type="tv"):
    return {
        "main_info": {"title": title, "year": year, "media_type": media_type},
        "raw_scores": {"tmdb_id": tmdb_id},
    }


def _initialize(tmp_path, monkeypatch, movie=None):
    movie = movie or _movie()
    monkeypatch.setattr("config.constant.APP_DATA_DIR", str(tmp_path / "isolated-data"))
    data.save_dataset_and_meta({"Alpha (selected)": movie}, {"Alpha (selected)": {"tmdb_id": 101}})
    return movie


def _details(tmdb_id=101):
    return {"id": tmdb_id, "name": "Alpha", "poster_path": "/alpha-en.jpg"}


def test_localized_refresh_preserves_concurrent_watch_meta_and_legacy_only_row(tmp_path, monkeypatch):
    movie = _initialize(tmp_path, monkeypatch)

    def fetch(tmdb_id, **_):
        assert tmdb_id == 101
        with closing(connect()) as conn, conn:
            upsert_watched_row(
                conn, dataset_key="Beta", payload=_movie("Beta", 2021, 303),
                meta={"tmdb_id": 303, "custom": "keep watched meta"},
            )
            upsert_watched_row(conn, dataset_key="Legacy only", payload={}, meta={"tmdb_id": 404})
            upsert_watched_row(
                conn, dataset_key="Alpha (selected)", payload=movie,
                meta={"tmdb_id": 101, "custom": "keep current same-row fields"},
            )
        return _details()

    monkeypatch.setattr("apis.tmdb_api.get_tv_details", fetch)

    def reject_bulk(*_):
        raise AssertionError("Poster refresh must never replace the full metadata snapshot")

    monkeypatch.setattr(data, "save_meta", reject_bulk)
    meta, changed = watched._refresh_localized_poster(movie, "en")
    assert changed
    assert meta["localized"]["en"]["poster_path"] == "/alpha-en.jpg"
    assert meta["custom"] == "keep current same-row fields"
    assert data.load_meta() == {
        "Alpha (selected)": meta, "Beta": {"tmdb_id": 303, "custom": "keep watched meta"},
        "Legacy only": {"tmdb_id": 404},
    }
    assert set(data.load_dataset()) == {"Alpha (selected)", "Beta"}


def test_refresh_refuses_same_year_homonym_even_when_selected_id_is_known(tmp_path, monkeypatch):
    movie = _initialize(tmp_path, monkeypatch)
    with closing(connect()) as conn, conn:
        upsert_watched_row(
            conn, dataset_key="Alpha (other)", payload=_movie(tmdb_id=202, media_type="movie"),
            meta={"tmdb_id": 202},
        )

    def unexpected(*_args, **_kwargs):
        raise AssertionError("Ambiguous poster key must not fetch or write")

    monkeypatch.setattr("apis.tmdb_api.get_tv_details", unexpected)
    monkeypatch.setattr("posters.cache.sync_poster_cache_from_meta_and_sources", unexpected)
    assert watched.sync_poster_for_display(movie, "en") == {
        "updated": False, "reason": "watched_row_changed_or_ambiguous"
    }
    assert data.load_meta() == {"Alpha (selected)": {"tmdb_id": 101}, "Alpha (other)": {"tmdb_id": 202}}


def test_localized_refresh_does_not_write_replacement_after_response(tmp_path, monkeypatch):
    movie = _initialize(tmp_path, monkeypatch)

    def fetch(*_args, **_kwargs):
        with closing(connect()) as conn, conn:
            upsert_watched_row(
                conn, dataset_key="Alpha (selected)", payload=_movie(tmdb_id=202),
                meta={"tmdb_id": 202, "custom": "new record"},
            )
        return _details()

    monkeypatch.setattr("apis.tmdb_api.get_tv_details", fetch)
    assert watched._refresh_localized_poster(movie, "en") is None
    assert data.load_meta() == {"Alpha (selected)": {"tmdb_id": 202, "custom": "new record"}}


def test_localized_refresh_chooses_movie_endpoint_and_keeps_newer_poster(tmp_path, monkeypatch):
    movie = _initialize(tmp_path, monkeypatch, _movie(media_type="movie"))

    def fetch(tmdb_id, *, language, append_to_response):
        assert tmdb_id == 101 and language == "en-US" and append_to_response
        with closing(connect()) as conn, conn:
            upsert_watched_row(
                conn, dataset_key="Alpha (selected)", payload=movie,
                meta={"tmdb_id": 101, "localized": {"en": {"poster_path": "/newer.jpg"}}},
            )
        return _details()

    monkeypatch.setattr("apis.tmdb_api.get_movie_details", fetch)
    meta, changed = watched._refresh_localized_poster(movie, "en")
    assert not changed and meta["localized"]["en"]["poster_path"] == "/newer.jpg"
    assert data.load_meta()["Alpha (selected)"] == meta

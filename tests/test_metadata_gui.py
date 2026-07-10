import copy
import tempfile
from pathlib import Path

from config import constant
from config import scheme
from common import format_score


def _make_movie(title: str, user_score: float, year: int, raw_score: float = 8.0, **extra) -> dict:

    movie = {
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
    }
    movie.update(extra)
    return movie


def test_build_watched_movie_card_uses_meta_description() -> None:
    from web.export import build_export_lookup_cache, build_watched_movie_card

    movie = _make_movie("Meta Title", 8.0, 2020)
    lookup_cache = build_export_lookup_cache(
        meta={"Meta Title": {"description": "Описание из meta"}},
        pool_by_identity={},
    )

    card = build_watched_movie_card(movie, lookup_cache=lookup_cache)

    assert card["overview"] == "Описание из meta"


def test_build_add_meta_payload_from_resolve() -> None:
    from dataset.meta.payload import build_add_meta_payload

    resolved = {
        "source_values": {"description": "TMDb overview text"},
        "sources": {"description": "tmdb_api"},
        "tmdb_data": {
            "tmdb_id": 123,
            "imdb_id": "tt123",
            "poster_path": "/poster.jpg",
            "poster_url": "https://image.tmdb.org/t/p/original/poster.jpg",
            "tmdb_score": 7.8,
            "tmdb_votes": 456,
            "tmdb_popularity": 12.3,
            "media_type": "movie",
            "release_date": "2009-03-06",
            "runtime": 162,
            "status": "Ended",
            "in_production": False,
            "number_of_seasons": 1,
            "number_of_episodes": 8,
            "episode_run_time": [50],
            "watch_providers": ["Kinopoisk"],
            "kp_id": 999,
            "kp_score": 9.9,
            "kp_votes": 1000,
            "imdb_score": 8.8,
            "imdb_votes": 2000,
        },
        "api_data": {},
    }

    payload = build_add_meta_payload(resolved)

    assert payload["description"] == "TMDb overview text"
    assert payload["tmdb_id"] == 123
    assert payload["imdb_id"] == "tt123"
    assert payload["poster_path"] == "/poster.jpg"
    assert payload["poster_url"] == "https://image.tmdb.org/t/p/original/poster.jpg"
    assert payload["media_type"] == "movie"
    assert payload["release_date"] == "2009-03-06"
    assert payload["runtime"] == 162
    assert payload["status"] == "Ended"
    assert payload["in_production"] is False
    assert payload["number_of_seasons"] == 1
    assert payload["number_of_episodes"] == 8
    assert payload["episode_run_time"] == [50]
    assert payload["watch_providers"] == ["Kinopoisk"]
    assert payload["source"] == "tmdb"
    assert payload["raw_scores"] == {
        "tmdb_score": 7.8,
        "tmdb_votes": 456,
        "tmdb_popularity": 12.3,
    }
    assert "kp_id" not in payload
    assert "kp_score" not in payload
    assert "kp_votes" not in payload
    assert "imdb_score" not in payload
    assert "imdb_votes" not in payload


def test_build_candidate_meta_payload_uses_overview() -> None:
    from dataset.meta.payload import build_candidate_meta_payload

    payload = build_candidate_meta_payload(
        {
            "title": "Candidate",
            "overview": "Overview text",
            "tmdb_id": 42,
            "tmdb_score": 7.1,
            "tmdb_votes": 900,
            "tmdb_popularity": 5.5,
            "media_type": "movie",
            "release_date": "2009-03-06",
            "runtime": 162,
            "status": "Returning Series",
            "number_of_seasons": 2,
            "number_of_episodes": 16,
            "episode_run_time": [48],
            "watch_providers": ["Okko"],
            "kp_score": 9.9,
            "kp_votes": 1000,
            "imdb_score": 8.8,
            "imdb_votes": 2000,
        }
    )

    assert payload["description"] == "Overview text"
    assert payload["tmdb_id"] == 42
    assert payload["media_type"] == "movie"
    assert payload["release_date"] == "2009-03-06"
    assert payload["runtime"] == 162
    assert payload["status"] == "Returning Series"
    assert payload["number_of_seasons"] == 2
    assert payload["number_of_episodes"] == 16
    assert payload["episode_run_time"] == [48]
    assert payload["watch_providers"] == ["Okko"]
    assert payload["raw_scores"] == {
        "tmdb_score": 7.1,
        "tmdb_votes": 900,
        "tmdb_popularity": 5.5,
    }
    assert "kp_score" not in payload
    assert "kp_votes" not in payload
    assert "imdb_score" not in payload
    assert "imdb_votes" not in payload


def test_upsert_poster_cache_entry_preserves_local_path() -> None:
    from posters.cache import poster_identity_key, upsert_poster_cache_entry

    with tempfile.TemporaryDirectory() as temp_root:
        cache_path = Path(temp_root) / "posters.json"
        cache = {
            poster_identity_key("Local", 2021): {
                "title": "Local",
                "year": 2021,
                "local_path": str(Path(temp_root) / "existing.jpg"),
                "status": "found",
            }
        }
        (Path(temp_root) / "existing.jpg").write_text("x", encoding="utf-8")

        entry = upsert_poster_cache_entry(
            "Local",
            2021,
            {
                "poster_path": "/new.jpg",
                "poster_url": "https://example.com/new.jpg",
                "source": "test",
                "status": "found",
            },
            cache=cache,
            persist=False,
        )

        assert entry["local_path"] == str(Path(temp_root) / "existing.jpg")
        assert entry["poster_url"] == "https://example.com/new.jpg"


def test_sync_watched_metadata_updates_meta_description(monkeypatch) -> None:
    from posters import sync_watched as sync_watched_module

    dataset = {"Alpha": _make_movie("Alpha", 8.0, 2020)}
    meta = {"Alpha": {"main_info": {"title": "Alpha"}, "raw_scores": {}, "description": ""}}

    monkeypatch.setattr(sync_watched_module.storage_data, "load_dataset", lambda: dataset)
    monkeypatch.setattr(sync_watched_module.storage_data, "load_meta", lambda: dict(meta))
    monkeypatch.setattr(
        sync_watched_module.train_report,
        "resolve_movie_description",
        lambda title, year, meta_obj, pool_by_identity: "Resolved description",
    )
    monkeypatch.setattr(sync_watched_module, "load_poster_cache", lambda: {})
    monkeypatch.setattr(sync_watched_module, "save_poster_cache", lambda cache: None)

    saved = {}

    def fake_save_meta(updated_meta):
        saved["meta"] = updated_meta

    monkeypatch.setattr(sync_watched_module.storage_data, "save_meta", fake_save_meta)

    stats = sync_watched_module.sync_watched_metadata(write_meta=True)

    assert stats["description_updated"] == 1
    assert saved["meta"]["Alpha"]["description"] == "Resolved description"


def test_fetch_poster_metadata_uses_tmdb_cache(monkeypatch) -> None:
    from posters import fetch_metadata as fetch_metadata_module

    dataset = {"Show": _make_movie("Show", 8.0, 2020)}
    monkeypatch.setattr(fetch_metadata_module.storage_data, "load_dataset", lambda: dataset)
    monkeypatch.setattr(
        fetch_metadata_module.storage_data,
        "get_meta_obj",
        lambda title: {"tmdb_id": 999},
    )
    monkeypatch.setattr(fetch_metadata_module, "load_poster_cache", lambda: {})
    monkeypatch.setattr(
        fetch_metadata_module,
        "_read_poster_from_tmdb_details_cache",
        lambda tmdb_id: {
            "poster_path": "/abc.jpg",
            "poster_url": "https://image.tmdb.org/t/p/w342/abc.jpg",
            "source": "tmdb_details_cache",
            "status": "found",
        },
    )
    monkeypatch.setattr(fetch_metadata_module, "save_poster_cache", lambda cache: None)

    stats = fetch_metadata_module.fetch_poster_metadata_for_watched(use_api=False)

    assert stats["updated_from_cache"] == 1


def test_build_poster_hints_from_resolve_does_not_mutate() -> None:
    from dataset.title_resolve import build_poster_hints_from_resolve

    resolved = {
        "tmdb_data": {"poster_path": "/abc.jpg"},
        "api_data": {},
    }
    original = copy.deepcopy(resolved)

    hints = build_poster_hints_from_resolve(resolved)

    assert resolved == original
    assert hints["status"] == "found"

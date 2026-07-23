from copy import deepcopy

import pytest

from tools.migrations import migrate_watched_raw_scores_tmdb_only as migrate_script
from tools.tmdb import refresh_watched_from_tmdb as refresh_script


def _movie(title: str = "Show", year: int = 2020, media_type: str = "tv") -> dict:
    return {
        "main_info": {
            "title": title,
            "user_score": 8.0,
            "year": year,
            "country": "США",
            "media_type": media_type,
        },
        "raw_scores": {
            "kp_score": 9.9,
            "imdb_score": 8.8,
        },
        "computed_scores": {},
        "genre": {"manual_genre": 1},
    }


def _details(tmdb_id: int = 123, title: str = "Show") -> dict:
    return {
        "id": tmdb_id,
        "name": title,
        "original_name": title,
        "first_air_date": "2020-01-01",
        "vote_average": 7.8,
        "vote_count": 456,
        "popularity": 12.3,
        "overview": "TMDb overview",
        "poster_path": "/poster.jpg",
        "status": "Ended",
        "type": "Scripted",
        "in_production": False,
        "number_of_seasons": 1,
        "number_of_episodes": 8,
        "episode_run_time": [50],
        "external_ids": {"imdb_id": "tt123"},
        "origin_country": ["US"],
        "original_language": "en",
        "production_countries": [{"iso_3166_1": "US", "name": "United States of America"}],
        "genres": [{"id": 18, "name": "Drama"}],
        "networks": [{"name": "HBO"}],
        "production_companies": [{"name": "Studio"}],
        "content_ratings": {"results": [{"iso_3166_1": "US", "rating": "TV-MA"}]},
        "watch/providers": {"results": {"RU": {"flatrate": [{"provider_name": "Kinopoisk"}]}}},
        "aggregate_credits": {
            "cast": [{"id": 1, "name": "Actor", "roles": [{"character": "Lead", "episode_count": 8}]}],
            "crew": [{"id": 2, "name": "Creator", "jobs": [{"job": "Creator", "episode_count": 8}]}],
        },
        "keywords": {"results": [{"name": "marriage"}]},
    }


def test_refresh_watched_by_existing_tmdb_id_updates_meta_and_raw_scores() -> None:
    dataset = {"Show": _movie()}
    meta = {
        "Show": {
            "tmdb_id": 123,
            "personal_notes": "keep me",
            "episode_run_time": [44],
        }
    }

    updated_dataset, updated_meta, report = refresh_script.refresh_watched(
        dataset,
        meta,
        details_func=lambda tmdb_id, **kwargs: _details(tmdb_id),
    )

    movie = updated_dataset["Show"]
    meta_obj = updated_meta["Show"]
    assert report["refreshed_by_tmdb_id"] == 1
    assert report["updated_raw_scores"] == 1
    assert movie["raw_scores"] == {
        "tmdb_score": 7.8,
        "tmdb_votes": 456,
        "tmdb_popularity": 12.3,
    }
    assert "kp_score" not in movie["raw_scores"]
    assert "imdb_score" not in movie["raw_scores"]
    assert "tags_vibe" not in movie
    assert movie["genre"] == {"manual_genre": 1}
    assert meta_obj["tmdb_id"] == 123
    assert meta_obj["imdb_id"] == "tt123"
    assert meta_obj["description"] == "TMDb overview"
    assert meta_obj["poster_path"] == "/poster.jpg"
    assert meta_obj["poster_url"].endswith("/poster.jpg")
    assert meta_obj["status"] == "Ended"
    assert meta_obj["type"] == "Scripted"
    assert meta_obj["in_production"] is False
    assert meta_obj["number_of_seasons"] == 1
    assert meta_obj["number_of_episodes"] == 8
    assert meta_obj["episode_run_time"] == [50]
    assert meta_obj["origin_country"] == ["US"]
    assert meta_obj["country_codes"] == ["US"]
    assert meta_obj["countries"] == ["US", "United States of America"]
    assert meta_obj["genres"] == ["Drama"]
    assert meta_obj["genre_keys"] == ["drama"]
    assert meta_obj["original_language"] == "en"
    assert meta_obj["networks"] == ["HBO"]
    assert meta_obj["production_companies"] == ["Studio"]
    assert meta_obj["content_rating"] == "US: TV-MA"
    assert meta_obj["watch_providers"] == ["Kinopoisk"]
    assert meta_obj["actors_top"][0]["name"] == "Actor"
    assert meta_obj["crew_top"][0]["name"] == "Creator"
    assert meta_obj["keywords"] == ["marriage"]
    assert meta_obj["quality_score"] > 0
    assert meta_obj["final_score"] > 0
    assert meta_obj["personal_notes"] == "keep me"
    assert movie["main_info"]["user_score"] == 8.0


def _movie_details(tmdb_id: int = 501, title: str = "Film", *, adult) -> dict:
    """Movie-shaped Details: release_dates + credits, no TV appends."""
    return {
        "id": tmdb_id,
        "adult": adult,
        "title": title,
        "original_title": title,
        "release_date": "2024-02-03",
        "runtime": 132,
        "vote_average": 8.2,
        "vote_count": 1200,
        "popularity": 40.0,
        "overview": "Movie overview",
        "poster_path": "/movie.jpg",
        "external_ids": {"imdb_id": "tt501"},
        "origin_country": ["US"],
        "original_language": "en",
        "production_countries": [{"iso_3166_1": "US", "name": "United States of America"}],
        "genres": [{"id": 18, "name": "Drama"}],
        "production_companies": [{"name": "Studio"}],
        "release_dates": {
            "results": [
                {
                    "iso_3166_1": "RU",
                    "release_dates": [{"certification": "16+", "type": 3}],
                }
            ]
        },
        "watch/providers": {"results": {"RU": {"flatrate": [{"provider_name": "Kinopoisk"}]}}},
        "credits": {
            "cast": [{"id": 11, "name": "Lead Actor", "character": "Hero"}],
            "crew": [{"id": 12, "name": "Director", "job": "Director"}],
        },
        "keywords": {"keywords": [{"name": "heist"}]},
    }


@pytest.mark.parametrize("adult", [True, False, None])
def test_refresh_watched_movie_preserves_adult_certification_and_credits(adult) -> None:
    dataset = {"Film": _movie("Film", 2024, media_type="movie")}
    meta = {"Film": {"tmdb_id": 501, "personal_notes": "keep", "adult": True, "content_rating": "old"}}

    updated_dataset, updated_meta, report = refresh_script.refresh_watched(
        dataset,
        meta,
        details_func=lambda tmdb_id, **kwargs: _movie_details(tmdb_id, adult=adult),
    )

    meta_obj = updated_meta["Film"]
    assert report["refreshed_by_tmdb_id"] == 1
    assert "adult" in meta_obj
    assert meta_obj["adult"] is adult
    assert meta_obj["content_rating"] == "16+"
    assert meta_obj["actors_top"] == [{"name": "Lead Actor", "role": "Hero"}]
    assert meta_obj["crew_top"] == [{"name": "Director", "role": "Director"}]
    assert meta_obj["runtime"] == 132
    assert meta_obj["personal_notes"] == "keep"
    assert updated_dataset["Film"]["main_info"]["user_score"] == 8.0


def test_refresh_watched_movie_ignores_tv_shaped_rating_and_aggregate_credits() -> None:
    """Movie path must not treat content_ratings / aggregate_credits as primary sources."""
    dataset = {"Film": _movie("Film", 2024, media_type="movie")}
    meta = {"Film": {"tmdb_id": 501}}
    details = _movie_details(501, adult=False)
    details["content_ratings"] = {"results": [{"iso_3166_1": "US", "rating": "TV-MA"}]}
    details["aggregate_credits"] = {
        "cast": [{"id": 99, "name": "TV Actor", "roles": [{"character": "Extra", "episode_count": 1}]}],
        "crew": [{"id": 98, "name": "TV Creator", "jobs": [{"job": "Creator", "episode_count": 1}]}],
    }

    _updated_dataset, updated_meta, report = refresh_script.refresh_watched(
        dataset,
        meta,
        details_func=lambda tmdb_id, **kwargs: details,
    )

    meta_obj = updated_meta["Film"]
    assert report["refreshed_by_tmdb_id"] == 1
    assert meta_obj["content_rating"] == "16+"
    assert meta_obj["actors_top"][0]["name"] == "Lead Actor"
    assert meta_obj["crew_top"][0]["name"] == "Director"
    assert meta_obj["adult"] is False


def test_refresh_watched_tv_keeps_content_ratings_and_aggregate_credits() -> None:
    dataset = {"Show": _movie()}
    meta = {"Show": {"tmdb_id": 123}}
    details = _details(123)
    details["adult"] = False
    details["credits"] = {
        "cast": [{"id": 50, "name": "Wrong Movie Actor", "character": "X"}],
        "crew": [{"id": 51, "name": "Wrong Movie Crew", "job": "Writer"}],
    }
    details["release_dates"] = {
        "results": [{"iso_3166_1": "RU", "release_dates": [{"certification": "18+", "type": 3}]}]
    }

    _updated_dataset, updated_meta, report = refresh_script.refresh_watched(
        dataset,
        meta,
        details_func=lambda tmdb_id, **kwargs: details,
    )

    meta_obj = updated_meta["Show"]
    assert report["refreshed_by_tmdb_id"] == 1
    assert meta_obj["adult"] is False
    assert meta_obj["content_rating"] == "US: TV-MA"
    assert meta_obj["actors_top"][0]["name"] == "Actor"
    assert meta_obj["crew_top"][0]["name"] == "Creator"


def test_refresh_watched_uses_stable_movie_identity_and_movie_api(monkeypatch) -> None:
    dataset_key = "Shared (2024, movie)"
    dataset = {dataset_key: _movie("Shared", 2024, media_type="movie")}
    meta = {dataset_key: {"tmdb_id": 501, "personal_notes": "local"}}
    calls = []

    def movie_details(tmdb_id, **kwargs):
        calls.append((tmdb_id, kwargs["append_to_response"]))
        details = _details(tmdb_id, "Shared")
        details.pop("first_air_date")
        details["title"] = "Shared"
        details["release_date"] = "2024-02-03"
        details["runtime"] = 132
        return details

    def fail_tv_details(*_args, **_kwargs):
        raise AssertionError("TV API used for movie")

    monkeypatch.setattr(refresh_script.tmdb_api, "get_movie_details", movie_details)
    monkeypatch.setattr(refresh_script.tmdb_api, "get_tv_details", fail_tv_details)

    updated_dataset, updated_meta, report = refresh_script.refresh_watched(dataset, meta)

    assert report["refreshed_by_tmdb_id"] == 1
    assert calls == [(501, refresh_script.tmdb_api.DEFAULT_MOVIE_DETAIL_APPENDS)]
    assert list(updated_dataset) == [dataset_key]
    assert list(updated_meta) == [dataset_key]
    assert updated_meta[dataset_key]["tmdb_id"] == 501
    assert updated_meta[dataset_key]["release_date"] == "2024-02-03"
    assert updated_meta[dataset_key]["runtime"] == 132
    assert updated_meta[dataset_key]["personal_notes"] == "local"


def test_refresh_watched_clears_explicit_unknown_runtime_but_keeps_partial_fields() -> None:
    dataset = {"Show": _movie()}
    meta = {
        "Show": {
            "tmdb_id": 123,
            "personal_notes": "keep",
            "episode_run_time": [50],
            "number_of_seasons": 1,
            "number_of_episodes": 8,
            "poster_path": "/old.jpg",
        }
    }
    details = {
        "id": 123,
        "overview": "Updated overview",
        "number_of_seasons": 2,
        "number_of_episodes": 14,
        "episode_run_time": [],
        "vote_average": 8.1,
        "vote_count": 999,
    }

    updated_dataset, updated_meta, report = refresh_script.refresh_watched(
        dataset,
        meta,
        details_func=lambda _tmdb_id, **_kwargs: details,
    )

    assert report["refreshed_by_tmdb_id"] == 1
    assert updated_dataset["Show"]["main_info"]["user_score"] == 8.0
    assert updated_meta["Show"]["description"] == "Updated overview"
    assert updated_meta["Show"]["number_of_seasons"] == 2
    assert updated_meta["Show"]["number_of_episodes"] == 14
    assert "episode_run_time" not in updated_meta["Show"]
    assert updated_meta["Show"]["poster_path"] == "/old.jpg"
    assert updated_meta["Show"]["personal_notes"] == "keep"


def test_refresh_watched_timeout_and_deleted_title_leave_record_unchanged() -> None:
    dataset = {"First": _movie("First"), "Second": _movie("Second")}
    meta = {
        "First": {"tmdb_id": 1, "personal_notes": "one"},
        "Second": {"tmdb_id": 2, "personal_notes": "two"},
    }
    original_dataset = deepcopy(dataset)
    original_meta = deepcopy(meta)

    def unavailable(tmdb_id, **_kwargs):
        if tmdb_id == 1:
            raise TimeoutError("slow network")
        return {}

    updated_dataset, updated_meta, report = refresh_script.refresh_watched(
        dataset,
        meta,
        details_func=unavailable,
    )

    assert report["failed"] == 2
    assert report["processed"] == 2
    assert [item["status"] for item in report["items"]] == ["failed", "failed"]
    assert updated_dataset == original_dataset
    assert updated_meta == original_meta
    assert list(updated_dataset) == ["First", "Second"]


def test_run_refresh_applies_atomically_to_sqlite_runtime(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "watchbane.sqlite3"
    db_path.write_bytes(b"sqlite placeholder")
    report_path = tmp_path / "refresh-report.json"
    backup_path = tmp_path / "before-refresh.sqlite3"
    saved = []
    dataset = {"Show": _movie()}
    meta = {"Show": {"tmdb_id": 123, "personal_notes": "keep"}}

    monkeypatch.setattr(refresh_script, "dataset_path", lambda: db_path)
    monkeypatch.setattr(refresh_script, "meta_path", lambda: db_path)
    monkeypatch.setattr(refresh_script.storage_data, "load_dataset", lambda: deepcopy(dataset))
    monkeypatch.setattr(refresh_script.storage_data, "load_meta", lambda: deepcopy(meta))
    monkeypatch.setattr(
        refresh_script.storage_data,
        "save_dataset_and_meta",
        lambda updated_dataset, updated_meta: saved.append((updated_dataset, updated_meta)),
    )
    monkeypatch.setattr(
        refresh_script,
        "backup_sqlite_database",
        lambda *, db_path: backup_path,
    )

    report = refresh_script.run_refresh(
        apply=True,
        report_path=report_path,
        details_func=lambda tmdb_id, **_kwargs: _details(tmdb_id),
    )

    assert report["mode"] == "apply"
    assert report["dataset_path"] == str(db_path)
    assert report["meta_path"] == str(db_path)
    assert report["backup_paths"] == {"database": str(backup_path)}
    assert len(saved) == 1
    saved_dataset, saved_meta = saved[0]
    assert saved_dataset["Show"]["main_info"]["user_score"] == 8.0
    assert saved_meta["Show"]["personal_notes"] == "keep"
    assert saved_meta["Show"]["description"] == "TMDb overview"
    assert report_path.is_file()


def test_refresh_watched_without_tmdb_id_search_match_updates() -> None:
    dataset = {"Show": _movie()}
    meta = {"Show": {}}
    search_calls = []

    def fake_search(title, **kwargs):
        search_calls.append((title, kwargs))
        return [{"id": 555, "name": title, "original_name": title, "first_air_date": "2020-01-01"}]

    updated_dataset, updated_meta, report = refresh_script.refresh_watched(
        dataset,
        meta,
        search_func=fake_search,
        details_func=lambda tmdb_id, **kwargs: _details(tmdb_id),
    )

    assert report["matched_by_search"] == 1
    assert search_calls[0][0] == "Show"
    assert updated_meta["Show"]["tmdb_id"] == 555
    assert updated_dataset["Show"]["raw_scores"]["tmdb_votes"] == 456


def test_refresh_watched_uncertain_match_goes_to_report() -> None:
    dataset = {"Show": _movie()}
    meta = {"Show": {}}

    updated_dataset, updated_meta, report = refresh_script.refresh_watched(
        dataset,
        meta,
        search_func=lambda title, **kwargs: [
            {"id": 1, "name": title, "original_name": title, "first_air_date": "2020-01-01"},
            {"id": 2, "name": title, "original_name": title, "first_air_date": "2020-01-01"},
        ],
        details_func=lambda tmdb_id, **kwargs: _details(tmdb_id),
    )

    assert report["needs_manual_match"] == 1
    assert report["items"] == [{"title": "Show", "year": 2020, "status": "needs_manual_match"}]
    assert updated_dataset == dataset
    assert updated_meta == meta


def test_migrate_watched_raw_scores_strips_legacy_fields() -> None:
    dataset = {"Show": _movie()}
    meta = {"Show": {"raw_scores": {"kp_votes": 1000, "tmdb_score": 7.1}}}

    migrated_dataset, migrated_meta, stats = migrate_script.migrate_watched_raw_scores(dataset, meta)

    assert migrated_dataset["Show"]["raw_scores"] == {}
    assert migrated_dataset["Show"]["computed_scores"] == {}
    assert migrated_meta["Show"]["raw_scores"] == {"tmdb_score": 7.1}
    assert stats["dataset_records_migrated"] == 1
    assert stats["meta_records_migrated"] == 1
    assert stats["stripped_legacy_fields"] == 3

from tools.migrations import migrate_watched_raw_scores_tmdb_only as migrate_script
from tools.tmdb import refresh_watched_from_tmdb as refresh_script


def _movie(title: str = "Show", year: int = 2020) -> dict:
    return {
        "main_info": {
            "title": title,
            "user_score": 8.0,
            "year": year,
            "country": "США",
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
    meta = {"Show": {"tmdb_id": 123, "personal_notes": "keep me"}}

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

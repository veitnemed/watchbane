from candidates.pool import existing_index
from candidates.sources.tmdb import builder


def _discover_item(tmdb_id: int, title: str, year: int, votes: int = 10) -> dict:
    return {
        "id": tmdb_id,
        "name": title,
        "original_name": title,
        "first_air_date": f"{year}-01-01",
        "vote_count": votes,
        "vote_average": 7.0,
        "popularity": 5.0,
    }


def _movie_discover_item(tmdb_id: int, title: str, year: int, votes: int = 10) -> dict:
    return {
        "id": tmdb_id,
        "title": title,
        "original_title": title,
        "release_date": f"{year}-03-06",
        "vote_count": votes,
        "vote_average": 7.0,
        "popularity": 5.0,
    }


def _details(tmdb_id: int, title: str, year: int, votes: int = 20) -> dict:
    return {
        "id": tmdb_id,
        "name": title,
        "original_name": title,
        "first_air_date": f"{year}-01-01",
        "last_air_date": f"{year}-12-31",
        "origin_country": ["RU"],
        "production_countries": [{"iso_3166_1": "RU", "name": "Russia"}],
        "original_language": "ru",
        "genres": [{"id": 18, "name": "Drama"}],
        "vote_average": 7.0,
        "vote_count": votes,
        "popularity": 5.0,
        "overview": "Описание",
        "external_ids": {"imdb_id": f"tt{tmdb_id}"},
        "aggregate_credits": {},
        "keywords": {"results": []},
    }


def _movie_details(tmdb_id: int, title: str, year: int, votes: int = 20) -> dict:
    return {
        "id": tmdb_id,
        "title": title,
        "original_title": title,
        "release_date": f"{year}-03-06",
        "status": "Released",
        "runtime": 162,
        "production_countries": [{"iso_3166_1": "US", "name": "United States of America"}],
        "original_language": "en",
        "genres": [{"id": 18, "name": "Drama"}],
        "vote_average": 7.0,
        "vote_count": votes,
        "popularity": 5.0,
        "overview": "Movie overview",
        "external_ids": {"imdb_id": f"tt{tmdb_id}"},
        "credits": {},
        "keywords": {"keywords": []},
    }


def _patch_offline_builder(monkeypatch, discover_items, pool, details_calls):
    monkeypatch.setattr(builder.api_tmdb, "load_tmdb_token", lambda: "token")
    monkeypatch.setattr(builder, "load_candidate_pool", lambda: dict(pool))
    monkeypatch.setattr(builder, "remove_watched_discover", lambda items: (list(items), 0))

    def fake_tmdb_get(_path, params=None, token=None):
        assert token == "token"
        return {
            "page": (params or {}).get("page", 1),
            "total_pages": 1,
            "results": list(discover_items),
        }

    def fake_details(tmdb_id, **kwargs):
        assert "append_to_response" in kwargs
        details_calls.append(int(tmdb_id))
        source = next(item for item in discover_items if int(item["id"]) == int(tmdb_id))
        return _details(
            int(tmdb_id),
            source["name"],
            int(source["first_air_date"][:4]),
            votes=int(source.get("vote_count") or 20),
        )

    monkeypatch.setattr(builder.api_tmdb, "tmdb_get", fake_tmdb_get)
    monkeypatch.setattr(builder.api_tmdb, "get_tv_details", fake_details)


def test_existing_index_matches_tmdb_id_and_title_year() -> None:
    index = existing_index.build_existing_candidate_index(
        {
            "one": {"tmdb_id": 101, "title": "Метод", "year": 2015},
            "two": {"title": "Трасса", "year": 2024},
        }
    )

    assert existing_index.is_discover_item_existing(_discover_item(101, "Other", 2020), index) is True
    assert existing_index.discover_item_existing_reason(_discover_item(101, "Other", 2020), index) == "tmdb_id"
    assert existing_index.discover_item_existing_reason(_discover_item(202, "Трасса", 2024), index) == "title_year"
    assert existing_index.is_discover_item_existing(_discover_item(303, "Новый", 2025), index) is False


def test_existing_index_scopes_tmdb_id_and_title_year_by_media_type() -> None:
    index = existing_index.build_existing_candidate_index(
        {
            "tv": {"tmdb_id": 42, "title": "Watchmen", "year": 2019, "media_type": "tv"},
        }
    )

    assert existing_index.discover_item_existing_reason(
        _movie_discover_item(42, "Watchmen", 2019),
        index,
        media_type="movie",
    ) is None
    assert existing_index.discover_item_existing_reason(
        _discover_item(42, "Watchmen", 2019),
        index,
        media_type="tv",
    ) == "tmdb_id"


def test_tmdb_only_builder_skips_existing_before_details(monkeypatch) -> None:
    discover_items = [
        _discover_item(101, "Known by tmdb", 2020),
        _discover_item(202, "Known by title", 2021),
        _discover_item(303, "Novel", 2022),
    ]
    details_calls = []
    _patch_offline_builder(
        monkeypatch,
        discover_items,
        {
            "known_tmdb": {"tmdb_id": 101, "title": "Saved", "year": 2020},
            "known_title": {"tmdb_id": 999, "title": "Known by title", "year": 2021},
        },
        details_calls,
    )

    result = builder.build_candidate_pool("RU", pages=1, details_limit=10)

    assert details_calls == [303]
    assert result["source"] == "tmdb"
    assert result["source_version"] == 2
    assert result["stats"]["source"] == "tmdb"
    assert result["stats"]["source_version"] == 2
    assert result["stats"]["existing_pool_skipped_tmdb_id"] == 1
    assert result["stats"]["existing_pool_skipped_title_year"] == 1
    assert result["stats"]["details_requested"] == 1
    assert result["stats"]["external_ids_imdb_id_count"] == 1
    assert result["stats"]["complete_candidates"] == 1


def test_watched_item_is_still_skipped_before_existing_filter(monkeypatch) -> None:
    watched = _discover_item(101, "Watched", 2020)
    novel = _discover_item(202, "Novel", 2021)
    details_calls = []
    _patch_offline_builder(monkeypatch, [watched, novel], {}, details_calls)
    monkeypatch.setattr(builder, "remove_watched_discover", lambda items: ([novel], 1))

    result = builder.build_candidate_pool("RU", pages=1, details_limit=10)

    assert details_calls == [202]
    assert result["stats"]["watched_skipped"] == 1
    assert result["stats"]["existing_pool_skipped_tmdb_id"] == 0
    assert result["stats"]["final_candidates"] == 1


def test_builder_skips_watched_localized_title_before_details(monkeypatch) -> None:
    watched = _discover_item(1396, "Breaking Bad", 2008)
    novel = _discover_item(60059, "Better Call Saul", 2015)
    discover_items = [watched, novel]
    details_calls = []
    dataset = {
        "Во все тяжкие": {
            "main_info": {"title": "Во все тяжкие", "year": 2008},
            "localized": {"en": {"title": "Breaking Bad"}},
            "tmdb_id": 1396,
        }
    }

    monkeypatch.setattr(builder.api_tmdb, "load_tmdb_token", lambda: "token")
    monkeypatch.setattr(builder, "load_candidate_pool", lambda: {})
    monkeypatch.setattr("storage.data.load_dataset", lambda: dataset)
    monkeypatch.setattr(
        builder,
        "build_discovery_slices",
        lambda *args, **kwargs: [
            {
                "slice_name": "test",
                "query": {"sort_by": "vote_count.desc", "with_origin_country": "US"},
                "pages_per_slice": 1,
            }
        ],
    )

    def fake_tmdb_get(_path, params=None, token=None):
        assert token == "token"
        return {"page": 1, "total_pages": 1, "results": list(discover_items)}

    def fake_details(tmdb_id, **kwargs):
        assert "append_to_response" in kwargs
        details_calls.append(int(tmdb_id))
        source = next(item for item in discover_items if int(item["id"]) == int(tmdb_id))
        return _details(
            int(tmdb_id),
            source["name"],
            int(source["first_air_date"][:4]),
            votes=int(source.get("vote_count") or 20),
        )

    monkeypatch.setattr(builder.api_tmdb, "tmdb_get", fake_tmdb_get)
    monkeypatch.setattr(builder.api_tmdb, "get_tv_details", fake_details)

    result = builder.build_candidate_pool("US", pages=1, details_limit=10)

    assert details_calls == [60059]
    assert result["stats"]["watched_skipped"] == 1
    assert [candidate["title"] for candidate in result["candidates"]] == ["Better Call Saul"]


def test_skip_existing_pool_false_preserves_all_discover_items(monkeypatch) -> None:
    discover_items = [
        _discover_item(101, "Known by tmdb", 2020),
        _discover_item(202, "Novel", 2021),
    ]
    details_calls = []
    _patch_offline_builder(
        monkeypatch,
        discover_items,
        {"known": {"tmdb_id": 101, "title": "Saved", "year": 2020}},
        details_calls,
    )

    result = builder.build_candidate_pool("RU", pages=1, details_limit=10, skip_existing_pool=False)

    assert details_calls == [101, 202]
    assert result["stats"]["existing_pool_skipped_tmdb_id"] == 0
    assert result["stats"]["existing_pool_skipped_title_year"] == 0
    assert result["stats"]["details_requested"] == 2


def test_tmdb_only_builder_does_not_return_kp_or_imdb_rating_fields(monkeypatch) -> None:
    details_calls = []
    _patch_offline_builder(monkeypatch, [_discover_item(101, "Novel", 2020)], {}, details_calls)

    result = builder.build_candidate_pool("RU", pages=1, details_limit=1)

    candidate = result["candidates"][0]
    assert candidate["imdb_id"] == "tt101"
    for field_name in (
        "kp_score",
        "kp_votes",
        "kp_id",
        "kp_status",
        "imdb_score",
        "imdb_votes",
        "imdb_rating",
        "imdb_runtime_minutes",
        "imdb_genres",
    ):
        assert field_name not in candidate


def test_tmdb_movie_builder_uses_movie_discover_details_and_normalizer(monkeypatch) -> None:
    discover_items = [_movie_discover_item(202, "Watchmen", 2009)]
    details_calls = []
    discover_paths = []

    monkeypatch.setattr(builder.api_tmdb, "load_tmdb_token", lambda: "token")
    monkeypatch.setattr(builder, "load_candidate_pool", lambda: {})
    monkeypatch.setattr(builder, "remove_watched_discover", lambda items, **_kwargs: (list(items), 0))

    def fake_tmdb_get(path, params=None, token=None):
        discover_paths.append((path, params or {}))
        assert token == "token"
        return {"page": 1, "total_pages": 1, "results": list(discover_items)}

    def fake_details(tmdb_id, **kwargs):
        assert "append_to_response" in kwargs
        details_calls.append(int(tmdb_id))
        source = discover_items[0]
        return _movie_details(
            int(tmdb_id),
            source["title"],
            int(source["release_date"][:4]),
            votes=int(source.get("vote_count") or 20),
        )

    monkeypatch.setattr(builder.api_tmdb, "tmdb_get", fake_tmdb_get)
    monkeypatch.setattr(builder.api_tmdb, "get_movie_details", fake_details)

    result = builder.build_candidate_pool(
        "US",
        pages=1,
        details_limit=1,
        year_min=2009,
        year_max=2009,
        media_type="movie",
    )

    assert discover_paths[0][0] == "/discover/movie"
    assert discover_paths[0][1]["primary_release_date.gte"] == "2009-01-01"
    assert "first_air_date.gte" not in discover_paths[0][1]
    assert details_calls == [202]
    assert result["media_type"] == "movie"
    assert result["settings"]["media_type"] == "movie"
    candidate = result["candidates"][0]
    assert candidate["media_type"] == "movie"
    assert candidate["title"] == "Watchmen"
    assert candidate["release_date"] == "2009-03-06"
    assert candidate["runtime"] == 162

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


def _details(tmdb_id: int, title: str, year: int, votes: int = 20) -> dict:
    return {
        "id": tmdb_id,
        "name": title,
        "original_name": title,
        "first_air_date": f"{year}-01-01",
        "origin_country": ["RU"],
        "production_countries": [{"iso_3166_1": "RU", "name": "Russia"}],
        "original_language": "ru",
        "genres": [{"id": 18, "name": "Drama"}],
        "vote_average": 7.0,
        "vote_count": votes,
        "popularity": 5.0,
        "overview": "",
        "external_ids": {},
        "credits": {},
    }


class _FakeConnection:
    def close(self) -> None:
        pass


def _patch_offline_builder(
    monkeypatch,
    discover_items,
    pool,
    details_calls,
    *,
    fail_imdb=False,
    fail_kp_cache=False,
    fail_kp_api=False,
    kp_cache_calls=None,
    kp_api_calls=None,
):
    monkeypatch.setattr(builder.api_tmdb, "load_tmdb_token", lambda: "token")
    monkeypatch.setattr(builder.api_tmdb, "discover_tv_candidates", lambda **_kwargs: list(discover_items))
    monkeypatch.setattr(builder, "load_candidate_pool", lambda: dict(pool))
    monkeypatch.setattr(builder, "remove_watched_discover", lambda items: (list(items), 0))

    def fake_details(tmdb_id, **_kwargs):
        details_calls.append(int(tmdb_id))
        source = next(item for item in discover_items if int(item["id"]) == int(tmdb_id))
        return _details(
            int(tmdb_id),
            source["name"],
            int(source["first_air_date"][:4]),
            votes=int(source.get("vote_count") or 20),
        )

    def fake_connect(_db_path):
        if fail_imdb:
            raise AssertionError("IMDb should not be touched for skipped discover items")
        return _FakeConnection()

    def fake_imdb(candidate, _conn):
        if fail_imdb:
            raise AssertionError("IMDb should not be touched for skipped discover items")
        return candidate

    def fake_kp_cache(candidate):
        if fail_kp_cache:
            raise AssertionError("KP should not be touched for skipped discover items")
        if kp_cache_calls is not None:
            kp_cache_calls.append(candidate.get("tmdb_id"))
        candidate["kp_id"] = None
        candidate["kp_rating"] = None
        candidate["kp_votes"] = None
        candidate["kp_status"] = "not_requested"
        candidate["is_complete"] = False
        return candidate

    def fake_kp_api(candidate, _country, _stats, **_kwargs):
        if fail_kp_api:
            raise AssertionError("KP should not be touched for skipped discover items")
        if kp_api_calls is not None:
            kp_api_calls.append(candidate.get("tmdb_id"))
        return candidate

    monkeypatch.setattr(builder.api_tmdb, "get_tv_details", fake_details)
    monkeypatch.setattr(builder, "connect_imdb", fake_connect)
    monkeypatch.setattr(builder, "enrich_from_imdb_sql", fake_imdb)
    monkeypatch.setattr(builder, "enrich_from_kp_cache_only", fake_kp_cache)
    monkeypatch.setattr(builder, "enrich_from_kp_api_if_needed", fake_kp_api)


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
    assert existing_index.filter_existing_discover_items(
        [
            _discover_item(101, "Other", 2020),
            _discover_item(303, "Новый", 2025),
        ],
        index,
    ) == [_discover_item(303, "Новый", 2025)]


def test_discover_item_with_existing_tmdb_id_is_skipped_before_details(monkeypatch) -> None:
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

    result = builder.build_candidate_pool("RU", skip_existing_pool=True, kp_build_debug=False)

    assert details_calls == [202]
    assert result["stats"]["existing_pool_skipped_tmdb_id"] == 1
    assert result["stats"]["existing_pool_skipped_title_year"] == 0
    assert result["stats"]["novel_before_details"] == 1
    assert result["stats"]["details_requested"] == 1


def test_discover_item_with_existing_title_year_is_skipped_before_details(monkeypatch) -> None:
    discover_items = [
        _discover_item(101, "Трасса", 2024),
        _discover_item(202, "Novel", 2021),
    ]
    details_calls = []
    _patch_offline_builder(
        monkeypatch,
        discover_items,
        {"known": {"tmdb_id": 999, "title": "Трасса", "year": 2024}},
        details_calls,
    )

    result = builder.build_candidate_pool("RU", skip_existing_pool=True, kp_build_debug=False)

    assert details_calls == [202]
    assert result["stats"]["existing_pool_skipped_tmdb_id"] == 0
    assert result["stats"]["existing_pool_skipped_title_year"] == 1
    assert result["stats"]["novelty_rate_before_details"] == 0.5


def test_watched_item_is_still_skipped_before_existing_filter(monkeypatch) -> None:
    watched = _discover_item(101, "Watched", 2020)
    novel = _discover_item(202, "Novel", 2021)
    discover_items = [watched, novel]
    details_calls = []
    _patch_offline_builder(monkeypatch, discover_items, {}, details_calls)
    monkeypatch.setattr(builder, "remove_watched_discover", lambda items: ([novel], 1))

    result = builder.build_candidate_pool("RU", skip_existing_pool=True, kp_build_debug=False)

    assert details_calls == [202]
    assert result["stats"]["watched_skipped"] == 1
    assert result["stats"]["existing_pool_skipped_tmdb_id"] == 0
    assert result["stats"]["novel_before_details"] == 1


def test_skip_existing_pool_false_preserves_old_behavior(monkeypatch) -> None:
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

    result = builder.build_candidate_pool("RU", skip_existing_pool=False, kp_build_debug=False)

    assert details_calls == [101, 202]
    assert result["stats"]["existing_pool_skipped_tmdb_id"] == 0
    assert result["stats"]["existing_pool_skipped_title_year"] == 0
    assert result["stats"]["details_requested"] == 2


def test_no_kp_or_imdb_calls_happen_when_all_discover_items_are_skipped(monkeypatch) -> None:
    discover_items = [
        _discover_item(101, "Known by tmdb", 2020),
        _discover_item(202, "Known by title", 2021),
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
        fail_imdb=True,
        fail_kp_cache=True,
        fail_kp_api=True,
    )

    result = builder.build_candidate_pool("RU", skip_existing_pool=True, kp_build_debug=False)

    assert details_calls == []
    assert result["stats"]["existing_pool_skipped_tmdb_id"] == 1
    assert result["stats"]["existing_pool_skipped_title_year"] == 1
    assert result["stats"]["novel_before_details"] == 0
    assert result["stats"]["details_requested"] == 0
    assert result["candidates"] == []


def test_enrichment_mode_fast_skips_imdb_sql_and_kp(monkeypatch) -> None:
    discover_items = [_discover_item(101, "Fast", 2020)]
    details_calls = []
    _patch_offline_builder(
        monkeypatch,
        discover_items,
        {},
        details_calls,
        fail_imdb=True,
        fail_kp_cache=True,
        fail_kp_api=True,
    )

    result = builder.build_candidate_pool("RU", enrichment_mode="fast", kp_build_debug=False)

    assert details_calls == [101]
    assert result["stats"]["enrichment_mode"] == "fast"
    assert result["stats"]["found_in_imdb_sql"] == 0
    assert result["stats"]["kp_api_requested"] == 0
    assert "kp_status" not in result["candidates"][0]
    assert result["candidates"][0]["quality_score"] > 0


def test_enrichment_mode_kp_cache_uses_cache_without_api_or_imdb(monkeypatch) -> None:
    discover_items = [_discover_item(101, "Cache", 2020)]
    details_calls = []
    kp_cache_calls = []
    _patch_offline_builder(
        monkeypatch,
        discover_items,
        {},
        details_calls,
        fail_imdb=True,
        fail_kp_api=True,
        kp_cache_calls=kp_cache_calls,
    )

    result = builder.build_candidate_pool("RU", enrichment_mode="kp_cache", kp_build_debug=False)

    assert details_calls == [101]
    assert kp_cache_calls == [101]
    assert result["stats"]["enrichment_mode"] == "kp_cache"
    assert result["stats"]["kp_api_requested"] == 0


def test_enrichment_mode_kp_top_calls_api_only_for_top_n_after_basic_quality(monkeypatch) -> None:
    discover_items = [
        _discover_item(101, "Low", 2020, votes=10),
        _discover_item(202, "High", 2021, votes=500),
        _discover_item(303, "Middle", 2022, votes=100),
    ]
    details_calls = []
    kp_api_calls = []
    _patch_offline_builder(
        monkeypatch,
        discover_items,
        {},
        details_calls,
        fail_imdb=True,
        kp_api_calls=kp_api_calls,
    )

    result = builder.build_candidate_pool(
        "RU",
        enrichment_mode="kp_top",
        kp_top_limit=2,
        kp_build_debug=False,
    )

    assert details_calls == [202, 303, 101]
    assert kp_api_calls == [202, 303]
    assert result["stats"]["enrichment_mode"] == "kp_top"
    assert result["stats"]["kp_top_limit"] == 2
    assert result["stats"]["kp_api_skipped_not_top"] == 1


def test_enrichment_mode_full_preserves_imdb_and_kp_api_behavior(monkeypatch) -> None:
    discover_items = [_discover_item(101, "Full", 2020)]
    details_calls = []
    kp_cache_calls = []
    kp_api_calls = []
    _patch_offline_builder(
        monkeypatch,
        discover_items,
        {},
        details_calls,
        kp_cache_calls=kp_cache_calls,
        kp_api_calls=kp_api_calls,
    )

    result = builder.build_candidate_pool("RU", kp_build_debug=False)

    assert details_calls == [101]
    assert kp_cache_calls == [101]
    assert kp_api_calls == [101]
    assert result["stats"]["enrichment_mode"] == "full"

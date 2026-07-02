"""Tests for TMDb details helpers."""

from apis import tmdb_api


def _details_payload(**overrides) -> dict:
    payload = {
        "id": 101,
        "name": "Show",
        "overview": "Русское описание",
        "poster_path": "/poster.jpg",
        "external_ids": {
            "imdb_id": "tt123",
            "tvdb_id": 456,
        },
        "aggregate_credits": {
            "cast": [
                {
                    "id": 1,
                    "name": "Actor One",
                    "roles": [
                        {"character": "Hero", "episode_count": 12},
                    ],
                },
                {
                    "id": 2,
                    "name": "Actor Two",
                    "roles": [
                        {"character": "Friend", "episode_count": 3},
                    ],
                },
            ],
            "crew": [
                {
                    "id": 3,
                    "name": "Writer One",
                    "jobs": [
                        {"job": "Writer", "episode_count": 8},
                    ],
                },
            ],
        },
    }
    payload.update(overrides)
    return payload


def test_get_tv_details_uses_default_tv_detail_appends(monkeypatch, tmp_path) -> None:
    calls = []
    monkeypatch.setattr(tmdb_api, "DETAILS_CACHE_DIR", tmp_path)

    def fake_cached_tmdb_get(path, params, cache_path, *, force_refresh=False, token=None):
        calls.append((path, params, cache_path, force_refresh, token))
        return {"id": 101}

    monkeypatch.setattr(tmdb_api, "cached_tmdb_get", fake_cached_tmdb_get)

    result = tmdb_api.get_tv_details(101, token="token")

    assert result == {"id": 101}
    assert calls[0][0] == "/tv/101"
    assert calls[0][1]["append_to_response"] == ",".join(tmdb_api.DEFAULT_TV_DETAIL_APPENDS)
    assert "aggregate_credits" in calls[0][1]["append_to_response"]
    assert str(calls[0][2]).endswith(".json")


def test_extract_best_overview_prefers_raw_ru_overview() -> None:
    assert tmdb_api.extract_best_overview(_details_payload()) == "Русское описание"


def test_extract_best_overview_falls_back_to_translation_en() -> None:
    details = _details_payload(
        overview="",
        translations={
            "translations": [
                {
                    "iso_639_1": "en",
                    "iso_3166_1": "US",
                    "data": {"overview": "English overview"},
                },
            ],
        },
    )

    assert tmdb_api.extract_best_overview(details) == "English overview"


def test_extract_best_poster_path_uses_direct_poster() -> None:
    assert tmdb_api.extract_best_poster_path(_details_payload()) == "/poster.jpg"


def test_extract_external_ids_preserves_imdb_id() -> None:
    assert tmdb_api.extract_external_ids(_details_payload())["imdb_id"] == "tt123"
    assert tmdb_api.normalize_tmdb_tv(_details_payload())["imdb_id"] == "tt123"


def test_extract_aggregate_credits_top_parses_people() -> None:
    credits = tmdb_api.extract_aggregate_credits_top(_details_payload(), limit=1)

    assert credits["actors_top"] == [
        {
            "name": "Actor One",
            "role": "Hero",
            "episode_count": 12,
            "tmdb_person_id": 1,
        }
    ]
    assert credits["crew_top"] == [
        {
            "name": "Writer One",
            "role": "Writer",
            "episode_count": 8,
            "tmdb_person_id": 3,
        }
    ]

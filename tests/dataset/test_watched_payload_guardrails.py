from __future__ import annotations

from config import constant, scheme
from dataset.dataset_records import add_dataset_record, update_dataset_record

FORBIDDEN_PAYLOAD_KEYS = {"tags_vibe", "genre"}
FORBIDDEN_RAW_SCORE_KEYS = {"kp_score", "kp_votes", "imdb_score", "imdb_votes", "kp_popularity", "imdb_popularity"}


def test_add_dataset_record_does_not_persist_legacy_payload_fields(monkeypatch) -> None:
    saved: dict = {}

    def fake_save_dataset_and_meta(data, meta):
        saved["data"] = data
        saved["meta"] = meta

    monkeypatch.setattr("dataset.records.add.save_dataset_and_meta", fake_save_dataset_and_meta)
    monkeypatch.setattr("dataset.records.add.load_dataset", lambda: {})
    monkeypatch.setattr("dataset.records.add.load_meta", lambda: {})
    monkeypatch.setattr("dataset.records.add.run_after_add_side_effects", lambda **kwargs: {})

    result = add_dataset_record(
        {
            "main_info": {
                "title": "Guardrail Show",
                "user_score": 3,
                "year": 2020,
                "country": "США",
            },
            "raw_scores": {
                "tmdb_score": 7.5,
                "tmdb_votes": 100,
                "tmdb_popularity": 12.0,
            },
            "genres_tmdb": ["Drama"],
            "genre": {"has_drama": 1},
        }
    )

    assert result.ok is True
    movie = saved["data"]["Guardrail Show"]
    assert FORBIDDEN_PAYLOAD_KEYS.isdisjoint(movie.keys())
    assert FORBIDDEN_RAW_SCORE_KEYS.isdisjoint(movie["raw_scores"].keys())
    assert movie.get("genres_tmdb") == ["Drama"]


def test_update_dataset_record_does_not_persist_legacy_payload_fields(monkeypatch) -> None:
    existing = {
        "Guardrail Show": {
            "main_info": {
                "title": "Guardrail Show",
                "user_score": 3,
                "year": 2020,
                "country": "США",
            },
            "raw_scores": {
                "tmdb_score": 7.5,
                "tmdb_votes": 100,
                "tmdb_popularity": 12.0,
            },
            "computed_scores": {},
            "genres_tmdb": ["Drama"],
        }
    }
    saved: dict = {}

    def fake_save_dataset(data):
        saved["data"] = data

    monkeypatch.setattr("dataset.records.update.save_dataset", fake_save_dataset)
    monkeypatch.setattr("dataset.records.update.load_dataset", lambda: existing)

    result = update_dataset_record(
        "Guardrail Show",
        {
            "raw_scores": {
                "tmdb_score": 8.0,
                "tmdb_votes": 200,
                "tmdb_popularity": 15.0,
            }
        },
    )

    assert result.ok is True
    movie = saved["data"]["Guardrail Show"]
    assert FORBIDDEN_PAYLOAD_KEYS.isdisjoint(movie.keys())
    assert FORBIDDEN_RAW_SCORE_KEYS.isdisjoint(movie["raw_scores"].keys())

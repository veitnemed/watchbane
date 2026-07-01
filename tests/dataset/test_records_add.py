import copy

from config import constant
from config import scheme
from common import format_score


def _valid_add_payload(title: str = "New Title") -> dict:
    return {
        "main_info": {
            "title": title,
            "user_score": 8.0,
            "year": 2020,
            "country": "Россия",
        },
        "raw_scores": {
            "kp_score": 8.0,
            "kp_votes": 1000,
            "imdb_score": 8.0,
            "imdb_votes": 100,
        },
        constant.TAGS_VIBE_SECTION: {feature: 0 for feature in constant.TAGS_VIBE},
        constant.GENRE_SECTION: {feature: 0 for feature in constant.GENRE},
    }


def test_add_dataset_record_returns_side_effects(monkeypatch) -> None:
    from dataset.records import add as add_module
    from dataset.records.add import add_dataset_record

    saved = {}

    monkeypatch.setattr(add_module, "load_dataset", lambda: {})
    monkeypatch.setattr(add_module, "save_dataset", lambda data: saved.update(data))
    monkeypatch.setattr(add_module, "get_meta_obj", lambda _title: None)
    monkeypatch.setattr(add_module, "add_movies_to_meta", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        add_module,
        "run_after_add_side_effects",
        lambda **_kwargs: [{"type": "poster_cache_sync", "ok": True}],
    )

    result = add_dataset_record(_valid_add_payload())

    assert result.ok is True
    assert result.side_effects == [{"type": "poster_cache_sync", "ok": True}]
    assert "New Title" in saved


def test_add_dataset_record_rejects_duplicate(monkeypatch) -> None:
    from dataset.records import add as add_module
    from dataset.records.add import add_dataset_record

    monkeypatch.setattr(add_module, "load_dataset", lambda: {"New Title": {}})

    result = add_dataset_record(_valid_add_payload())

    assert result.ok is False
    assert result.reason == "duplicate_title"

from config import constant


def _valid_add_payload(title: str = "New Title") -> dict:
    return {
        "main_info": {
            "title": title,
            "user_score": 8.0,
            "year": 2020,
            "country": "Россия",
        },
        "raw_scores": {
            "tmdb_score": 8.0,
            "tmdb_votes": 1000,
            "tmdb_popularity": 42.5,
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
    assert saved["New Title"]["main_info"]["media_type"] == "tv"


def test_add_dataset_record_rejects_duplicate(monkeypatch) -> None:
    from dataset.records import add as add_module
    from dataset.records.add import add_dataset_record

    monkeypatch.setattr(add_module, "load_dataset", lambda: {"New Title": {}})

    result = add_dataset_record(_valid_add_payload())

    assert result.ok is False
    assert result.reason == "duplicate_title"


def test_add_dataset_record_allows_same_title_with_different_media_type(monkeypatch) -> None:
    from dataset.records import add as add_module
    from dataset.records.add import add_dataset_record

    saved = {}
    meta_calls = []
    existing = {
        "Watchmen": {
            "main_info": {
                "title": "Watchmen",
                "user_score": 8.0,
                "year": 2019,
                "country": "US",
                "media_type": "tv",
            }
        }
    }

    monkeypatch.setattr(add_module, "load_dataset", lambda: dict(existing))
    monkeypatch.setattr(add_module, "save_dataset", lambda data: saved.update(data))
    monkeypatch.setattr(add_module, "get_meta_obj", lambda _title: None)
    monkeypatch.setattr(
        add_module,
        "add_movies_to_meta",
        lambda _main, _raw, extra_meta=None, **kwargs: meta_calls.append(kwargs) or True,
    )
    monkeypatch.setattr(add_module, "run_after_add_side_effects", lambda **_kwargs: [])

    payload = _valid_add_payload("Watchmen")
    payload["main_info"]["year"] = 2009
    payload["main_info"]["media_type"] = "movie"

    result = add_dataset_record(payload)

    assert result.ok is True
    assert result.title == "Watchmen (2009, movie)"
    assert saved["Watchmen (2009, movie)"]["main_info"]["title"] == "Watchmen"
    assert saved["Watchmen (2009, movie)"]["main_info"]["media_type"] == "movie"
    assert meta_calls == [{"meta_key": "Watchmen (2009, movie)"}]


def test_add_dataset_record_accepts_tmdb_only_raw_scores(monkeypatch) -> None:
    from dataset.records import add as add_module
    from dataset.records.add import add_dataset_record

    saved = {}
    meta_saved = {}

    monkeypatch.setattr(add_module, "load_dataset", lambda: {})
    monkeypatch.setattr(add_module, "save_dataset", lambda data: saved.update(data))
    monkeypatch.setattr(add_module, "get_meta_obj", lambda _title: None)
    monkeypatch.setattr(add_module, "add_movies_to_meta", lambda _main, raw, extra_meta=None: meta_saved.update(raw) or True)
    monkeypatch.setattr(add_module, "run_after_add_side_effects", lambda **_kwargs: [])

    payload = _valid_add_payload("TMDb Only")
    payload["raw_scores"] = {
        "tmdb_score": 8.1,
        "tmdb_votes": 1200,
        "tmdb_popularity": 42.5,
    }

    result = add_dataset_record(payload)

    assert result.ok is True
    movie = saved["TMDb Only"]
    assert movie["raw_scores"] == {
        "tmdb_score": 8.1,
        "tmdb_votes": 1200,
        "tmdb_popularity": 42.5,
    }
    assert "kp_score" not in movie["raw_scores"]
    assert "imdb_score" not in movie["raw_scores"]
    assert movie["computed_scores"]["tmdb_score"] == 8.1
    assert meta_saved["tmdb_votes"] == 1200


def test_add_dataset_record_saves_new_meta_from_tmdb_meta_payload(monkeypatch) -> None:
    from dataset.records import add as add_module
    from dataset.records.add import add_dataset_record

    saved = {}
    meta_calls = []

    monkeypatch.setattr(add_module, "load_dataset", lambda: {})
    monkeypatch.setattr(add_module, "save_dataset", lambda data: saved.update(data))
    monkeypatch.setattr(add_module, "get_meta_obj", lambda _title: None)
    monkeypatch.setattr(
        add_module,
        "add_movies_to_meta",
        lambda main, raw, extra_meta=None: meta_calls.append({
            "main": dict(main),
            "raw": dict(raw),
            "extra_meta": dict(extra_meta or {}),
        }) or True,
    )
    monkeypatch.setattr(add_module, "load_meta", lambda: {})
    monkeypatch.setattr(add_module, "save_meta", lambda _meta: None)
    monkeypatch.setattr(add_module, "run_after_add_side_effects", lambda **_kwargs: [])

    payload = _valid_add_payload("TMDb Meta")
    payload["raw_scores"] = {
        "tmdb_score": 7.7,
        "tmdb_votes": 22,
        "tmdb_popularity": 39.2,
    }
    meta_payload = {
        "raw_scores": dict(payload["raw_scores"]),
        "tmdb_id": 153581,
        "description": "TMDb description.",
        "poster_path": "/poster.jpg",
    }

    result = add_dataset_record(payload, meta_payload=meta_payload)

    assert result.ok is True
    assert "TMDb Meta" in saved
    assert meta_calls == [{
        "main": payload["main_info"],
        "raw": payload["raw_scores"],
        "extra_meta": {
            "tmdb_id": 153581,
            "description": "TMDb description.",
            "poster_path": "/poster.jpg",
        },
    }]

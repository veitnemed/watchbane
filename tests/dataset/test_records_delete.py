from common import format_score


def _make_movie(title: str, user_score: float, year: int) -> dict:
    raw_scores = {
        "tmdb_score": 8.0,
        "tmdb_votes": 120000,
        "tmdb_popularity": 42.5,
    }
    main_info = {"title": title, "user_score": user_score, "year": year}
    return {
        "main_info": main_info,
        "raw_scores": raw_scores,
        "computed_scores": format_score.raw_to_struct(raw_scores, main_info),
    }


def test_delete_watched_record_returns_delete_record_result(monkeypatch, tmp_path) -> None:
    from dataset.records import delete as delete_module
    from dataset.records.delete import delete_watched_record
    from posters.cache import poster_identity_key

    dataset = {"Alpha": _make_movie("Alpha", 8.0, 2020)}
    meta = {"Alpha": {"main_info": dataset["Alpha"]["main_info"], "raw_scores": dataset["Alpha"]["raw_scores"]}}
    identity = poster_identity_key("Alpha", 2020)
    poster_cache = {identity: {"title": "Alpha", "year": 2020, "status": "found"}}

    from storage import data as storage_data
    from storage.sqlite.poster_repository import save_poster_cache_dict

    monkeypatch.setattr("config.constant.APP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr("config.constant.BACKUP_DIR", str(tmp_path / "backups"))
    monkeypatch.setattr(delete_module, "DEFAULT_POSTER_CACHE_JSON", tmp_path / "legacy-posters.json")
    monkeypatch.setattr("posters.download_images.DEFAULT_POSTER_IMAGES_DIR", tmp_path / "images")
    storage_data.save_dataset_and_meta(dataset, meta)
    save_poster_cache_dict(poster_cache)

    result = delete_watched_record("Alpha", timestamp="test")

    assert result.ok is True
    assert result.deleted_dataset == 1
    assert result.deleted_meta == 1
    assert result.deleted_poster_cache == 1
    assert "Alpha" not in storage_data.load_dataset()
    assert result.to_dict()["ok"] is True


def test_build_watched_delete_preview_flags_meta_and_poster(monkeypatch) -> None:
    from dataset.records.delete import build_watched_delete_preview
    from posters.cache import poster_identity_key

    dataset = {"Alpha": _make_movie("Alpha", 8.0, 2020)}
    meta = {"Alpha": {"main_info": dataset["Alpha"]["main_info"]}}
    identity = poster_identity_key("Alpha", 2020)

    monkeypatch.setattr("dataset.records.delete.storage_data.load_meta", lambda: meta)
    monkeypatch.setattr(
        "dataset.records.delete.load_poster_cache",
        lambda: {identity: {"status": "found", "local_path": "C:/alpha.jpg"}},
    )

    preview = build_watched_delete_preview("Alpha", data=dataset)

    assert preview is not None
    assert preview["has_meta"] is True
    assert preview["has_poster_cache"] is True

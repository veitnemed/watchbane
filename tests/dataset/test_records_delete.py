import copy

from config import constant
from config import scheme
from common import format_score


def _make_movie(title: str, user_score: float, year: int) -> dict:
    tags_vibe = {feature: 0 for feature in constant.TAGS_VIBE}
    genre_tags = {feature: 0 for feature in constant.GENRE}
    return {
        "main_info": {"title": title, "user_score": user_score, "year": year},
        "raw_scores": {
            "kp_score": 8.0,
            "kp_votes": 120000,
            "imdb_score": 8.0,
            "imdb_votes": 1200,
        },
        "computed_scores": format_score.raw_to_struct(
            {"kp_score": 8.0, "kp_votes": 120000, "imdb_score": 8.0, "imdb_votes": 1200},
            {"title": title, "user_score": user_score, "year": year},
        ),
        scheme.TAGS_VIBE: tags_vibe,
        constant.GENRE_SECTION: genre_tags,
    }


def test_delete_watched_record_returns_delete_record_result(monkeypatch) -> None:
    from dataset.records import delete as delete_module
    from dataset.records.delete import delete_watched_record
    from posters.cache import poster_identity_key

    dataset = {"Alpha": _make_movie("Alpha", 8.0, 2020)}
    meta = {"Alpha": {"main_info": dataset["Alpha"]["main_info"], "raw_scores": dataset["Alpha"]["raw_scores"]}}
    identity = poster_identity_key("Alpha", 2020)
    poster_cache = {identity: {"title": "Alpha", "year": 2020, "status": "found"}}

    saved_dataset = {}
    saved_meta = {}
    saved_cache = {}

    monkeypatch.setattr(delete_module.storage_data, "load_dataset", lambda: copy.deepcopy(dataset))
    monkeypatch.setattr(delete_module.storage_data, "load_meta", lambda: copy.deepcopy(meta))
    monkeypatch.setattr(delete_module, "load_poster_cache", lambda: copy.deepcopy(poster_cache))
    monkeypatch.setattr(delete_module.storage_data, "save_dataset", lambda payload: saved_dataset.update(payload))
    monkeypatch.setattr(delete_module.storage_data, "save_meta", lambda payload: saved_meta.update(payload))
    monkeypatch.setattr(delete_module, "save_poster_cache", lambda payload: saved_cache.update(payload))
    monkeypatch.setattr(delete_module, "backup_before_watched_delete", lambda timestamp=None: ["backup-dataset"])

    result = delete_watched_record("Alpha", timestamp="test")

    assert result.ok is True
    assert result.deleted_dataset == 1
    assert result.deleted_meta == 1
    assert result.deleted_poster_cache == 1
    assert "Alpha" not in saved_dataset
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

from config import constant
from config import scheme
from common import format_score


def _make_movie(title: str, user_score: float, year: int) -> dict:
    tags_vibe = {feature: 0 for feature in constant.TAGS_VIBE}
    genre_tags = {feature: 0 for feature in constant.GENRE}
    raw_scores = {
        "kp_score": 8.0,
        "kp_votes": 120000,
        "imdb_score": 8.0,
        "imdb_votes": 1200,
    }
    main_info = {"title": title, "user_score": user_score, "year": year, "country": "Россия"}
    return {
        "main_info": main_info,
        "raw_scores": raw_scores,
        "computed_scores": format_score.raw_to_struct(raw_scores, main_info),
        scheme.TAGS_VIBE: tags_vibe,
        constant.GENRE_SECTION: genre_tags,
    }


def test_update_dataset_record_forbids_rename(monkeypatch) -> None:
    from dataset.records import update as update_module
    from dataset.records.update import update_dataset_record

    monkeypatch.setattr(
        update_module,
        "load_dataset",
        lambda: {"Alpha": _make_movie("Alpha", 8.0, 2020)},
    )

    result = update_dataset_record("Alpha", {"main_info": {"title": "Beta"}})

    assert result.ok is False
    assert result.reason == "title_change_forbidden"


def test_update_dataset_record_syncs_meta_on_raw_only_change(monkeypatch) -> None:
    from dataset.records import update as update_module
    from dataset.records.update import update_dataset_record

    synced = {}

    monkeypatch.setattr(
        update_module,
        "load_dataset",
        lambda: {"Alpha": _make_movie("Alpha", 8.0, 2020)},
    )
    monkeypatch.setattr(update_module, "save_dataset", lambda _data: None)
    monkeypatch.setattr(
        update_module,
        "sync_raw_scores_to_meta",
        lambda title, main_info, raw_scores: synced.update(
            {"title": title, "main_info": main_info, "raw_scores": raw_scores}
        ),
    )

    result = update_dataset_record(
        "Alpha",
        {"raw_scores": {"kp_score": 8.0, "kp_votes": 120000, "imdb_score": 8.0, "imdb_votes": 1200}},
    )

    assert result.ok is True
    assert result.reason == "nothing_changed"
    assert synced["title"] == "Alpha"

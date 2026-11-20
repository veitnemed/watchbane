from config import constant
from config import scheme
from common import format_score


def _make_movie(title: str, user_score: float, year: int) -> dict:
    raw_scores = {
        "tmdb_score": 8.0,
        "tmdb_votes": 1200,
        "tmdb_popularity": 42.5,
    }
    main_info = {"title": title, "user_score": user_score, "year": year, "country": "Россия"}
    return {
        "main_info": main_info,
        "raw_scores": raw_scores,
        "computed_scores": format_score.raw_to_struct(raw_scores, main_info),
    }


def _seed_movie(title, movie):
    from storage.data import save_dataset

    save_dataset({title: movie})


def test_update_dataset_record_preserves_media_type() -> None:
    from dataset.records.update import update_dataset_record
    from storage.data import load_dataset

    movie = _make_movie("Watchmen", 3, 2009)
    movie["main_info"]["media_type"] = "movie"
    _seed_movie("Watchmen", movie)
    result = update_dataset_record("Watchmen", {"main_info": {"user_score": 2}})

    assert result.ok is True
    assert load_dataset()["Watchmen"]["main_info"]["media_type"] == "movie"


def test_update_dataset_record_forbids_rename() -> None:
    from dataset.records.update import update_dataset_record

    _seed_movie("Alpha", _make_movie("Alpha", 3, 2020))
    result = update_dataset_record("Alpha", {"main_info": {"title": "Beta"}})

    assert result.ok is False
    assert result.reason == "title_change_forbidden"


def test_update_dataset_record_syncs_meta_on_raw_only_change() -> None:
    from dataset.records.update import update_dataset_record
    from storage.data import load_meta

    _seed_movie("Alpha", _make_movie("Alpha", 3, 2020))
    result = update_dataset_record(
        "Alpha",
        {"raw_scores": {"tmdb_score": 8.0, "tmdb_votes": 1200, "tmdb_popularity": 42.5}},
    )

    assert result.ok is True
    assert result.reason == "nothing_changed"
    assert load_meta()["Alpha"]["main_info"]["title"] == "Alpha"
    assert load_meta()["Alpha"]["raw_scores"]["tmdb_votes"] == 1200


def test_update_dataset_record_rejects_boolean_raw_score_values() -> None:
    from dataset.records.update import update_dataset_record
    from storage.data import load_dataset, load_meta

    _seed_movie("Alpha", _make_movie("Alpha", 3, 2020))
    before = load_dataset()
    result = update_dataset_record("Alpha", {"raw_scores": {"tmdb_votes": True}})

    assert result.ok is False
    assert result.reason == "invalid_patch"
    assert load_dataset() == before
    assert not load_meta()

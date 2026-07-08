"""Tests for TMDb-only candidate pool import."""

from candidates.sources.tmdb import importer


def _candidate(**overrides) -> dict:
    candidate = {
        "title": "Show",
        "year": 2020,
        "tmdb_id": 101,
        "tmdb_score": 7.8,
        "tmdb_votes": 500,
        "tmdb_popularity": 20.0,
        "genres": ["Drama"],
        "genre_keys": ["drama"],
        "countries": ["RU"],
        "country_codes": ["RU"],
        "description": "Overview",
        "poster_path": "/poster.jpg",
    }
    candidate.update(overrides)
    return candidate


def _patch_importer(monkeypatch, pool: dict, saved: dict) -> None:
    monkeypatch.setattr(importer, "load_candidate_pool", lambda: dict(pool))
    monkeypatch.setattr(importer, "save_candidate_pool", lambda value: saved.update({"pool": value}))
    monkeypatch.setattr(importer, "build_watched_signatures", lambda: set())
    monkeypatch.setattr(importer, "build_dataset_title_keys", lambda: set())
    monkeypatch.setattr(importer, "load_candidate_criteria", lambda: {})
    monkeypatch.setattr(importer, "save_named_criteria", lambda name, criteria: saved.update({"criteria": criteria}))


def test_import_new_tmdb_candidate(monkeypatch) -> None:
    saved = {}
    _patch_importer(monkeypatch, {}, saved)

    stats = importer.import_tmdb_candidates_to_common_pool([_candidate()], criteria_name="pool")

    assert stats["added"] == 1
    assert stats["updated"] == 0
    assert stats["incomplete"] == 0
    candidate = next(iter(saved["pool"].values()))
    assert candidate["source"] == "tmdb"
    assert candidate["source_version"] == 2
    assert candidate["tmdb_id"] == 101
    assert candidate["is_complete"] is True
    assert candidate["final_score"] > 0


def test_import_skips_watched_localized_title(monkeypatch) -> None:
    saved = {}
    dataset = {
        "Во все тяжкие": {
            "main_info": {"title": "Во все тяжкие", "year": 2008},
            "localized": {"en": {"title": "Breaking Bad"}},
            "tmdb_id": 1396,
        }
    }

    monkeypatch.setattr(importer, "load_candidate_pool", lambda: {})
    monkeypatch.setattr(importer, "save_candidate_pool", lambda value: saved.update({"pool": value}))
    monkeypatch.setattr(importer, "load_candidate_criteria", lambda: {})
    monkeypatch.setattr(importer, "save_named_criteria", lambda name, criteria: saved.update({"criteria": criteria}))
    monkeypatch.setattr("storage.data.load_dataset", lambda: dataset)

    stats = importer.import_tmdb_candidates_to_common_pool([
        _candidate(title="Breaking Bad", year=2008, tmdb_id=1396)
    ], criteria_name="pool")

    assert stats["added"] == 0
    assert stats["watched_skipped"] == 1
    assert saved["pool"] == {}


def test_update_old_kp_imdb_candidate_and_strip_old_fields(monkeypatch) -> None:
    saved = {}
    old = _candidate(
        tmdb_score=6.0,
        tmdb_votes=50,
        final_score=0.1,
        kp_score=9.0,
        kp_votes=1000,
        kp_id=1,
        kp_status="done",
        imdb_score=8.0,
        imdb_votes=2000,
        imdb_rating=8.0,
        imdb_genres=["Drama"],
    )
    incoming = _candidate(tmdb_score=8.1, tmdb_votes=700, imdb_id="tt101")
    _patch_importer(monkeypatch, {"show|2020": old}, saved)

    stats = importer.import_tmdb_candidates_to_common_pool([incoming], criteria_name="pool")

    assert stats["updated"] == 1
    assert stats["stripped_external_rating_fields"] >= 8
    candidate = next(iter(saved["pool"].values()))
    assert candidate["tmdb_score"] == 8.1
    assert candidate["imdb_id"] == "tt101"
    for field_name in importer.EXTERNAL_RATING_FIELDS:
        assert field_name not in candidate


def test_conflict_title_year_chooses_better_tmdb_candidate(monkeypatch) -> None:
    saved = {}
    existing = _candidate(tmdb_id=111, tmdb_score=7.0, tmdb_votes=100, final_score=0.2)
    incoming = _candidate(tmdb_id=222, tmdb_score=8.0, tmdb_votes=900)
    _patch_importer(monkeypatch, {"show|2020": existing}, saved)

    stats = importer.import_tmdb_candidates_to_common_pool([incoming], criteria_name="pool")

    assert stats["updated"] == 1
    candidate = next(iter(saved["pool"].values()))
    assert candidate["tmdb_id"] == 222
    assert candidate["tmdb_score"] == 8.0


def test_same_tmdb_id_different_media_type_is_added_as_distinct_candidate(monkeypatch) -> None:
    saved = {}
    existing = _candidate(title="Show", year=2020, media_type="tv", tmdb_id=42)
    incoming = _candidate(title="Movie", year=2021, media_type="movie", tmdb_id=42)
    _patch_importer(monkeypatch, {"show|2020": existing}, saved)

    stats = importer.import_tmdb_candidates_to_common_pool([incoming], criteria_name="pool")

    assert stats["added"] == 1
    assert stats["updated"] == 0
    assert set(saved["pool"]) == {"show|2020", "movie|2021|movie"}
    assert saved["pool"]["show|2020"]["media_type"] == "tv"
    assert saved["pool"]["movie|2021|movie"]["media_type"] == "movie"


def test_same_title_year_different_media_type_is_added_as_distinct_candidate(monkeypatch) -> None:
    saved = {}
    existing = _candidate(title="Watchmen", year=2009, media_type="tv", tmdb_id=1396)
    incoming = _candidate(title="Watchmen", year=2009, media_type="movie", tmdb_id=202)
    _patch_importer(monkeypatch, {"watchmen|2009": existing}, saved)

    stats = importer.import_tmdb_candidates_to_common_pool([incoming], criteria_name="pool")

    assert stats["added"] == 1
    assert stats["updated"] == 0
    assert set(saved["pool"]) == {"watchmen|2009", "watchmen|2009|movie"}


def test_import_builds_tmdb_id_index_once_for_large_batch(monkeypatch) -> None:
    saved = {}
    calls = []
    real_build_index = importer.build_tmdb_id_index

    def fake_build_index(pool):
        calls.append(len(pool))
        return real_build_index(pool)

    candidates = [
        _candidate(title=f"Show {index}", year=2020 + index, tmdb_id=1000 + index)
        for index in range(25)
    ]
    _patch_importer(monkeypatch, {}, saved)
    monkeypatch.setattr(importer, "build_tmdb_id_index", fake_build_index)

    stats = importer.import_tmdb_candidates_to_common_pool(candidates, criteria_name="pool")

    assert stats["added"] == 25
    assert len(saved["pool"]) == 25
    assert calls == [0]


def test_candidate_with_imdb_id_but_no_imdb_score_saved_correctly(monkeypatch) -> None:
    saved = {}
    _patch_importer(monkeypatch, {}, saved)

    stats = importer.import_tmdb_candidates_to_common_pool([
        _candidate(tmdb_id=None, imdb_id="tt999", title="No TMDb", year=2022)
    ], criteria_name="pool")

    assert stats["added"] == 1
    assert stats["incomplete"] == 1
    candidate = next(iter(saved["pool"].values()))
    assert candidate["imdb_id"] == "tt999"
    assert "imdb_score" not in candidate
    assert "imdb_votes" not in candidate
    assert candidate["is_complete"] is False
    assert candidate["missing_fields"] == ["tmdb_id"]

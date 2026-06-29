import copy

from config import constant
from config import scheme
from common import format_score


def _make_movie(title: str, user_score: float, year: int, raw_score: float = 8.0) -> dict:
    tags_vibe = {feature: 0 for feature in constant.TAGS_VIBE}
    genre_tags = {feature: 0 for feature in constant.GENRE}

    return {
        "main_info": {
            "title": title,
            "user_score": user_score,
            "year": year,
        },
        "raw_scores": {
            "kp_score": raw_score,
            "kp_votes": 120000,
            "imdb_score": raw_score,
            "imdb_votes": 1200,
        },
        "computed_scores": format_score.raw_to_struct(
            {
                "kp_score": raw_score,
                "kp_votes": 120000,
                "imdb_score": raw_score,
                "imdb_votes": 1200,
            },
            {
                "title": title,
                "user_score": user_score,
                "year": year,
            },
        ),
        scheme.TAGS_VIBE: tags_vibe,
        constant.GENRE_SECTION: genre_tags,
    }


def test_build_diagnostic_query_variants() -> None:
    from posters.tmdb_diagnostic import build_diagnostic_query_variants

    variants = build_diagnostic_query_variants('Слово пацана. Кровь на асфалте')

    assert 'Слово пацана. Кровь на асфалте' in variants
    assert any('асфалте' not in variant or variant == 'Слово пацана' for variant in variants)
    assert 'Слово пацана' in variants


def test_explain_candidate_rejection_year_mismatch() -> None:
    from posters.tmdb_diagnostic import explain_candidate_rejection

    result = {
        "id": 1,
        "name": "Show",
        "original_name": "Show",
        "first_air_date": "2015-01-01",
    }

    reason = explain_candidate_rejection("Show", 2020, result)

    assert reason == "year_mismatch"


def test_explain_candidate_rejection_title_mismatch() -> None:
    from posters.tmdb_diagnostic import explain_candidate_rejection

    result = {
        "id": 2,
        "name": "Other",
        "original_name": "Other",
        "first_air_date": "2020-01-01",
    }

    reason = explain_candidate_rejection("Show", 2020, result)

    assert reason == "title_mismatch"


def test_explain_candidate_rejection_multiple_candidates() -> None:
    from posters.tmdb_diagnostic import explain_candidate_rejection

    first = {"id": 1, "name": "Show", "original_name": "Show", "first_air_date": "2020-01-01"}
    second = {"id": 2, "name": "Show", "original_name": "Show", "first_air_date": "2020-06-01"}

    reason = explain_candidate_rejection(
        "Show",
        2020,
        first,
        matched=[first, second],
        match_status="uncertain_match",
    )

    assert reason == "multiple_candidates"


def test_diagnose_watched_tmdb_unresolved_shows_candidates(monkeypatch) -> None:
    from posters import tmdb_diagnostic as module

    dataset = {"Alpha": _make_movie("Alpha", 8.0, 2020)}
    meta = {
        "Alpha": {
            "main_info": dataset["Alpha"]["main_info"],
            "raw_scores": dataset["Alpha"]["raw_scores"],
        }
    }

    def fake_search(query: str):
        if query == "Alpha":
            return [
                {
                    "id": 101,
                    "name": "Alpha",
                    "original_name": "Alpha",
                    "first_air_date": "2018-01-01",
                    "overview": "Alpha overview",
                    "poster_path": "/alpha.jpg",
                }
            ]
        return []

    monkeypatch.setattr(module.storage_data, "load_dataset", lambda: copy.deepcopy(dataset))
    monkeypatch.setattr(module.storage_data, "load_meta", lambda: copy.deepcopy(meta))
    monkeypatch.setattr(module, "load_poster_cache", lambda: {})
    monkeypatch.setattr(module, "load_watched_tmdb_overrides", lambda: {})

    report = module.diagnose_watched_tmdb_unresolved(search_func=fake_search, details_func=lambda _id: {})

    assert report["total_unresolved"] == 1
    entry = report["entries"][0]
    assert entry["dataset_title"] == "Alpha"
    assert entry["reason"] == "not_found"
    assert len(entry["candidates"]) == 1
    assert entry["candidates"][0]["tmdb_id"] == 101
    assert entry["candidates"][0]["rejection_reason"] == "year_mismatch"
    assert '"alpha|2020"' in entry["candidates"][0]["override_snippet"]


def test_diagnose_watched_tmdb_unresolved_does_not_write_data(monkeypatch) -> None:
    from posters import tmdb_diagnostic as module

    dataset = {"Alpha": _make_movie("Alpha", 8.0, 2020)}
    meta = {"Alpha": {"main_info": dataset["Alpha"]["main_info"], "raw_scores": dataset["Alpha"]["raw_scores"]}}

    writes = {"dataset": False, "meta": False, "cache": False}

    monkeypatch.setattr(module.storage_data, "load_dataset", lambda: copy.deepcopy(dataset))
    monkeypatch.setattr(module.storage_data, "load_meta", lambda: copy.deepcopy(meta))
    monkeypatch.setattr(module, "load_poster_cache", lambda: {})
    monkeypatch.setattr(module, "load_watched_tmdb_overrides", lambda: {})
    monkeypatch.setattr(module.storage_data, "save_dataset", lambda _payload: writes.__setitem__("dataset", True))
    monkeypatch.setattr(module.storage_data, "save_meta", lambda _payload: writes.__setitem__("meta", True))

    module.diagnose_watched_tmdb_unresolved(search_func=lambda _query: [], details_func=lambda _id: {})

    assert writes == {"dataset": False, "meta": False, "cache": False}


def test_diagnose_watched_tmdb_unresolved_dataset_unchanged(monkeypatch) -> None:
    from posters import tmdb_diagnostic as module

    dataset = {"Alpha": _make_movie("Alpha", 8.0, 2020)}
    original = copy.deepcopy(dataset)

    monkeypatch.setattr(module.storage_data, "load_dataset", lambda: dataset)
    monkeypatch.setattr(module.storage_data, "load_meta", lambda: {})
    monkeypatch.setattr(module, "load_poster_cache", lambda: {})
    monkeypatch.setattr(module, "load_watched_tmdb_overrides", lambda: {})

    module.diagnose_watched_tmdb_unresolved(search_func=lambda _query: [], details_func=lambda _id: {})

    assert dataset == original


def test_format_watched_tmdb_diagnostic_report_contains_variants() -> None:
    from posters.tmdb_diagnostic import format_watched_tmdb_diagnostic_report

    report = {
        "total_checked": 1,
        "total_unresolved": 1,
        "entries": [
            {
                "dataset_title": "Alpha",
                "dataset_year": 2020,
                "search_query": "Alpha",
                "reason": "uncertain_match",
                "query_variants": [
                    {"query": "Alpha", "result_count": 2, "matched_count": 2, "is_primary": True},
                ],
                "candidates": [
                    {
                        "tmdb_id": 101,
                        "name": "Alpha",
                        "original_name": "Alpha",
                        "first_air_date": "2020-01-01",
                        "calculated_year": 2020,
                        "has_poster_path": True,
                        "overview": "Test",
                        "rejection_reason": "multiple_candidates",
                        "override_snippet": '"alpha|2020": {\n  "tmdb_id": 101,\n  "media_type": "tv",\n  "note": "manual confirmed"\n}',
                    }
                ],
            }
        ],
    }

    text = format_watched_tmdb_diagnostic_report(report)

    assert "uncertain_match" in text
    assert "query variants" in text
    assert "override snippet" in text
    assert "multiple_candidates" in text

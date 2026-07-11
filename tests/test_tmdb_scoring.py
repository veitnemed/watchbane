"""Tests for TMDb-only candidate scoring."""

from candidates.scoring.sort_keys import candidate_sort_score, dedupe_ranked_candidates_by_title_identity
from candidates.sources.tmdb.scoring import (
    compute_metadata_completeness_score,
    compute_tmdb_bayesian_rating,
    compute_tmdb_final_score,
    compute_tmdb_quality_score,
    compute_tmdb_vote_reliability,
)
from candidates.scoring.rating_confidence import candidate_rating_confidence


def _candidate(**overrides) -> dict:
    candidate = {
        "title": "Show",
        "year": 2020,
        "tmdb_id": 101,
        "tmdb_score": 7.8,
        "tmdb_votes": 300,
        "tmdb_popularity": 20.0,
        "country_codes": ["RU"],
        "genres": ["Drama"],
        "description": "Overview",
        "poster_path": "/poster.jpg",
        "content_rating": "18+",
        "actors_top": [{"name": "Actor"}],
        "keywords": ["detective"],
        "networks": ["Channel One"],
        "first_air_date": "2020-01-01",
        "imdb_id": "tt101",
    }
    candidate.update(overrides)
    return candidate


def test_ru_show_with_20_votes_gets_moderate_score() -> None:
    candidate = _candidate(tmdb_score=8.0, tmdb_votes=20, country_codes=["RU"], tmdb_popularity=8.0)

    assert compute_tmdb_bayesian_rating(candidate) > 0.70
    assert compute_tmdb_vote_reliability(candidate) > 0.45
    assert 0.55 < compute_tmdb_quality_score(candidate) < 0.85


def test_tiny_vote_count_high_rating_is_not_absolute_top() -> None:
    tiny_sample = _candidate(
        title="Tiny",
        tmdb_score=9.5,
        tmdb_votes=2,
        tmdb_popularity=20.0,
        country_codes=["US"],
    )
    reliable = _candidate(
        title="Reliable",
        tmdb_score=7.8,
        tmdb_votes=2000,
        tmdb_popularity=60.0,
        country_codes=["US"],
    )

    assert compute_tmdb_quality_score(tiny_sample) < compute_tmdb_quality_score(reliable)
    assert compute_tmdb_final_score(tiny_sample) <= 0.44


def test_zero_vote_ru_candidate_is_not_ranked_as_strong_evidence() -> None:
    zero_votes = _candidate(
        title="Zero",
        tmdb_score=0.0,
        tmdb_votes=0,
        tmdb_popularity=20.0,
        country_codes=["RU"],
    )
    moderate = _candidate(
        title="Moderate",
        tmdb_score=8.0,
        tmdb_votes=20,
        tmdb_popularity=8.0,
        country_codes=["RU"],
    )

    assert compute_tmdb_quality_score(zero_votes) < 0.45
    assert compute_tmdb_final_score(zero_votes) < compute_tmdb_final_score(moderate)


def test_zero_votes_make_rating_unknown_instead_of_treating_zero_as_bad_rating() -> None:
    zero_rating = _candidate(tmdb_score=0.0, tmdb_votes=0, country_codes=["US"])
    placeholder_rating = _candidate(tmdb_score=9.9, tmdb_votes=0, country_codes=["US"])

    assert candidate_rating_confidence(zero_rating) == "unknown"
    assert compute_tmdb_bayesian_rating(zero_rating) == compute_tmdb_bayesian_rating(placeholder_rating)
    assert compute_tmdb_quality_score(zero_rating) == compute_tmdb_quality_score(placeholder_rating)


def test_low_rating_few_votes_is_below_moderate_ru_candidate() -> None:
    weak = _candidate(
        title="Weak",
        tmdb_score=3.0,
        tmdb_votes=3,
        tmdb_popularity=50.0,
        country_codes=["RU"],
    )
    moderate = _candidate(
        title="Moderate",
        tmdb_score=7.5,
        tmdb_votes=20,
        tmdb_popularity=8.0,
        country_codes=["RU"],
    )

    assert compute_tmdb_final_score(weak) <= 0.44
    assert compute_tmdb_final_score(weak) < compute_tmdb_final_score(moderate)


def test_reliable_show_gets_high_score() -> None:
    candidate = _candidate(tmdb_score=7.8, tmdb_votes=2000, tmdb_popularity=60.0, country_codes=["US"])

    assert compute_tmdb_vote_reliability(candidate) == 1.0
    assert compute_metadata_completeness_score(candidate) >= 0.9
    assert compute_tmdb_quality_score(candidate) > 0.75


def test_duplicate_tiebreak_prefers_better_tmdb_final_score() -> None:
    weak = _candidate(title="Same", final_score=0.62, quality_score=0.7, tmdb_score=8.2, tmdb_votes=100)
    strong = _candidate(title="Same", final_score=0.82, quality_score=0.72, tmdb_score=7.9, tmdb_votes=80)

    assert candidate_sort_score(strong) > candidate_sort_score(weak)


def test_search_dedupe_keeps_same_title_year_with_different_media_type() -> None:
    series = _candidate(title="Watchmen", year=2009, media_type="tv", quality_score=0.7)
    movie = _candidate(title="Watchmen", year=2009, media_type="movie", quality_score=0.8)

    deduped = dedupe_ranked_candidates_by_title_identity([series, movie])

    assert {candidate["media_type"] for candidate in deduped} == {"tv", "movie"}


def test_final_score_quality_mode_uses_tmdb_only_signals() -> None:
    candidate = _candidate(tmdb_score=8.0, tmdb_votes=20, country_codes=["RU"])
    candidate["quality_score"] = compute_tmdb_quality_score(candidate)

    assert compute_tmdb_final_score(candidate, mode="quality") > 0.6

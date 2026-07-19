"""C3-07: explicit sexual content safety gate for recommendation eligibility."""

from __future__ import annotations

from datetime import datetime, timezone

from candidates.models.keys import candidate_state_identity_key
from candidates.recommendation_deck_service import RecommendationDeckService
from candidates.safety.explicit_content import (
    REASON_ADULT_FLAG,
    REASON_EXPLICIT_CONTENT_RATING,
    REASON_EXPLICIT_KEYWORD,
    REASON_EXPLICIT_PHRASE,
    evaluate_explicit_sexual_content,
    is_blocked_explicit_sexual_content,
)
from candidates import title_state_service


NOW = datetime(2026, 7, 19, 12, 0, tzinfo=timezone.utc)

# Regression fixture for QA-DEFECT-01 (TMDb 95897 «Переполнение» / Overflow).
# adult/content_rating null as in audit; structural keywords still present after details.
OVERFLOW_95897 = {
    "title": "Переполнение",
    "original_title": "Overflow",
    "year": 2020,
    "media_type": "tv",
    "tmdb_id": 95897,
    "adult": None,
    "content_rating": None,
    "overview": (
        "Kazushi Sudou is a university student who is visited by his two childhood friends, "
        "the sisters Ayane and Kotone Shirakawa. When Ayane discovers that Kazushi not only "
        "forgot to buy her pudding but is also using her special lotion in the bath, she "
        "decides to take revenge and join Kazushi in his bath along with Kotone. Will the "
        "perverted Kazushi be able to remain indifferent to them both?"
    ),
    "description": "",
    "keywords": [
        "romance",
        "softcore",
        "hentai",
        "anime",
        "erotic",
        "animated porn",
    ],
    "genres": ["Animation", "Romance"],
    "genre_keys": ["animation", "romance"],
    "country_codes": ["JP"],
    "tmdb_score": 7.4,
    "tmdb_votes": 89,
    "tmdb_popularity": 12.0,
    "final_score": 90,
    "poster_path": "/overflow.jpg",
}


def _safe_base(index: int, *, title: str | None = None) -> dict:
    return {
        "title": title or f"Safe Title {index:03d}",
        "year": 2000 + (index % 20),
        "media_type": "tv" if index % 2 else "movie",
        "tmdb_id": 50_000 + index,
        "adult": False,
        "content_rating": "TV-14",
        "overview": "A thoughtful drama about friendship and growing up.",
        "keywords": ["friendship", "drama"],
        "genres": ["Drama"],
        "genre_keys": ["drama"],
        "country_codes": ["US"],
        "tmdb_score": 8.0,
        "tmdb_votes": 500 + index,
        "tmdb_popularity": 40.0,
        "final_score": 80 - (index % 10),
        "poster_path": f"/safe-{index}.jpg",
    }


def _service(pool: dict, db_path) -> RecommendationDeckService:
    return RecommendationDeckService(pool_loader=lambda: pool, db_path=db_path)


def _deck_titles(deck: dict) -> set[str]:
    return {item["title"] for item in deck["active"] + deck["reserve"]}


def _deck_tmdb_ids(deck: dict) -> set[int]:
    return {
        int(item["tmdb_id"])
        for item in deck["active"] + deck["reserve"]
        if item.get("tmdb_id") is not None
    }


def test_positive_explicit_keyword_blocks() -> None:
    candidate = {
        **_safe_base(1, title="Blocked Softcore"),
        "keywords": ["softcore", "drama"],
        "adult": None,
        "content_rating": None,
    }
    decision = evaluate_explicit_sexual_content(candidate)
    assert decision.blocked is True
    assert decision.reason_code == REASON_EXPLICIT_KEYWORD
    assert any(signal.startswith("keyword:") for signal in decision.signals)


def test_regression_tmdb_95897_overflow_blocked_despite_null_adult() -> None:
    decision = evaluate_explicit_sexual_content(OVERFLOW_95897)
    assert OVERFLOW_95897["adult"] is None
    assert OVERFLOW_95897["content_rating"] is None
    assert decision.blocked is True
    assert decision.reason_code == REASON_EXPLICIT_KEYWORD
    assert is_blocked_explicit_sexual_content(OVERFLOW_95897) is True


def test_adult_flag_blocks_alone() -> None:
    candidate = {**_safe_base(2), "adult": True, "keywords": [], "overview": "Wholesome picnic."}
    decision = evaluate_explicit_sexual_content(candidate)
    assert decision.blocked is True
    assert decision.reason_code == REASON_ADULT_FLAG


def test_explicit_content_rating_blocks() -> None:
    candidate = {
        **_safe_base(3),
        "adult": None,
        "content_rating": "NC-17",
        "keywords": [],
        "overview": "Intense crime drama.",
    }
    decision = evaluate_explicit_sexual_content(candidate)
    assert decision.blocked is True
    assert decision.reason_code == REASON_EXPLICIT_CONTENT_RATING


def test_strong_phrase_blocks() -> None:
    candidate = {
        **_safe_base(4),
        "adult": None,
        "content_rating": None,
        "keywords": [],
        "overview": "This series features graphic sex in every episode.",
    }
    decision = evaluate_explicit_sexual_content(candidate)
    assert decision.blocked is True
    assert decision.reason_code == REASON_EXPLICIT_PHRASE


def test_negative_ordinary_romance_animation_remains_eligible() -> None:
    candidate = {
        **_safe_base(10, title="Ordinary Romance Anime"),
        "media_type": "tv",
        "adult": None,
        "content_rating": "TV-14",
        "overview": (
            "Two classmates slowly fall in love over a school year. "
            "They share quiet evenings and honest conversations."
        ),
        "keywords": ["romance", "school", "anime"],
        "genres": ["Animation", "Romance"],
        "genre_keys": ["animation", "romance"],
        "country_codes": ["JP"],
    }
    decision = evaluate_explicit_sexual_content(candidate)
    assert decision.blocked is False
    assert decision.reason_code is None


def test_negative_same_sex_romance_not_auto_blocked() -> None:
    candidate = {
        **_safe_base(11, title="Same-Sex Romance"),
        "adult": None,
        "content_rating": "TV-14",
        "overview": (
            "Two men rebuild their friendship into a gentle romantic relationship. "
            "The story focuses on trust, family, and everyday life together."
        ),
        "keywords": ["lgbt", "romance", "gay relationship"],
        "genres": ["Drama", "Romance"],
        "genre_keys": ["drama", "romance"],
    }
    decision = evaluate_explicit_sexual_content(candidate)
    assert decision.blocked is False


def test_negative_ambiguous_words_without_explicit_context_not_blocked() -> None:
    candidate = {
        **_safe_base(12, title="Ambiguous Bath Story"),
        "adult": None,
        "content_rating": None,
        "keywords": ["drama"],
        "overview": (
            "После долгого дня герой наполнил ванну, ощутил тепло тела в воде "
            "и лёг в постель. Врач обнажил рану на руке для осмотра."
        ),
    }
    decision = evaluate_explicit_sexual_content(candidate)
    assert decision.blocked is False
    assert decision.reason_code is None


def test_tv_ma_alone_does_not_block() -> None:
    candidate = {
        **_safe_base(13),
        "content_rating": "TV-MA",
        "keywords": ["crime", "thriller"],
        "overview": "A dark thriller about a detective and a serial killer.",
    }
    assert evaluate_explicit_sexual_content(candidate).blocked is False


def test_deck_excludes_blocked_from_active_and_reserve(tmp_path) -> None:
    pool = {f"safe-{i}": _safe_base(i) for i in range(15)}
    pool["overflow"] = {**OVERFLOW_95897, "final_score": 99, "tmdb_popularity": 99.0}
    deck = _service(pool, tmp_path / "deck.sqlite3").build_deck({}, NOW)

    assert 95897 not in _deck_tmdb_ids(deck)
    assert "Переполнение" not in _deck_titles(deck)
    assert int(deck["excluded"]["explicit_content"]) >= 1


def test_deck_still_fills_to_ten_with_safe_candidates(tmp_path) -> None:
    pool = {f"safe-{i}": _safe_base(i) for i in range(20)}
    pool["overflow"] = {**OVERFLOW_95897, "final_score": 99}
    deck = _service(pool, tmp_path / "deck.sqlite3").build_deck({}, NOW, limit_active=10, reserve_size=5)

    assert len(deck["active"]) == 10
    assert 95897 not in _deck_tmdb_ids(deck)
    assert all(int(item["tmdb_id"]) != 95897 for item in deck["reserve"])


def test_watched_hidden_filtering_not_regressed(tmp_path) -> None:
    db_path = tmp_path / "deck.sqlite3"
    pool = {f"safe-{i}": _safe_base(i) for i in range(20)}
    watched = pool["safe-0"]
    hidden = pool["safe-1"]
    title_state_service.mark_watched(watched, path=db_path)
    title_state_service.hide_candidate(hidden, path=db_path)

    deck = _service(pool, db_path).build_deck({}, NOW, limit_active=30, reserve_size=10)
    shown = {candidate_state_identity_key(item) for item in deck["active"] + deck["reserve"]}

    assert candidate_state_identity_key(watched) not in shown
    assert candidate_state_identity_key(hidden) not in shown
    assert int(deck["excluded"]["watched"]) >= 1
    assert int(deck["excluded"]["actioned"]) >= 1


def test_isolated_qa_defect_01_safety_scenario_passes_twice(tmp_path) -> None:
    """Local 2/2 replay of C3-05 QA-DEFECT-01 DEFAULT eligibility after thinning."""
    for pass_index in (1, 2):
        pool = {f"safe-{i}": _safe_base(i) for i in range(12)}
        # High-score explicit title would otherwise enter after popular thinning.
        pool["overflow"] = {
            **OVERFLOW_95897,
            "final_score": 100,
            "tmdb_score": 9.9,
            "tmdb_votes": 10_000,
            "tmdb_popularity": 200.0,
        }
        deck = _service(pool, tmp_path / f"pass-{pass_index}.sqlite3").build_deck(
            {},
            NOW,
            limit_active=10,
            reserve_size=10,
        )
        assert 95897 not in _deck_tmdb_ids(deck), f"pass {pass_index} leaked Overflow"
        assert int(deck["excluded"]["explicit_content"]) >= 1
        assert len(deck["active"]) == 10

from __future__ import annotations

from datetime import datetime, timezone

from candidates.recommendation_deck_service import (
    ProductionEligibilityContext,
    RecommendationDeckService,
    evaluate_production_eligibility,
)
from storage.sqlite.candidate_pool_repository import merge_candidate_pool_dict
from tests.helpers.candidate_factory import as_pool, safe_movie
from tools.qa.candidate_pool_cleanliness_audit import (
    PoolAuditState,
    audit_candidate_pool,
    load_audit_state_read_only,
    load_pool_read_only,
)


NOW = datetime(2026, 7, 26, tzinfo=timezone.utc)


def _state() -> PoolAuditState:
    return PoolAuditState(set(), set(), set(), set(), set(), set(), set())


def _candidate(tmdb_id: int, title: str, **overrides: object) -> dict[str, object]:
    candidate = safe_movie()
    candidate.update({"tmdb_id": tmdb_id, "title": title, "original_title": title})
    candidate.update(overrides)
    return candidate


def test_audit_classifies_hard_garbage_without_making_metadata_missing_garbage() -> None:
    pool = as_pool(
        _candidate(1, "Valid"),
        _candidate(0, "Invalid id"),
        _candidate(2, "Invalid type", media_type="podcast"),
        _candidate(3, "Untitled"),
        _candidate(4, "Duplicate first"),
        _candidate(4, "Duplicate second"),
        _candidate(5, "Explicit", adult=True),
        _candidate(6, "Reality", genre_keys=["reality"]),
        _candidate(
            7, "Metadata only", poster_path="", overview="", description="",
            year=None, genres=[], countries=[], country_codes=[], country="", runtime=None,
            content_rating="", keywords=[],
        ),
    )

    report = audit_candidate_pool(pool, state=_state(), now=NOW)

    assert report["summary"]["pool_total"] == 9
    assert report["reason_counts"]["invalid_tmdb_id"] == 1
    assert report["reason_counts"]["invalid_media_type"] == 1
    assert report["reason_counts"]["unusable_title"] == 1
    assert report["reason_counts"]["duplicate_identity"] == 1
    assert report["reason_counts"]["explicit_content"] == 1
    assert report["reason_counts"]["hard_drop_genre"] == 1
    metadata = next(item for item in report["candidate_findings"] if item["title"] == "Metadata only")
    assert metadata["hard_garbage_reasons"] == []
    assert metadata["production_eligibility"] is True
    assert {"poster", "overview", "year", "genres", "countries", "runtime", "content_rating", "keywords"} <= set(metadata["missing_fields"])


def test_extracted_evaluator_preserves_deck_eligibility_contract(tmp_path) -> None:
    valid = _candidate(101, "Valid")
    explicit = _candidate(102, "Explicit", adult=True)
    duplicate = _candidate(101, "Valid copy")
    pool = {"valid": valid, "explicit": explicit, "duplicate": duplicate}
    context = ProductionEligibilityContext({}, NOW, set(), set(), set(), set(), set(), set(), set())
    decisions = []
    for candidate in pool.values():
        decision = evaluate_production_eligibility(candidate, context)
        decisions.append(decision)
        if decision.track_identity and decision.stable_identity is not None:
            context.seen.add(decision.stable_identity)
            context.seen_aliases.update(decision.aliases)
    deck = RecommendationDeckService(pool_loader=lambda: pool, db_path=tmp_path / "deck.sqlite3").build_deck({}, NOW, limit_active=10, reserve_size=0)

    assert [decision.reason_code for decision in decisions] == [None, "explicit_content", "duplicate"]
    assert [item["title"] for item in deck["active"]] == ["Valid"]
    assert deck["excluded"]["explicit_content"] == 1
    assert deck["excluded"]["duplicate"] == 1


def test_read_only_audit_does_not_modify_runtime_database(tmp_path) -> None:
    db_path = tmp_path / "watchbane.sqlite3"
    pool = as_pool(_candidate(200, "Stored"))
    merge_candidate_pool_dict(pool, path=db_path)
    before = db_path.read_bytes()

    state = load_audit_state_read_only(db_path, now=NOW)
    report = audit_candidate_pool(load_pool_read_only(db_path), state=state, now=NOW)

    assert report["summary"]["pool_total"] == 1
    assert db_path.read_bytes() == before

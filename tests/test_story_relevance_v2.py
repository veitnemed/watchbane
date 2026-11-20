import pytest

from tools.qa.evaluate_story_relevance import score_v2


def test_coverage_and_rank_separate_from_behavior():
    cases = [
        {"id": "clean", "group": "clean", "full": ["tmdb:tv:1"]},
        {"id": "missing", "group": "clean", "full": ["tmdb:tv:2"]},
        {"id": "name", "group": "wrong_name", "full": ["tmdb:movie:1"]},
        {"id": "ambiguous", "group": "ambiguous"},
        {"id": "near", "group": "near"},
        {"id": "ood", "group": "ood"},
    ]
    film, tv = "tmdb:movie:1", "tmdb:tv:1"
    ranks = {"clean": [film, tv], "missing": [], "name": [film], "ambiguous": [],
             "near": [tv], "ood": []}
    report = score_v2(cases, ranks, {film, tv}, annotations={
        "name": {"action": "RESULTS", "discrepancy_explicit": True,
                 "supported_suggestion": True, "confident_error": False},
        "ambiguous": {"action": "CLARIFY", "focused": True, "confident_error": False},
        "near": {"action": "RESULTS", "scoped_partial": True, "confident_error": True},
    })
    grouped = report["groups"]
    assert grouped["clean"]["covered"] == grouped["clean"]["hit_5"] == 1
    assert grouped["clean"]["hit_1"] == 0
    assert grouped["clean"]["mrr"] == 0.5
    assert report["cases"][1]["missing_titles"] == ["tmdb:tv:2"]
    assert grouped["wrong_name"]["behavior_pass"] == grouped["ambiguous"]["behavior_pass"] == 1
    assert grouped["near"]["confident_errors"] == 1 and grouped["near"]["behavior_pass"] == 0
    assert grouped["ood"]["cases_without_cards"] == 1 and grouped["ood"]["unreviewed"] == 1


def test_ood_notice_requires_no_cards_and_explicit_scope_review():
    case = {"id": "ood", "group": "ood"}
    correct = {"ood": {"action": "NO_MATCH", "scope_notice": True}}
    known = {"tmdb:tv:1"}
    assert score_v2([case], {"ood": []}, known, annotations=correct)["cases"][0]["behavior_pass"]
    returned = score_v2([case], {"ood": ["tmdb:tv:1"]}, known, annotations=correct)
    assert not returned["cases"][0]["behavior_pass"]


def test_review_labels_reject_unknown_flags_or_case_ids():
    cases, ranked = [{"id": "a", "group": "ambiguous"}], {"a": []}
    for annotation in ({"b": {"action": "CLARIFY"}}, {"a": {"action": "CLARIFY", "focused": "maybe"}}):
        with pytest.raises(ValueError):
            score_v2(cases, ranked, set(), annotations=annotation)


def test_missing_name_judgment_not_inferred_from_exact_id():
    film = "tmdb:movie:1"
    cases = [{"id": "w", "group": "wrong_name", "full": [film]}]
    ranked = {"w": [film]}
    row = score_v2(cases, ranked, {film}, limit=1)
    assert row["groups"]["wrong_name"]["hit_1"] == 1
    assert row["cases"][0]["behavior_pass"] is None

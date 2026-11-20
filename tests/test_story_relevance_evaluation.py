import pytest

from tools.qa.evaluate_story_relevance import score


def test_score_distinguishes_retrieval_miss_missing_title_and_random_cards():
    cases = [
        {"id": "hit", "expect": "match", "full": ["tv:a"]},
        {"id": "miss", "expect": "match", "full": ["tv:b"]},
        {"id": "missing", "expect": "match", "full": ["tv:c"]},
        {"id": "trap", "expect": "uncertain", "traps": ["movie:a"]},
        {"id": "ood", "expect": "no_match"},
    ]
    evaluated = score(cases, {
        "hit": ["movie:a", "tv:a"], "miss": ["tv:a"], "missing": [],
        "trap": ["movie:a"], "ood": ["tv:a"],
    }, {"movie:a", "tv:a", "tv:b"})
    assert evaluated["counts"]["positive_cases"] == 3
    assert evaluated["counts"]["positive_cases_covered"] == 2
    assert evaluated["counts"]["hit_1"] == 0
    assert evaluated["counts"]["hit_5"] == 1
    assert evaluated["counts"]["negative_no_match_with_cards"] == 1
    assert evaluated["counts"]["uncertain_cases_with_cards"] == 1
    assert evaluated["cases"][0]["first_full_rank"] == 2
    assert evaluated["cases"][2]["missing_titles"] == ["tv:c"]
    assert evaluated["cases"][3]["annotated_traps_returned"] == ["movie:a"]


def test_score_rejects_duplicate_ids():
    with pytest.raises(ValueError, match="duplicate or unknown title"):
        score([{"id": "a", "expect": "no_match"}], {"a": ["a", "a"]}, {"a"})


def test_score_limit_one_counts_first_hit_once():
    actual = score([{"id": "a", "expect": "match", "full": ["a"]}], {"a": ["a"]}, {"a"}, limit=1)
    assert actual["counts"]["hit_1"] == 1

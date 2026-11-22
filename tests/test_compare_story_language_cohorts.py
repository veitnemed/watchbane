from dataclasses import replace
from hashlib import sha256
import json

import pytest

from tools.qa.compare_story_language_cohorts import LanguageCohorts, plan_cohorts, score_cohorts
from web.story_catalog_multilingual import FORMAT


def _fixture(tmp_path):
    rows = [{"format": FORMAT}]
    for media, number, locale, original in (
        ("tv", 1, "en-US", "ru"),
        ("movie", 1, "ru-RU", "en"),
        ("tv", 3, "en-GB", "en"),
        ("movie", 4, "ko-KR", "ru"),
    ):
        overview = f"synthetic {locale} overview"
        rows.append({
            "id": f"tmdb:{media}:{number}", "media_type": media, "tmdb_id": number,
            "title": "Synthetic", "overview": overview, "year": 2000, "original_language": original,
            "synopsis_locale": locale,
            "evidence": {"source": "provider_translation_record", "provider_locale": locale,
                         "synopsis_sha256": sha256(overview.encode()).hexdigest()},
        })
    raw = "".join(json.dumps(row) + "\n" for row in rows).encode()
    path = tmp_path / "private-fixture.jsonl"
    path.write_bytes(raw)
    return path, sha256(raw).hexdigest()


def test_nested_compared_cohorts_do_not_confuse_numeric_ids_or_coverage_with_rank(tmp_path):
    file, pin = _fixture(tmp_path)
    cohort = plan_cohorts(file, expected_sha256=pin)
    assert [r.key for r in cohort.baseline] == ["tmdb:movie:1"]
    assert [r.key for r in cohort.expanded] == ["tmdb:movie:1", "tmdb:tv:1"]
    assert cohort.baseline[0] is cohort.expanded[0]
    truth = {"common": "tmdb:movie:1", "new": "tmdb:tv:1", "absent": "tmdb:tv:3", "unverified": None}
    movie, tv = "tmdb:movie:1", "tmdb:tv:1"
    a = {"common": [movie], "new": [], "absent": [movie], "unverified": []}
    b = {"common": [tv, movie], "new": [tv], "absent": [], "unverified": [movie]}
    assert score_cohorts(cohort, truth=truth, ranked_a=a, ranked_b=b) == {
        "catalog_a": 1, "catalog_b": 2,
        "paired": {"cases": 1, "a_top1": 1, "a_top5": 1, "b_top1": 0, "b_top5": 1},
        "expanded_only": {"cases": 1, "b_top1": 1, "b_top5": 1},
        "absent": {"cases": 1, "a_with_cards": 1, "b_with_cards": 0},
        "without_verified_target": {"cases": 1, "a_with_cards": 0, "b_with_cards": 1},
    }


def test_explicit_locale_and_file_pin_are_enforced(tmp_path):
    file, pin = _fixture(tmp_path)
    assert plan_cohorts(file, expected_sha256=pin, english_locales=("en-GB",)).expanded[-1].key == "tmdb:tv:3"
    for tags in ((), ("ko-KR",), ("EN-us",), ("en-US", "en-US")):
        with pytest.raises(ValueError, match="English locale"):
            plan_cohorts(file, expected_sha256=pin, english_locales=tags)
    with pytest.raises(ValueError, match="eligible description"):
        plan_cohorts(file, expected_sha256=pin, english_locales=("en-AU",))
    with pytest.raises(ValueError, match="SHA-256"):
        plan_cohorts(file, expected_sha256="0" * 64)


def test_join_rejects_substitution_replay_and_foreign_results(tmp_path):
    file, pin = _fixture(tmp_path)
    plan = plan_cohorts(file, expected_sha256=pin)
    movie, tv = "tmdb:movie:1", "tmdb:tv:1"
    truth = {"q": movie}
    for bad in ({}, {"different": []}, {"q": [tv]}, {"q": [movie, movie]}):
        with pytest.raises(ValueError, match="Rankings"):
            score_cohorts(plan, truth=truth, ranked_a=bad, ranked_b={"q": []})
    changed = replace(plan.baseline[0], overview="different")
    switched = LanguageCohorts(plan.baseline, (changed, plan.expanded[1]))
    with pytest.raises(ValueError, match="identical RU"):
        score_cohorts(switched, truth=truth, ranked_a={"q": []}, ranked_b={"q": []})
    with pytest.raises(ValueError, match="typed targets"):
        score_cohorts(plan, truth={"q": "tmdb:movie:01"}, ranked_a={"q": []}, ranked_b={"q": []})


def test_http_outcomes_keep_equal_totals_failures_and_non_targets_distinct(tmp_path):
    from tools.qa.compare_story_language_cohorts import score_cohort_outcomes

    file, pin = _fixture(tmp_path)
    cohort = plan_cohorts(file, expected_sha256=pin)
    movie, tv = "tmdb:movie:1", "tmdb:tv:1"
    frozen = {case: ("known_target", movie)
              for case in ("lost", "gained", "both", "neither", "failed")}
    frozen.update({"new": ("known_target", tv), "absent": ("known_target", "tmdb:tv:3"),
                   "off": ("out_of_scope", None), "short": ("insufficient_detail", None),
                   "unresolved": ("known_target", None)})
    a = {"lost": [movie], "gained": [], "both": [movie], "neither": [], "failed": None,
         "new": [], "absent": [movie], "off": None, "short": [], "unresolved": [movie]}
    b = {"lost": [tv, movie], "gained": [movie], "both": [movie], "neither": [], "failed": [movie],
         "new": [tv], "absent": [], "off": [], "short": [tv], "unresolved": None}
    report = score_cohort_outcomes(cohort, frozen_cases=frozen, ranked_a=a, ranked_b=b)
    assert report["paired_successes"] == 4 and report["paired_excluded_failed"] == 1
    assert report["paired_transitions"] == {
        "top1": {"a_only": 1, "b_only": 1, "both": 1, "neither": 1},
        "top5": {"a_only": 0, "b_only": 1, "both": 2, "neither": 1},
    }
    assert report["expanded_only_successful_hits"] == {"successful": 1, "b_top1": 1, "b_top5": 1}
    outcomes = report["outcomes"]
    assert outcomes["out_of_scope"]["a_failed"] == outcomes["out_of_scope"]["b_empty"] == 1
    assert outcomes["insufficient_detail"]["a_empty"] == outcomes["insufficient_detail"]["b_with_cards"] == 1
    assert outcomes["unresolved_positive"]["a_with_cards"] == outcomes["unresolved_positive"]["b_failed"] == 1
    assert outcomes["absent"]["a_with_cards"] == outcomes["absent"]["b_empty"] == 1
    assert frozen["lost"] == ("known_target", movie)
    assert "tmdb:" not in str(report)


def test_http_outcomes_reject_invalid_truth_or_raw_response(tmp_path):
    from tools.qa.compare_story_language_cohorts import score_cohort_outcomes

    file, pin = _fixture(tmp_path)
    cohort = plan_cohorts(file, expected_sha256=pin)
    for bad in (("known_target", "tmdb:movie:01"), ("out_of_scope", "tmdb:movie:1"), ("other", None)):
        with pytest.raises(ValueError, match="Invalid frozen"):
            score_cohort_outcomes(cohort, frozen_cases={"q": bad}, ranked_a={"q": []}, ranked_b={"q": []})
    with pytest.raises(ValueError, match="Rankings"):
        score_cohort_outcomes(cohort, frozen_cases={"q": ("out_of_scope", None)},
                              ranked_a={"q": "raw HTTP response"}, ranked_b={"q": []})

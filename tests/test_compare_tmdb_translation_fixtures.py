import json

import pytest

from tools.qa.compare_tmdb_translation_fixtures import PairedCase, compare_translation_fixtures
from web.tmdb_ids import QueueItem


def _case(media, identifier, ru="", en="", *, appended="", tag=None, adult=False):
    item = QueueItem(media, identifier)
    common = {"id": identifier, "title" if media == "movie" else "name": "Test title",
              "original_language": "ko", "adult": adult}
    translations = [] if tag is None else [{
        "iso_639_1": tag[:2], "iso_3166_1": tag[3:], "data": {"overview": "Tagged text"},
    }]
    return PairedCase(item, json.dumps(common | {"overview": ru}).encode(),
                      json.dumps(common | {"overview": en}).encode(),
                      json.dumps(common | {"overview": appended,
                                           "translations": {"translations": translations}}).encode())


def test_equal_budget_counts_independent_attempts_and_aggregate_evidence():
    good = _case("movie", 41, "An untagged overview", tag="ru-RU")
    original = _case("tv", 41, en="English fallback", tag="ko-KR")
    final = _case("movie", 42, tag="en-US")
    report = compare_translation_fixtures((good, original, final), attempt_cap=3)
    base, alternate = report["baseline"], report["appended"]
    assert base["requested_locale_only"] == {"en-US": 1, "ru-RU": 1}
    assert (base["eligible_tagged"], base["eligible_untagged"], base["budget_exhausted"]) == (0, 2, 1)
    assert base["total_body_bytes"] == sum(map(len, (good.ru_details, original.ru_details, original.en_details)))
    assert alternate["attempted_launches"] == base["attempted_launches"] == 3
    assert alternate["provider_tagged_locale"] == {"ru-RU": 1, "en-US": 1, "ko-KR": 1}
    assert alternate["eligible_tagged"] == 3 and alternate["eligible_untagged"] == 0
    sizes = [len(c.appended_details) for c in (good, original, final)]
    assert alternate["total_body_bytes"] == sum(sizes)
    assert alternate["p95_body_bytes_nearest_rank"] == max(sizes)
    assert "Tagged text" not in json.dumps(report)


def test_oversized_untagged_missing_and_ineligible_are_not_equated():
    untagged = _case("movie", 51, "Still unknown", appended="Still unknown")
    missing = _case("movie", 52)
    adult = _case("movie", 53, "Unusable", tag="ru-RU", adult=True)
    big = _case("movie", 54, "x" * 500, appended="x" * 500)
    cases = (untagged, missing, adult, big)
    report = compare_translation_fixtures(cases, attempt_cap=10, body_cap=300)
    for route in ("baseline", "appended"):
        row = report[route]
        assert [row[x] for x in ("eligible_untagged", "missing_overview", "ineligible", "oversized")] == [1, 1, 1, 1]
        assert row["p95_body_bytes_nearest_rank"] > 300
    assert report["baseline"]["attempted_launches"] == 5
    assert report["appended"]["attempted_launches"] == 4
    budget = compare_translation_fixtures((missing,), attempt_cap=0)
    assert budget["baseline"]["budget_exhausted"] == budget["appended"]["budget_exhausted"] == 1
    assert budget["baseline"]["p95_body_bytes_nearest_rank"] is None


def test_duplicate_typed_case_and_invalid_caps_refuse_before_comparison():
    one = _case("movie", 88)
    with pytest.raises(ValueError, match="duplicate"):
        compare_translation_fixtures((one, one), attempt_cap=5)
    with pytest.raises(ValueError, match="cap"):
        compare_translation_fixtures((one,), attempt_cap=True)

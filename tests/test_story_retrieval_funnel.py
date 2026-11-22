from dataclasses import replace
import json

import pytest

from tools.qa.story_retrieval_funnel import FunnelTrace, score_retrieval_funnel


M, T, V, A = "tmdb:movie:10", "tmdb:tv:10", "tmdb:tv:11", "tmdb:movie:99"
INDEX = frozenset((M, T, V))


def retrieved(targets=(), *, eligible=None, count=None, dense=(), lexical=(), final=(),
              intent="known_target", eligible_targets=None):
    return FunnelTrace(intent, "retrieved", frozenset(targets),
                       len(INDEX if eligible is None else eligible) if count is None else count,
                       dense, lexical, final, eligible_targets,
                       None if eligible is None else frozenset(eligible))


def frac(n, d):
    return {"n": n, "d": d}


def test_aggregate_separates_all_cohorts_stages_and_no_output_identifiers():
    traces = (
        retrieved((M,), dense=(M,), final=(M,)),
        retrieved((T,), dense=(M,), lexical=(T,), final=(M, T)),
        retrieved((M, T), dense=(M,), lexical=(T,), final=()),
        retrieved((M,), eligible=(M, T), dense=(T,), final=(T,)),
        retrieved((M,), eligible=(T,), dense=(T,), final=(T,)),
        retrieved((M,), count=1, dense=(T,), final=(T,)),
        retrieved((M,), count=1, dense=(M,), final=(M,)),
        retrieved((M,), eligible=(M,), final=()),
        FunnelTrace("known_target", "no_filtered_descriptions", frozenset((M,)), eligible_keys=frozenset()),
        FunnelTrace("known_target", "unsupported_exclusion", frozenset((M,))),
        FunnelTrace("known_target", "error", frozenset((M,))),
        retrieved((A,), dense=(T,), final=(T,)),
        FunnelTrace("known_target", "need_plot_detail"),
        retrieved(intent="out_of_scope", dense=(T,), final=(T,)),
        FunnelTrace("out_of_scope", "explicit_non_film_request"),
        FunnelTrace("out_of_scope", "query_too_long"),
        FunnelTrace("out_of_scope", "error"),
        FunnelTrace("insufficient_detail", "no_eligible_catalog_entries"),
    )
    report = score_retrieval_funnel(iter(traces), indexed=INDEX)
    assert report["cases"] == len(traces) == 18 and report["indexed_titles"] == 3
    assert report["verified_query_coverage"] == frac(11, 12)
    cohorts = report["cohorts"]
    assert [cohorts[name]["cases"] for name in ("covered", "absent", "unverified", "out_of_scope",
                                               "insufficient_detail")] == [11, 1, 1, 4, 1]
    assert cohorts["covered"]["routes"] == {
        "retrieved": 8, "no_filtered_descriptions": 1, "unsupported_exclusion": 1, "error": 1,
        "explicit_non_film_request": 0, "need_plot_detail": 0, "no_eligible_catalog_entries": 0,
        "query_too_long": 0,
    }
    assert cohorts["covered"]["retrieved_without_final_cards"] == frac(2, 8)
    assert cohorts["covered"]["retrieved_without_candidates"] == frac(1, 8)
    assert cohorts["covered"]["retrieved_candidates_without_final_cards"] == frac(1, 7)
    assert cohorts["out_of_scope"]["with_final_cards"] == frac(1, 3)
    assert cohorts["out_of_scope"]["routes"]["explicit_non_film_request"] == 1
    assert cohorts["insufficient_detail"]["routes"]["no_eligible_catalog_entries"] == 1
    assert cohorts["absent"]["with_final_cards"] == frac(1, 1)
    assert cohorts["unverified"]["routes"]["need_plot_detail"] == 1
    assert report["covered_funnel"] == {
        "reached_retrieval": frac(8, 11), "target_eligible": frac(6, 8),
        "target_excluded_by_query_filters": frac(1, 8), "target_eligibility_unknown": frac(1, 8),
        "lanes": {name: frac(num, 6) for name, num in
                  (("dense_only", 2), ("lexical_only", 1), ("both_lanes", 1), ("neither", 2))},
        "union_discovered": frac(4, 6), "discovery_miss": frac(2, 6),
        "ranking_miss_after_discovery": frac(1, 4), "top1_of_discovered": frac(2, 4),
        "top5_of_discovered": frac(3, 4), "top1_of_covered": frac(2, 11), "top5_of_covered": frac(3, 11),
    }
    raw = json.dumps(report)
    assert all(key not in raw for key in (M, T, V, A))


def test_independent_target_eligibility_resolves_partial_mask_without_whole_set():
    traces = (retrieved((M,), count=2, dense=(T,), eligible_targets=frozenset((M,))),
              retrieved((M,), count=2, dense=(T,), eligible_targets=frozenset()))
    report = score_retrieval_funnel(traces, indexed=INDEX)["covered_funnel"]
    assert report["target_eligible"] == frac(1, 2)
    assert report["target_excluded_by_query_filters"] == frac(1, 2)
    assert report["target_eligibility_unknown"] == frac(0, 2)
    assert report["discovery_miss"] == frac(1, 1)


_VALID = retrieved((M,), dense=(M,), final=(M,))


@pytest.mark.parametrize("trace", [
    replace(_VALID, intent="unknown"),
    replace(_VALID, intent="out_of_scope"),
    replace(_VALID, route="fake"),
    replace(_VALID, route="error"),
    replace(_VALID, targets={M}),
    replace(_VALID, targets=frozenset(("movie:10",))),
    replace(_VALID, eligible_count=True),
    replace(_VALID, eligible_count=0),
    replace(_VALID, eligible_count=4),
    replace(_VALID, eligible_keys=frozenset((M, T))),
    replace(_VALID, eligible_count=1, eligible_keys=frozenset((T,))),
    replace(_VALID, eligible_count=1, eligible_keys=frozenset((A,))),
    replace(_VALID, dense_keys=[M]),
    replace(_VALID, dense_keys=(M, M)),
    replace(_VALID, lexical_keys=(A,)),
    replace(_VALID, final_keys=(T,)),
    replace(_VALID, eligible_count=1, lexical_keys=(T,)),
    replace(_VALID, eligible_targets=frozenset((T,))),
    replace(_VALID, eligible_targets=frozenset()),
    retrieved((M,), count=1, dense=(T,), eligible_targets=frozenset((M,))),
    FunnelTrace("out_of_scope", "explicit_non_film_request", eligible_keys=frozenset((M,))),
    FunnelTrace("known_target", "error", targets=frozenset(("tmdb:movie:9223372036854775808",))),
])
def test_malformed_or_inconsistent_trace_refuses_counts_without_payload(trace):
    with pytest.raises(ValueError) as error:
        score_retrieval_funnel([trace], indexed=INDEX)
    assert "tmdb:" not in str(error.value)


def test_maximum_lanes_and_final_depth_are_explicit():
    keys = tuple(f"tmdb:tv:{i}" for i in range(1, 83))
    indexed = frozenset(keys)
    legal = FunnelTrace("out_of_scope", "retrieved", eligible_count=82,
                        dense_keys=keys[:40], lexical_keys=keys[40:80], final_keys=keys[40:45])
    assert score_retrieval_funnel([legal], indexed=indexed)["cases"] == 1
    for illegal in (replace(legal, dense_keys=keys[:41]), replace(legal, lexical_keys=keys[40:81]),
                    replace(legal, final_keys=keys[:6])):
        with pytest.raises(ValueError):
            score_retrieval_funnel([illegal], indexed=indexed)
    assert score_retrieval_funnel([], indexed=indexed)["verified_query_coverage"] == frac(0, 0)

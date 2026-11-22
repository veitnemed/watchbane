"""Pure aggregate funnel scoring for private Watchbane retrieval observations."""

from dataclasses import dataclass
import re

from candidates.story_seed_snapshot import MAX_ROWS


_INTENTS = ("known_target", "out_of_scope", "insufficient_detail")
_ROUTES = (
    "retrieved", "query_too_long", "need_plot_detail", "unsupported_exclusion",
    "explicit_non_film_request", "no_filtered_descriptions", "no_eligible_catalog_entries", "error",
)
_COHORTS = ("covered", "absent", "unverified", "out_of_scope", "insufficient_detail")
_TYPED_ID = re.compile(r"tmdb:(?:movie|tv):([1-9][0-9]{0,18})", re.ASCII)


@dataclass(frozen=True)
class FunnelTrace:
    """Immutable one-query evidence with no query text or case identifier.

    Routes are factual runtime outcomes; intent and verified targets are
    caller-supplied truth. Targets may be alternative acceptable identities.
    Eligible targets, if supplied, are the exact subset passing query-level
    filters; an empty set means verified exclusion, None means unknown.
    Small probes may instead provide the entire eligible set for a complete
    membership check. The ordinary observer needs only its eligible count.
    """

    intent: str
    route: str
    targets: frozenset[str] = frozenset()
    eligible_count: int = 0
    dense_keys: tuple[str, ...] = ()
    lexical_keys: tuple[str, ...] = ()
    final_keys: tuple[str, ...] = ()
    eligible_targets: frozenset[str] | None = None
    eligible_keys: frozenset[str] | None = None


def _typed(value):
    match = _TYPED_ID.fullmatch(value) if type(value) is str else None
    return bool(match and int(match[1]) <= (1 << 63) - 1)


def _typed_set(keys):
    return type(keys) is frozenset and all(_typed(key) for key in keys)


def _validate(trace, indexed):
    if (type(trace) is not FunnelTrace or type(trace.intent) is not str or trace.intent not in _INTENTS
            or type(trace.route) is not str or trace.route not in _ROUTES or not _typed_set(trace.targets)
            or (trace.intent != "known_target" and trace.targets)
            or type(trace.eligible_count) is not int or not 0 <= trace.eligible_count <= len(indexed)):
        raise ValueError("Invalid retrieval trace shape")
    if trace.route != "retrieved":
        if (trace.eligible_count or trace.dense_keys != () or trace.lexical_keys != () or trace.final_keys != ()
                or trace.eligible_targets is not None
                or (trace.eligible_keys is not None
                    and (type(trace.eligible_keys) is not frozenset or trace.eligible_keys))):
            raise ValueError("A filtered, refused, or failed request cannot claim a retrieval trace")
        return set(), set()
    if not trace.eligible_count:
        raise ValueError("A retrieved trace must have eligible documents")
    provided = trace.eligible_keys
    if provided is not None and (
            type(provided) is not frozenset or len(provided) != trace.eligible_count or not provided <= indexed):
        raise ValueError("Eligible keys do not match the indexed set and count")
    domain = indexed if provided is None else provided
    for keys, limit in ((trace.dense_keys, 40), (trace.lexical_keys, 40), (trace.final_keys, 5)):
        if (type(keys) is not tuple or len(keys) > limit
                or any(not _typed(key) or key not in domain for key in keys) or len(set(keys)) != len(keys)):
            raise ValueError("Ranking includes duplicate, out-of-scope, or oversized keys")
    dense, lexical = set(trace.dense_keys), set(trace.lexical_keys)
    union = dense | lexical
    if len(union) > trace.eligible_count or not set(trace.final_keys) <= union:
        raise ValueError("Final ranking is inconsistent with the eligible retrieval union")
    qualified = trace.eligible_targets
    if qualified is not None and (
            not _typed_set(qualified) or not qualified <= trace.targets & domain
            or not (trace.targets & union) <= qualified
            or len(union | qualified) > trace.eligible_count
            or (provided is not None and qualified != trace.targets & provided)
            or (trace.eligible_count == len(indexed) and qualified != trace.targets & indexed)):
        raise ValueError("Verified target eligibility conflicts with the retrieval trace")
    return dense, lexical


def _fraction(n, d):
    return {"n": n, "d": d}


def score_retrieval_funnel(traces, *, indexed):
    """Consume validated traces once and emit only counts and denominators.

    An omitted target under a partial mask with no eligibility evidence is
    unknown, not a discovery miss. A runtime 'retrieved' response with no
    cards is distinct from a pre-retrieval gate and a failed request.
    """
    if not _typed_set(indexed) or not 1 <= len(indexed) <= MAX_ROWS:
        raise ValueError("Expected a bounded nonempty indexed set of typed IDs")
    table = {name: {"cases": 0, "routes": dict.fromkeys(_ROUTES, 0), "final_cards": 0,
                    "retrieved_empty": 0, "candidate_union_empty": 0} for name in _COHORTS}
    counts = dict.fromkeys(("target_eligible", "target_excluded", "target_eligibility_unknown",
                            "dense_only", "lexical_only", "both_lanes", "neither",
                            "discovered", "top1", "top5"), 0)
    cases = 0
    for trace in traces:
        dense, lexical = _validate(trace, indexed)
        cases += 1
        present = trace.targets & indexed
        if trace.intent == "known_target":
            name = "covered" if present else "absent" if trace.targets else "unverified"
        else:
            name = trace.intent
        cohort = table[name]
        cohort["cases"] += 1
        cohort["routes"][trace.route] += 1
        if trace.route != "retrieved":
            continue
        cohort["final_cards"] += bool(trace.final_keys)
        cohort["retrieved_empty"] += not trace.final_keys
        cohort["candidate_union_empty"] += not (dense or lexical)
        if name != "covered":
            continue

        d_hit, l_hit = bool(present & dense), bool(present & lexical)
        discovered = d_hit or l_hit
        if trace.eligible_keys is not None:
            qualified = present & trace.eligible_keys
        elif trace.eligible_targets is not None:
            qualified = trace.eligible_targets
        elif trace.eligible_count == len(indexed) or discovered:
            # Full count covers every unique indexed key. A discovered target
            # is also direct evidence of at least one eligible alternative.
            qualified = present
        else:
            counts["target_eligibility_unknown"] += 1
            continue
        if not qualified:
            counts["target_excluded"] += 1
            continue
        counts["target_eligible"] += 1
        lane = ("both_lanes" if l_hit else "dense_only") if d_hit else ("lexical_only" if l_hit else "neither")
        counts[lane] += 1
        counts["discovered"] += discovered
        counts["top1"] += bool(present.intersection(trace.final_keys[:1]))
        counts["top5"] += bool(present.intersection(trace.final_keys))

    for cohort in table.values():
        successful = cohort["cases"] - cohort["routes"]["error"]
        retrieved = cohort["routes"]["retrieved"]
        cohort["with_final_cards"] = _fraction(cohort.pop("final_cards"), successful)
        empty_final, empty_union = cohort.pop("retrieved_empty"), cohort.pop("candidate_union_empty")
        cohort["retrieved_without_final_cards"] = _fraction(empty_final, retrieved)
        cohort["retrieved_without_candidates"] = _fraction(empty_union, retrieved)
        cohort["retrieved_candidates_without_final_cards"] = _fraction(empty_final - empty_union, retrieved - empty_union)
    covered, absent = table["covered"]["cases"], table["absent"]["cases"]
    reached = table["covered"]["routes"]["retrieved"]
    eligible, discovered = counts["target_eligible"], counts["discovered"]
    return {
        "schema_version": 1, "cases": cases, "indexed_titles": len(indexed), "cohorts": table,
        "verified_query_coverage": _fraction(covered, covered + absent),
        "covered_funnel": {
            "reached_retrieval": _fraction(reached, covered),
            "target_eligible": _fraction(eligible, reached),
            "target_excluded_by_query_filters": _fraction(counts["target_excluded"], reached),
            "target_eligibility_unknown": _fraction(counts["target_eligibility_unknown"], reached),
            # 'Both' means each lane contains at least one acceptable target,
            # not that the same alternative was necessarily in both lanes.
            "lanes": {key: _fraction(counts[key], eligible)
                      for key in ("dense_only", "lexical_only", "both_lanes", "neither")},
            "union_discovered": _fraction(discovered, eligible),
            "discovery_miss": _fraction(eligible - discovered, eligible),
            "ranking_miss_after_discovery": _fraction(discovered - counts["top5"], discovered),
            "top1_of_discovered": _fraction(counts["top1"], discovered),
            "top5_of_discovered": _fraction(counts["top5"], discovered),
            "top1_of_covered": _fraction(counts["top1"], covered),
            "top5_of_covered": _fraction(counts["top5"], covered),
        },
    }

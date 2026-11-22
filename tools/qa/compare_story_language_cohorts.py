"""Offline operator QA: plan and score a pinned nested Russian/English comparison."""
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
import re

from web.story_catalog_multilingual import MultilingualRow, load_operator_catalog

_TYPED = re.compile(r"tmdb:(?:movie|tv):[1-9][0-9]{0,9}", re.ASCII)
_EN = re.compile(r"en-[A-Z]{2}", re.ASCII)


@dataclass(frozen=True)
class LanguageCohorts:
    baseline: tuple[MultilingualRow, ...]
    expanded: tuple[MultilingualRow, ...]


def plan_cohorts(path: Path, *, expected_sha256: str, english_locales=("en-US",)) -> LanguageCohorts:
    """Start with verified ru-RU, then append explicitly selected, tagged EN rows.

    Original language is not a synopsis tag. The same RU objects and order
    are passed to both rankers; other locales are excluded. The operator is
    responsible for source/use clearance before supplying the pinned artifact.
    """
    if (not isinstance(english_locales, tuple) or not english_locales
            or any(type(tag) is not str or not _EN.fullmatch(tag) for tag in english_locales)
            or len(set(english_locales)) != len(english_locales)):
        raise ValueError("An exact, nonempty English locale list is required")
    rows = load_operator_catalog(path, expected_sha256=expected_sha256)
    ru = tuple(row for row in rows if row.synopsis_locale == "ru-RU")
    en = tuple(row for row in rows if row.synopsis_locale in english_locales)
    if not ru or not en:
        raise ValueError("Both cohorts require at least one eligible description")
    return LanguageCohorts(ru, ru + en)


def _typed(value):
    return (type(value) is str and _TYPED.fullmatch(value) is not None
            and int(value.rsplit(":", 1)[1]) < 2**31)


def score_cohorts(cohorts: LanguageCohorts, *, truth: Mapping, ranked_a: Mapping, ranked_b: Mapping) -> dict:
    """Join pre-frozen, verified case->typed target with independent ordered Top-5s.

    Use None only for cases without a verified target; their counts remain
    separate. The same model/query policy must generate the two rankings, but
    this count-only join does not run inference or attest benchmark provenance.
    """
    if not isinstance(cohorts, LanguageCohorts):
        raise ValueError("Use a nested language cohort plan")
    a = {row.key for row in cohorts.baseline}
    b = {row.key for row in cohorts.expanded}
    if (not a or not a < b or len(b) != len(cohorts.expanded) or len(a) != len(cohorts.baseline)
            or cohorts.expanded[:len(cohorts.baseline)] != cohorts.baseline
            or any(row.synopsis_locale != "ru-RU" for row in cohorts.baseline)
            or any(not _EN.fullmatch(row.synopsis_locale) for row in cohorts.expanded[len(a):])):
        raise ValueError("Use identical RU rows as the prefix of a strictly larger cohort")
    if not isinstance(truth, Mapping) or not truth or any(
        type(case) is not str or not case.strip() or (target is not None and not _typed(target))
        for case, target in truth.items()
    ):
        raise ValueError("Frozen truth must contain verified typed targets or None")
    for rankings, known in ((ranked_a, a), (ranked_b, b)):
        if not isinstance(rankings, Mapping) or rankings.keys() != truth.keys():
            raise ValueError("Rankings must match the frozen case IDs")
        for hits in rankings.values():
            if (not isinstance(hits, (list, tuple)) or len(hits) > 5
                    or any(not _typed(hit) or hit not in known for hit in hits) or len(set(hits)) != len(hits)):
                raise ValueError("Rankings must be unique typed Top-5 results from their own cohort")

    paired = {"cases": 0, "a_top1": 0, "a_top5": 0, "b_top1": 0, "b_top5": 0}
    expanded_only = {"cases": 0, "b_top1": 0, "b_top5": 0}
    absent = {"cases": 0, "a_with_cards": 0, "b_with_cards": 0}
    unverified = absent.copy()
    for case, target in truth.items():
        ra, rb = ranked_a[case], ranked_b[case]
        if target in a:
            paired["cases"] += 1
            paired["a_top1"] += bool(ra and ra[0] == target)
            paired["a_top5"] += target in ra
            paired["b_top1"] += bool(rb and rb[0] == target)
            paired["b_top5"] += target in rb
        elif target in b:
            expanded_only["cases"] += 1
            expanded_only["b_top1"] += bool(rb and rb[0] == target)
            expanded_only["b_top5"] += target in rb
        else:
            bucket = unverified if target is None else absent
            bucket["cases"] += 1
            bucket["a_with_cards"] += bool(ra)
            bucket["b_with_cards"] += bool(rb)
    return {"catalog_a": len(a), "catalog_b": len(b), "paired": paired,
            "expanded_only": expanded_only, "absent": absent, "without_verified_target": unverified}


def score_cohort_outcomes(cohorts: LanguageCohorts, *, frozen_cases: Mapping, ranked_a: Mapping,
                          ranked_b: Mapping) -> dict:
    """Audit paired HTTP outcomes from frozen case IDs, without reading query text.

    Each frozen case has (lane, target) with the sealed benchmark lane name:
    known_target with a verified typed target or None if its identity was not
    verified; out_of_scope and insufficient_detail require None.
    Each HTTP ranking is a Top-5 list/tuple on success, or None on failure.
    Paired ranking transitions count only common targets with two successes;
    failures are separately counted, never scored as empty misses.
    """
    negative_lanes = ("out_of_scope", "insufficient_detail")
    if not isinstance(frozen_cases, Mapping) or not frozen_cases:
        raise ValueError("Expected frozen intent and exact typed truth for every case")
    truth = {}
    for case, entry in frozen_cases.items():
        if (not isinstance(entry, tuple) or len(entry) != 2
                or (entry[0] == "known_target" and entry[1] is not None and not _typed(entry[1]))
                or (entry[0] != "known_target" and (entry[0] not in negative_lanes or entry[1] is not None))):
            raise ValueError("Invalid frozen intent or typed target")
        truth[case] = entry[1]
    if not isinstance(ranked_a, Mapping) or not isinstance(ranked_b, Mapping):
        raise ValueError("HTTP outcomes must map each frozen case ID")
    # Reuse exact key, typed membership, length and cohort structure validation.
    # Empty conversion is exclusively for shape validation; its metrics are discarded.
    checked = score_cohorts(cohorts, truth=truth,
                           ranked_a={case: () if hits is None else hits for case, hits in ranked_a.items()},
                           ranked_b={case: () if hits is None else hits for case, hits in ranked_b.items()})
    a = {row.key for row in cohorts.baseline}
    b = {row.key for row in cohorts.expanded}
    buckets = {
        name: {"cases": 0, "a_failed": 0, "b_failed": 0,
               "a_empty": 0, "b_empty": 0, "a_with_cards": 0, "b_with_cards": 0}
        for name in ("common", "expanded_only", "absent", *negative_lanes, "unresolved_positive")
    }
    transitions = {f"top{cutoff}": dict.fromkeys(("a_only", "b_only", "both", "neither"), 0)
                   for cutoff in (1, 5)}
    paired_successes = 0
    expanded_hits = dict.fromkeys(("successful", "b_top1", "b_top5"), 0)
    for case, (lane, target) in frozen_cases.items():
        ra, rb = ranked_a[case], ranked_b[case]
        if lane != "known_target":
            cohort = lane
        elif target is None:
            cohort = "unresolved_positive"
        else:
            cohort = "common" if target in a else "expanded_only" if target in b else "absent"
        bucket = buckets[cohort]
        bucket["cases"] += 1
        for side, hits in (("a", ra), ("b", rb)):
            suffix = "failed" if hits is None else "with_cards" if hits else "empty"
            bucket[f"{side}_{suffix}"] += 1
        if cohort == "expanded_only" and rb is not None:
            expanded_hits["successful"] += 1
            expanded_hits["b_top1"] += target in rb[:1]
            expanded_hits["b_top5"] += target in rb
        if cohort == "common" and ra is not None and rb is not None:
            paired_successes += 1
            for cutoff in (1, 5):
                ah, bh = target in ra[:cutoff], target in rb[:cutoff]
                label = ("both" if bh else "a_only") if ah else ("b_only" if bh else "neither")
                transitions[f"top{cutoff}"][label] += 1
    return {"catalog_a": checked["catalog_a"], "catalog_b": checked["catalog_b"],
            "outcomes": buckets, "paired_successes": paired_successes,
            "paired_excluded_failed": buckets["common"]["cases"] - paired_successes,
            "paired_transitions": transitions, "expanded_only_successful_hits": expanded_hits}

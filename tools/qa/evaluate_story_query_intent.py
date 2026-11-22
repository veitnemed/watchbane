"""Detached, synthetic-only query-intent experiment; keep selection output private."""
import argparse
from collections import Counter
from dataclasses import dataclass, replace
from hashlib import sha256
import json
import math
from pathlib import Path

from candidates.story_search import tokens


POLICY = "story-query-intent-v1"
_MAX_BYTES = 1024 * 1024


@dataclass(frozen=True)
class Case:
    id: str
    query: str
    intent: str
    short: bool
    family: str
    baseline_cards: bool = False
    exact_title: bool = False


def _read_pinned(path, digest):
    with Path(path).open("rb") as source:
        raw = source.read(_MAX_BYTES + 1)
    if len(raw) > _MAX_BYTES or sha256(raw).hexdigest() != digest:
        raise ValueError("Private input exceeds byte limit or doesn't match the pin")
    return raw


def read_split(path, digest):
    raw = _read_pinned(path, digest)
    cases = []
    for line in raw.splitlines():
        try:
            row = json.loads(line)
            if set(row) != {"id", "query", "intent", "short", "family"}:
                raise ValueError
            if any(not isinstance(row[key], str) or not row[key].strip() for key in ("id", "family")):
                raise ValueError
            if not isinstance(row["query"], str) or not row["query"].strip() or len(row["query"]) > 600:
                raise ValueError
            if row["intent"] not in ("film", "nonfilm"):
                raise ValueError
            if type(row["short"]) is not bool:
                raise ValueError
            if row["short"] and row["intent"] != "film":
                raise ValueError
            cases.append(Case(**row))
        except (TypeError, ValueError):
            raise ValueError("invalid synthetic intent row") from None
    return tuple(cases)


def split_fingerprints(split):
    digests = set()
    for case in split:
        key = tuple(tokens(case.query))
        if not key:
            raise ValueError("empty normalized case")
        for kind, value in (("id", case.id), ("query", key)):
            fingerprint = sha256(canonical([kind, value])).hexdigest()
            if fingerprint in digests:
                raise ValueError("duplicate normalized case or case ID")
            digests.add(fingerprint)
        digests.add(sha256(canonical(["family", case.family.strip().casefold()])).hexdigest())
    if {case.intent for case in split} != {"film", "nonfilm"}:
        raise ValueError("each split must contain both intent labels")
    return digests


def require_disjoint(left, right):
    if left & right:
        raise ValueError("overlapping split family, ID or normalized case")


def load_baseline(path, digest, split):
    baseline = json.loads(_read_pinned(path, digest))
    if not isinstance(baseline, dict) or set(baseline) != {case.id for case in split}:
        raise ValueError("baseline must cover exactly the evaluated cases")
    for item in baseline.values():
        if (not isinstance(item, dict) or set(item) != {"baseline_cards", "exact_title"}
                or any(type(value) is not bool for value in item.values())):
            raise ValueError("invalid baseline row")
    return tuple(replace(row, **baseline[row.id]) for row in split)


def train_model(train):
    # Deliberately import optional experiment dependencies only here.
    import sklearn
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import FeatureUnion, Pipeline

    model = Pipeline([
        ("features", FeatureUnion([
            ("word", TfidfVectorizer(analyzer="word", ngram_range=(1, 1),
                                     token_pattern=r"(?u)\b\w+\b")),
            ("char", TfidfVectorizer(analyzer="char", ngram_range=(3, 5))),
        ])),
        ("intent", LogisticRegression(C=1.0, solver="liblinear", random_state=0,
                                      max_iter=1000)),
    ])
    model.fit([row.query for row in train], [row.intent for row in train])
    # Hash fitted state (including IDF) rather than pickle or storing vocab in
    # any public output. Refitting with different results fails validation.
    artifacts = [
        [name, sorted(vocabulary.vocabulary_.items()), vocabulary.idf_.tolist()]
        for name, vocabulary in model.named_steps["features"].transformer_list
    ]
    clf = model.named_steps["intent"]
    model_hash = sha256(json.dumps(
        [POLICY, sklearn.__version__, artifacts, clf.classes_.tolist(), clf.coef_.tolist(),
         clf.intercept_.tolist()], ensure_ascii=True, separators=(",", ":"),
        allow_nan=False,
    ).encode()).hexdigest()
    return model, model_hash


def protected(row):
    stripped = row.query.strip()
    return row.exact_title or (
        len(stripped) >= 2
        and (stripped[0], stripped[-1]) in {('«', '»'), ('"', '"'), ('“', '”')}
    )


def scored(model, cases):
    probs = model.predict_proba([row.query for row in cases])
    column = list(model.classes_).index("nonfilm")
    return tuple((row, float(p[column])) for row, p in zip(cases, probs, strict=True))


def choose_cutoff(rows):
    # Include a no-op cutoff; probabilities are <=1. Among ties, choose the
    # higher, more conservative cutoff, including no-op if there is no gain.
    active = [(row, p) for row, p in rows if row.baseline_cards and not protected(row)]
    film_max = max((p for row, p in active if row.intent == "film"), default=-1.0)
    choices = {2.0, *(p for row, p in active if row.intent == "nonfilm" and p > film_max)}
    return max(choices, key=lambda cutoff: (
        sum(row.intent == "nonfilm" and p >= cutoff for row, p in active), cutoff))


def report(rows, cutoff):
    counts = Counter()
    for row, p in rows:
        counts[f"{row.intent}_total"] += 1
        # Count every short positive regardless of author annotation.
        short_film = row.intent == "film" and 1 <= len(tokens(row.query)) <= 5
        counts["short_film_total"] += short_film
        counts[f"{row.intent}_baseline_cards"] += row.baseline_cards
        counts["short_film_baseline_cards"] += short_film and row.baseline_cards
        counts[f"{row.intent}_newly_suppressed"] += (
            row.baseline_cards and not protected(row) and p >= cutoff
        )
        counts["short_film_newly_suppressed"] += (
            short_film and row.baseline_cards and not protected(row) and p >= cutoff
        )
    for label in ("nonfilm", "film"):
        counts[f"{label}_baseline_already_empty"] = counts[f"{label}_total"] - counts[f"{label}_baseline_cards"]
    tp = counts["nonfilm_newly_suppressed"]
    fp = counts["film_newly_suppressed"]
    baseline = counts["nonfilm_baseline_cards"]
    short_safe = counts["short_film_newly_suppressed"] == 0
    return {
        "counts": {key: counts[key] for key in (
            "nonfilm_total", "film_total", "short_film_total", "nonfilm_baseline_cards", "film_baseline_cards",
            "short_film_baseline_cards", "nonfilm_baseline_already_empty", "film_baseline_already_empty",
            "nonfilm_newly_suppressed", "film_newly_suppressed", "short_film_newly_suppressed",
        )},
        "suppression_precision": {"n": tp, "d": tp + fp},
        "baseline_nonfilm_card_reduction": {"n": tp, "d": baseline},
        "gates": {
            "precision": tp + fp > 0 and 100 * tp >= 95 * (tp + fp),
            "card_reduction": baseline > 0 and 100 * tp >= 35 * baseline,
            "no_new_short_film_suppression": counts["short_film_baseline_cards"] > 0 and short_safe,
        },
    }


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_subparsers(dest="mode", required=True)
    for name in ("select", "validate"):
        sub = mode.add_parser(name)
        sub.add_argument("--train", required=True, type=Path)
        sub.add_argument("--train-sha256", required=True)
        sub.add_argument("--baseline", required=True, type=Path)
        sub.add_argument("--baseline-sha256", required=True)
        if name == "select":
            sub.add_argument("--calibration", required=True, type=Path)
            sub.add_argument("--calibration-sha256", required=True)
        else:
            sub.add_argument("--selection", required=True, type=Path)
            sub.add_argument("--selection-sha256", required=True)
            sub.add_argument("--validation", required=True, type=Path)
            sub.add_argument("--validation-sha256", required=True)
    args = parser.parse_args(argv)

    train = read_split(args.train, args.train_sha256)
    train_signatures = split_fingerprints(train)
    if args.mode == "select":
        cal = read_split(args.calibration, args.calibration_sha256)
        cal_signatures = split_fingerprints(cal)
        require_disjoint(train_signatures, cal_signatures)
        cal = load_baseline(args.baseline, args.baseline_sha256, cal)
        model, model_hash = train_model(train)
        rows = scored(model, cal)
        cutoff = choose_cutoff(rows)
        selection = {"policy": POLICY, "model_sha256": model_hash,
                     "train_sha256": args.train_sha256, "calibration_sha256": args.calibration_sha256,
                     "cutoff_hex": cutoff.hex(), "calibration": report(rows, cutoff),
                     "baseline_sha256": args.baseline_sha256,
                     "private_calibration_fingerprints": sorted(cal_signatures)}
        print(canonical(selection).decode())
        return

    # No calibration input is accepted or opened in validation mode. Require
    # the exact selection pinned by the operator before opening validation.
    selection = json.loads(_read_pinned(args.selection, args.selection_sha256))
    if selection["policy"] != POLICY or selection["train_sha256"] != args.train_sha256:
        raise ValueError("selection policy or train split mismatch")
    if args.validation_sha256 in (selection["train_sha256"], selection["calibration_sha256"]):
        raise ValueError("validation must use a separate split")
    cutoff = float.fromhex(selection["cutoff_hex"])
    if not math.isfinite(cutoff) or not (0 <= cutoff <= 1 or cutoff == 2):
        raise ValueError("invalid selected cutoff")
    model, model_hash = train_model(train)
    if model_hash != selection["model_sha256"]:
        raise ValueError("refitted model does not match pinned selection")
    validation = read_split(args.validation, args.validation_sha256)
    require_disjoint(train_signatures | set(selection["private_calibration_fingerprints"]),
                     split_fingerprints(validation))
    validation = load_baseline(args.baseline, args.baseline_sha256, validation)
    result = report(scored(model, validation), cutoff)
    result.update({
        "policy": POLICY, "model_sha256": model_hash, "selection_sha256": args.selection_sha256,
        "validation_sha256": args.validation_sha256, "baseline_sha256": args.baseline_sha256,
        "cutoff_hex": selection["cutoff_hex"],
        "status": "PASS_INTENT_ONLY" if all(result["gates"].values()) else "REJECT",
    })
    print(canonical(result).decode())


if __name__ == "__main__":
    try:
        main()
    except (KeyError, OSError, TypeError, ValueError, ImportError):
        raise SystemExit("Private intent experiment input or runtime verification failed.") from None

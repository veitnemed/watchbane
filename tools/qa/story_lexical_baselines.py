"""Offline evaluation-only lexical baselines for story text (no title boosts)."""
from collections import Counter
import math
import re
from time import perf_counter


def words(text):
    return re.findall(r"[^\W_]+", text.casefold().replace("ё", "е"), re.UNICODE)


def grams(text):
    text = " ".join(words(text))
    return [text[i:i+n] for n in (3, 4, 5) for i in range(len(text)-n+1)]


class BM25:
    """Okapi with k1=1.2, b=.75, repeated query terms counted once."""
    def __init__(self, documents):
        self.rows = [Counter(words(d.overview)) for d in documents]
        self.keys = [d.key for d in documents]
        self.lengths = [sum(row.values()) for row in self.rows]
        self.avg = (sum(self.lengths) / (len(self.rows) or 1)) or 1
        df = Counter(t for row in self.rows for t in row)
        self.idf = {t: math.log1p((len(self.rows)-n+.5)/(n+.5)) for t,n in df.items()}

    def search(self, query, limit=5):
        terms = set(words(query))
        scores = []
        for row, length in zip(self.rows, self.lengths):
            norm = 1.2 * (.25 + .75 * length / self.avg)
            scores.append(sum(self.idf[t]*2.2*f/(f+norm)
                              for t in sorted(terms) if (f := row[t])))
        return _rank(self.keys, scores, limit)


class CharTFIDF:
    """3–5 character n-grams, sublinear TF and smoothed unit cosine."""
    def __init__(self, documents):
        counts = [Counter(grams(d.overview)) for d in documents]
        self.keys = [d.key for d in documents]
        df = Counter(t for row in counts for t in row)
        self.idf = {t: 1 + math.log((1+len(counts))/(1+n)) for t,n in df.items()}
        self.rows = [self._weights(row) for row in counts]

    def _weights(self, counts):
        w = {t:(1+math.log(n))*self.idf[t] for t,n in counts.items() if t in self.idf}
        norm = math.sqrt(sum(v*v for v in w.values())) or 1
        return {t:v/norm for t,v in w.items()}

    def search(self, query, limit=5):
        q = self._weights(Counter(grams(query)))
        return _rank(self.keys, [sum(w*row.get(t,0) for t,w in q.items())
                                 for row in self.rows], limit)


def _rank(keys, scores, limit):
    return [key for score, key in sorted(zip(scores, keys), key=lambda x: (-x[0], x[1]))
            if score > 0][:limit]


def evaluate(runners, cases, keys):
    """Return only typed IDs, timings, exact ranks and negative counts."""
    for case in cases:
        target = set(case["full"])
        row = {"id": case["id"], "covered": bool(target & keys), "expect":case["expect"], "runners": {}}
        for name, run in runners.items():
            tick = perf_counter()
            hits = run(case["query"])
            row["runners"][name] = {
                "ids": hits, "ms": round((perf_counter()-tick)*1000, 3),
                "exact_rank": next((n for n, key in enumerate(hits, 1) if key in target), None),
            }
        yield row


def main():
    import argparse
    import json
    from pathlib import Path
    from statistics import median
    from tools.qa.isolation import apply_isolated_data_dir

    p = argparse.ArgumentParser(description=__doc__)
    for name in ("catalog", "fixture", "profile", "model-dir"):
        p.add_argument("--" + name, type=Path, required=True)
    args = p.parse_args()
    apply_isolated_data_dir(args.profile)
    from candidates.story_service import create_story_search, story_catalog_snapshot

    docs, _ = story_catalog_snapshot(seed_path=args.catalog)
    cases = json.loads(args.fixture.read_text(encoding="utf-8"))["cases"]
    tick = perf_counter()
    bm25 = BM25(docs)
    bm25_ms = (perf_counter()-tick)*1000
    tick = perf_counter()
    char = CharTFIDF(docs)
    char_ms = (perf_counter()-tick)*1000
    tick = perf_counter()
    e5 = create_story_search(docs, args.model_dir)
    e5_ms = (perf_counter()-tick)*1000
    runners = {
        "bm25": bm25.search, "char_tfidf": char.search,
        "e5_product": lambda q: [h.document.key for h in e5.search(q).hits],
    }
    keys = {d.key for d in docs}
    # Run the fixture once in its sealed order; count only exact, known-positive IDs.
    rows = list(evaluate(runners, cases, keys))
    stats = {
        name: {
            "top1": sum(r["runners"][name]["exact_rank"] == 1 for r in rows),
            "top5": sum(r["runners"][name]["exact_rank"] is not None for r in rows),
            "near_miss_cards": sum(len(r["runners"][name]["ids"]) for r in rows if r["expect"] == "uncertain"),
            "ood_cards": sum(len(r["runners"][name]["ids"]) for r in rows if r["expect"] == "no_match"),
            "first_ms": rows[0]["runners"][name]["ms"] if rows else None,
            "median_ms": median(r["runners"][name]["ms"] for r in rows) if rows else None,
        } for name in runners
    }
    print(json.dumps({"documents": len(docs), "covered": sum(r["covered"] for r in rows),
        "positives": sum(bool(c["full"]) for c in cases),
        "prepare_ms": dict(bm25=bm25_ms, char_tfidf=char_ms, e5_product=e5_ms),
        "summary": stats, "rows": rows}, indent=2))


if __name__ == "__main__":
    main()

"""Repeatable synthetic lexical/concept/rerank comparison. No network or storage."""
import argparse
from dataclasses import replace
from hashlib import sha256
import json
from math import log2
from pathlib import Path
import platform
from statistics import mean, median
from time import perf_counter
from candidates.story_demo import demo_documents
from candidates.story_search import StorySearch, ConceptRetriever, lexical_score, tokens


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=20)
    args = parser.parse_args()
    path = Path(__file__).resolve().parents[2] / "tests/fixtures/story_queries.json"
    cases = json.loads(path.read_text())
    documents = demo_documents()
    engine = StorySearch(documents)
    def eligible(query):
        words = tokens(query)
        kind = "tv" if any(w.startswith("сериал") for w in words) else "movie" if any(w.startswith("фильм") for w in words) else None
        return [d for d in documents if not kind or d.media_type == kind]
    def lexical(query):
        rows = [(d, lexical_score(query, d.overview)) for d in eligible(query)]
        return [d.key for d, score in sorted(rows, key=lambda x: (-x[1], x[0].key)) if score > 0][:5]
    methods = {
        "lexical_exact_tokens": lexical,
        "concept_retrieval_only": lambda q: [d.key for d, _ in ConceptRetriever().retrieve(q, eligible(q), 5)],
        "concept_plus_role_rerank": lambda q: [h.document.key for h in engine.search(q).hits],
    }
    rows = []
    for name, search in methods.items():
        for case in cases:
            times = []
            search(case["query"])
            for _ in range(args.repeats):
                start = perf_counter()
                found = search(case["query"])
                times.append((perf_counter() - start) * 1000)
            relevant = set(case["relevant"])
            hits = [int(key in relevant) for key in found]
            ideal = sum(1/log2(i+2) for i in range(min(5, len(relevant))))
            rows.append({**case, "method": name, "found": found,
                "precision_at_5": sum(hits)/5 if relevant else None,
                "recall_at_5": sum(hits)/len(relevant) if relevant else None,
                "ndcg_at_5": sum(h/log2(i+2) for i,h in enumerate(hits))/ideal if ideal else None,
                "mrr": next((1/(i+1) for i,h in enumerate(hits) if h), 0) if relevant else None,
                "correct_abstention": not found if not relevant else None,
                "latency_ms_median": median(times), "latency_ms_p95": sorted(times)[max(0, int(.95*len(times))-1)]})
    summary = []
    for method in methods:
        for group in ["all", *dict.fromkeys(c["group"] for c in cases)]:
            selected = [r for r in rows if r["method"] == method and (group == "all" or r["group"] == group)]
            result = {"method":method,"group":group,"queries":len(selected)}
            for metric in ("precision_at_5","recall_at_5","ndcg_at_5","mrr","correct_abstention","latency_ms_median","latency_ms_p95"):
                values = [r[metric] for r in selected if r[metric] is not None]
                result[metric] = round(mean(values),4) if values else None
            summary.append(result)
    # Scalability probe duplicates plots, not a larger quality evaluation.
    large = [replace(d, key=f"{i}:{d.key}") for i in range(100) for d in documents]
    start = perf_counter(); large_engine = StorySearch(large); build_ms = (perf_counter()-start)*1000
    start = perf_counter(); large_engine.search("сериал про преступника"); large_ms = (perf_counter()-start)*1000
    payload = {"python":platform.python_version(),"platform":platform.platform(),
        "corpus_size":len(documents),"query_count":len(cases),"query_sha256":sha256(path.read_bytes()).hexdigest(),
        "corpus_sha256":sha256(repr(documents).encode()).hexdigest(),"repeats":args.repeats,
        "limitations":"Synthetic author-labelled set, no independent human judgments; exact lexical baseline is not production FTS. Warm timings exclude Qt/storage; p95 summary is mean per-query p95. Binary relevance, no tuning/holdout claim.",
        "scale_probe":{"documents":len(large),"build_ms":build_ms,"search_ms":large_ms,"duplicated_plots":True},
        "summary":summary,"queries":rows}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n")
    for row in summary:
        if row["group"] == "all": print(row)
    print(payload["scale_probe"])

if __name__ == "__main__": main()

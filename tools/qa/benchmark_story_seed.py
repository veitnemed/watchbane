"""Benchmark exactly the rows in a local JSONL snapshot; never rewrite the corpus."""
import argparse
import json
from pathlib import Path
import statistics
from time import perf_counter


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--catalog", type=Path, required=True)
    p.add_argument("--model-dir", type=Path, required=True)
    p.add_argument("--profile", type=Path, required=True,
                   help="Dedicated disposable profile; reuse it for a warm restart measurement")
    args = p.parse_args()
    from tools.qa.isolation import apply_isolated_data_dir
    apply_isolated_data_dir(args.profile)
    from candidates.story_seed_snapshot import load_seed_snapshot
    from candidates.story_service import local_story_catalog
    from candidates.story_search import StorySearch

    start = perf_counter()
    count = len(load_seed_snapshot(args.catalog))
    read_ms = (perf_counter() - start) * 1000
    start = perf_counter()
    engine, _ = local_story_catalog(args.model_dir, seed_path=args.catalog)
    index_ms = (perf_counter() - start) * 1000
    cache = engine.encoder.cache
    cache_index = {name: getattr(cache, name) for name in ("hits", "misses", "errors", "writes")}
    queries = (
        "преступник", "пристурник", "судмедэксперт полиции Майами серийный убийца",
        "семья пытается выжить после катастрофы", "как обнулить счётчик в принтере",
    )
    timings, results = [], {}
    lexical = StorySearch(engine.documents)
    for query in queries:
        tick = perf_counter()
        hits = engine.search(query).hits
        timings.append((perf_counter() - tick) * 1000)
        results[query] = {"hybrid_ids": [h.document.key for h in hits],
                          "fallback_ids": [h.document.key for h in lexical.search(query).hits]}
    print(json.dumps({"source_rows": count, "indexed_rows": len(engine.documents),
                      "snapshot_read_ms": round(read_ms, 1), "model_and_index_ms": round(index_ms, 1),
                      "index_cache": cache_index, "limited_query_sample_ms":
                      {"median": round(statistics.median(timings), 1), "max": round(max(timings), 1)},
                      "results": results}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

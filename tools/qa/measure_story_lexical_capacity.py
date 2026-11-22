"""Deterministic synthetic char-gram capacity comparison; never uses E5 or TMDb."""
import argparse
from hashlib import sha256
import json
from time import perf_counter

import numpy as np

from candidates.story_lexical import LexicalIndex
from candidates.story_search import StoryDocument
from web.story_retrieval_index import PreparedRetrievalIndex


_ROWS_DEFAULT = 1000
_ROWS_MAX = 2000
_ALPHABET = "абвгдежзиклмнопрстуфхцчшщэюя"
_STEMS = ("летописец", "проводник", "зодчество", "переводчик", "картограф", "первопроходец")


def make_documents(count, density, *, x86_5k_lab=False):
    allowed = type(count) is int and (1 <= count <= _ROWS_MAX or
                                      (x86_5k_lab is True and count == 5000 and density == "low"))
    if not allowed or density not in ("low", "high"):
        raise ValueError("unsupported synthetic row count or density")
    for row in range(count):
        signature = "".join(_ALPHABET[(row // len(_ALPHABET)**i) % len(_ALPHABET)] for i in (2, 1, 0))
        if density == "low":
            words = " ".join(_STEMS * 7)
        else:
            # Same word count but independent invented forms; deterministic by
            # row/chunk, and independent of Python hash randomization.
            symbols = "".join(_ALPHABET[b % len(_ALPHABET)]
                              for block in range(11)
                              for b in sha256(f"{row}:{block}".encode("ascii")).digest())
            words = " ".join(symbols[i:i + 8] for i in range(0, 42 * 8, 8))
        yield StoryDocument(f"synthetic:qa:{row:04}", f"Фикстура {row}", f"метка{signature} {words}.",
                            "movie", "synthetic_qa_only")


def _ranking(documents, scores):
    return tuple(sorted((i for i, score in enumerate(scores) if score > 0),
                        key=lambda i: (-scores[i], documents[i].key)))


def measure(count, density):
    documents = tuple(make_documents(count, density))
    started = perf_counter()
    baseline = LexicalIndex(documents)
    baseline_seconds = perf_counter() - started
    # No E5: allocate a one-column dummy matrix before the timer. The measured
    # prepared build includes key ranks plus its real lexical postings.
    dummy = np.zeros((count, 1), dtype=np.float32)
    started = perf_counter()
    prepared = PreparedRetrievalIndex(documents, dummy)
    prepared_seconds = perf_counter() - started
    lexical = prepared.lexical
    postings = sum(map(len, baseline.vectors))
    if postings != lexical.rows.size or baseline.idf != lexical.idf:
        raise AssertionError("prepared vocabulary or posting count diverged")
    probes = ("летописец картограф", "межзвёздный полёт", "меткаааб", "летаписец") + tuple(
        documents[index].overview for index in sorted({0, count // 2, count - 1})
    )
    exact_score_probes = exact_rank_probes = exact_top40_probes = 0
    max_absolute_score_delta = 0.0
    for probe in probes:
        old = baseline.scores(probe)
        new = lexical.scores(probe)
        exact_score_probes += bool(np.array_equal(old, new))
        max_absolute_score_delta = max(max_absolute_score_delta, float(np.max(np.abs(np.asarray(old) - new))))
        rank = _ranking(documents, old)
        exact_rank_probes += rank == _ranking(documents, new)
        # Check the serving candidate entry point too; all dummy dense vectors
        # tie and cannot demonstrate any semantic or final ranking quality.
        result = prepared.orders(probe, dummy[0], top_k=40)
        exact_top40_probes += result.lexical_top == rank[:40]
    return {"density": density, "rows": count,
            "mean_overview_characters": round(sum(len(d.overview) for d in documents) / count, 1),
            "distinct_grams": len(lexical.idf), "gram_postings": postings,
            "prepared_posting_array_bytes": lexical.rows.nbytes + lexical.weights.nbytes,
            "baseline_lexical_build_seconds": round(baseline_seconds, 4),
            "prepared_index_build_seconds": round(prepared_seconds, 4),
            "parity_probes": len(probes), "exact_lexical_score_probes": exact_score_probes,
            "exact_lexical_ranking_probes": exact_rank_probes, "exact_lexical_top40_probes": exact_top40_probes,
            "max_absolute_score_delta": max_absolute_score_delta}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=_ROWS_DEFAULT)
    args = parser.parse_args(argv)
    if not 1 <= args.rows <= _ROWS_MAX:
        parser.error("rows must be between 1 and 2000")
    print(json.dumps({"scope": "synthetic_qa_only_no_e5_no_rss",
                      "runs": [measure(args.rows, density) for density in ("low", "high")]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

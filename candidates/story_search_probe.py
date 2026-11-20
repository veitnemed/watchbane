"""Offline native QA for the production hybrid search service on an explicit tiny corpus."""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

_MAX_CASE_BYTES = 32768


def _read_cases(path: Path):
    with path.open("rb") as file:
        data = file.read(_MAX_CASE_BYTES + 1)
    if len(data) > _MAX_CASE_BYTES:
        raise ValueError("QA cases exceed the bounded input size")
    cases = json.loads(data.decode("utf-8-sig"))
    if not isinstance(cases, dict) or set(cases) != {"films", "queries", "out_of_scope"}:
        raise ValueError("Invalid QA case structure")
    films, queries, rejected = (cases[name] for name in ("films", "queries", "out_of_scope"))
    if not isinstance(films, list) or not 3 <= len(films) <= 6:
        raise ValueError("Expected 3–6 QA films")
    film_ids = set()
    for row in films:
        if not isinstance(row, dict) or set(row) != {"key", "title", "overview", "year"}:
            raise ValueError("Invalid QA film")
        key, title, overview, year = (row[name] for name in ("key", "title", "overview", "year"))
        if (not isinstance(key, str) or not key.isascii() or not key.isalnum() or key in film_ids
                or not isinstance(title, str) or not 1 <= len(title.strip()) <= 120
                or not isinstance(overview, str) or not 1 <= len(overview.strip()) <= 1000
                or type(year) is not int or not 1895 <= year <= 2026):
            raise ValueError("Invalid or duplicated QA film data")
        film_ids.add(key)

    if not isinstance(queries, list) or len(queries) != len(film_ids):
        raise ValueError("Expected one positive probe per QA film")
    expected_ids, seen_queries = set(), set()
    for row in queries:
        if not isinstance(row, dict) or set(row) != {"text", "top1"}:
            raise ValueError("Invalid QA query")
        query, key = row["text"], row["top1"]
        if (not isinstance(query, str) or not 1 <= len(query.strip()) <= 300 or query in seen_queries
                or not isinstance(key, str) or key not in film_ids or key in expected_ids):
            raise ValueError("Invalid or duplicated QA query")
        seen_queries.add(query)
        expected_ids.add(key)
    if not isinstance(rejected, str) or not 1 <= len(rejected.strip()) <= 300 or rejected in seen_queries:
        raise ValueError("Expected one distinct instruction-style negative control")
    return films, queries, rejected


def _build_semantic_engine(films, model_dir: Path):
    from candidates.story_search import StoryDocument
    from candidates.story_semantic import SemanticStorySearch
    from candidates.story_service import create_story_search

    documents = [StoryDocument(row["key"], row["title"], row["overview"], "movie",
                               "Изолированный QA", year=row["year"]) for row in films]
    engine = create_story_search(documents, model_dir)
    if not isinstance(engine, SemanticStorySearch) or engine.encoder.variant != "fp32":
        raise ValueError("The frozen QA must use the pinned FP32 semantic engine")
    return engine


def _run_cases(engine, films, queries, rejected: str) -> dict:
    from candidates.story_search import OUT_OF_SCOPE_NOTICE

    ranks = []
    for query in queries:
        response = engine.search(query["text"], limit=len(films))
        ranks.append(next((i for i, hit in enumerate(response.hits, 1)
                           if hit.document.key == query["top1"]), None))
    negative = engine.search(rejected, limit=len(films))
    negative_rejected = not negative.hits and negative.notice == OUT_OF_SCOPE_NOTICE
    top1 = sum(rank == 1 for rank in ranks)
    passed = top1 == len(queries) and negative_rejected
    return {"status": "ok" if passed else "expectation_failed", "search_tested": True,
            "backend": "semantic_f32", "corpus_size": len(films), "positive_total": len(queries),
            "top1_correct": top1, "expected_ranks": ranks, "instruction_rejected": negative_rejected,
            "gui_tested": False, "collection_tested": False}


def write_story_search_check(model_dir: str | Path, cases_path: str | Path, output_path: str | Path) -> int:
    model_path, report_path = Path(model_dir), Path(output_path)
    if report_path.resolve().is_relative_to(model_path.resolve()):
        raise ValueError("The report must be outside the model directory")
    with report_path.open("x", encoding="utf-8") as file:
        result = {"status": "invalid_cases", "search_tested": False, "gui_tested": False,
                  "collection_tested": False}
        try:
            films, queries, rejected = _read_cases(Path(cases_path))
        except (OSError, ValueError):
            pass
        else:
            result["status"] = "engine_or_query_failed"
            try:
                from storage import profiles
                previous = profiles.get_base_data_dir()
                with TemporaryDirectory(prefix="watchbane-native-story-qa-", dir=report_path.parent) as scratch:
                    profiles.set_base_data_dir(scratch)
                    try:
                        engine = _build_semantic_engine(films, model_path)
                        result = _run_cases(engine, films, queries, rejected)
                    finally:
                        profiles.set_base_data_dir(previous)
            except Exception:
                # The machine-readable report contains no model path or catalogue text.
                pass
        json.dump(result, file)
        file.write("\n")
    return 0 if result["status"] == "ok" else 1

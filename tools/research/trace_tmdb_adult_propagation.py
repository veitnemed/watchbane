"""Audit fresh TMDb movie adult propagation in an isolated Watchbane runtime.

The tool is deliberately diagnostic: it does not repair candidates or use the
user profile.  Evidence contains only signal states, never titles, IDs, raw
TMDb responses, or credentials.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


class AdultTraceError(RuntimeError):
    """Raised when a requested audit cannot safely run."""


def _status(value: object, *, present: bool = True) -> str:
    if not present:
        return "lost"
    if value is None:
        return "null"
    return "present"


def _fixture_details(adult: bool | None, *, tmdb_id: int) -> dict[str, Any]:
    return {
        "id": tmdb_id,
        "adult": adult,
        "title": "Synthetic adult trace",
        "original_title": "Synthetic adult trace",
        "release_date": "2020-01-01",
        "genres": [{"id": 18, "name": "Drama"}],
        "production_countries": [{"iso_3166_1": "US", "name": "United States"}],
        "original_language": "en",
        "vote_average": 8.0,
        "vote_count": 1000,
        "popularity": 30.0,
        "poster_path": "/adult-trace.jpg",
        "overview": "A neutral dramatic story.",
    }


def _discover_stub(details: dict[str, Any]) -> dict[str, Any]:
    """Create only the fields Discover normally provides; no adult is copied."""
    return {
        "id": details.get("id"),
        "title": details.get("title"),
        "original_title": details.get("original_title"),
        "release_date": details.get("release_date"),
        "genre_ids": [item.get("id") for item in details.get("genres") or [] if isinstance(item, dict)],
        "origin_country": ["US"],
        "original_language": details.get("original_language"),
        "vote_average": details.get("vote_average"),
        "vote_count": details.get("vote_count"),
        "popularity": details.get("popularity"),
        "poster_path": details.get("poster_path"),
        "overview": details.get("overview"),
    }


def _stored_adult(candidate: dict[str, Any], db_path: Path) -> tuple[bool, Any]:
    from storage.sqlite.candidate_pool_repository import load_candidate_pool_dict, save_candidate_pool_dict

    save_candidate_pool_dict({"adult-trace": candidate}, path=db_path, purge_watched=False)
    stored = load_candidate_pool_dict(path=db_path).get("adult-trace") or {}
    return "adult" in stored, stored.get("adult")


def _eligibility(candidate: dict[str, Any], db_path: Path) -> dict[str, Any]:
    from candidates.recommendation_deck_service import RecommendationDeckService
    from candidates.safety.explicit_content import evaluate_explicit_sexual_content

    decision = evaluate_explicit_sexual_content(candidate)
    deck = RecommendationDeckService(
        pool_loader=lambda: {"adult-trace": candidate}, db_path=db_path
    ).build_deck({}, datetime(2026, 7, 21, tzinfo=timezone.utc), limit_active=1, reserve_size=0)
    shown = bool(deck.get("active") or deck.get("reserve"))
    return {
        "adult_based_blocked": bool(decision.blocked and decision.reason_code == "adult_flag"),
        "safety_reason_code": decision.reason_code,
        "shown_in_deck": shown,
        "explicit_content_excluded": int((deck.get("excluded") or {}).get("explicit_content") or 0),
    }


def trace_details(details: dict[str, Any], *, db_path: Path, scenario: str) -> dict[str, Any]:
    """Trace full Details and Details-merge paths without exposing media metadata."""
    from candidates.replenish.filter_replenisher import _candidate_from_discover, _merge_details_into_candidate
    from candidates.sources.tmdb.normalizer import prepare_tmdb_movie_candidate

    raw_present = "adult" in details
    raw_adult = details.get("adult")
    full = prepare_tmdb_movie_candidate(details, source_query={"language": "ru-RU"})
    base = _candidate_from_discover(
        _discover_stub(details), media_type="movie", bucket={"bucket_id": "adult-trace", "country": "US"}
    )
    replenished = _merge_details_into_candidate(base, details, language="ru-RU")

    paths: dict[str, dict[str, Any]] = {}
    for path_name, candidate in (("full_details", full), ("filter_details_merge", replenished)):
        candidate_present = "adult" in candidate
        stored_present, stored_adult = _stored_adult(candidate, db_path.with_name(f"{scenario}-{path_name}.sqlite3"))
        eligibility = _eligibility(candidate, db_path.with_name(f"{scenario}-{path_name}-deck.sqlite3"))
        candidate_loss = raw_present and (not candidate_present or candidate.get("adult") != raw_adult)
        storage_loss = candidate_present and (
            not stored_present or stored_adult != candidate.get("adult")
        )
        loss_layer = (
            "normalization_or_detail_merge"
            if candidate_loss
            else "storage_normalization_or_persistence"
            if storage_loss
            else None
        )
        paths[path_name] = {
            "raw_adult_status": _status(raw_adult, present=raw_present),
            "normalized_adult_status": _status(candidate.get("adult"), present=candidate_present),
            "stored_adult_status": _status(stored_adult, present=stored_present),
            "adult_value_matches_raw": candidate_present and candidate.get("adult") == raw_adult,
            "stored_value_matches_normalized": stored_present and stored_adult == candidate.get("adult"),
            "loss_layer": loss_layer,
            "eligibility": eligibility,
        }
    return {"scenario": scenario, "raw_adult_status": _status(raw_adult, present=raw_present), "paths": paths}


def fixture_traces(runtime_root: Path) -> list[dict[str, Any]]:
    return [
        trace_details(_fixture_details(value, tmdb_id=900_000 + index), db_path=runtime_root / "data" / "fixture.sqlite3", scenario=name)
        for index, (name, value) in enumerate((("adult_true", True), ("adult_false", False), ("adult_null", None)), start=1)
    ]


def _public_trace(trace: dict[str, Any]) -> dict[str, Any]:
    """Keep evidence restricted to statuses and decisions."""
    return trace


def _write_evidence(output: Path, payload: dict[str, Any]) -> None:
    output.mkdir(parents=True, exist_ok=True)
    (output / "adult_trace.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    failures = [
        {"scenario": trace["scenario"], "path": path, "loss_layer": result["loss_layer"]}
        for trace in payload["fixture_traces"] + ([payload["live_trace"]] if payload.get("live_trace") else [])
        for path, result in trace["paths"].items()
        if result["loss_layer"]
    ]
    summary = {"fixture_scenarios": len(payload["fixture_traces"]), "live_status": payload["live_status"], "loss_count": len(failures)}
    (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "failures.json").write_text(json.dumps(failures, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_audit(runtime_root: Path, *, output: Path, movie_id: int, fetch_details: Any) -> dict[str, Any]:
    """Run all fixture traces and one supplied live Details fetcher."""
    from config.app_paths import get_app_paths
    from tools.qa.isolation import apply_isolated_data_dir, write_isolation_marker

    isolated = apply_isolated_data_dir(runtime_root)
    paths = get_app_paths()
    if paths.database_path.parent.parent != isolated:
        raise AdultTraceError("WATCHBANE_DATA_DIR did not resolve to the requested isolated runtime.")
    write_isolation_marker(isolated, meta={"audit": "TMDB-1.3b"})
    traces = fixture_traces(isolated)
    live_trace = None
    live_status = "request_failed"
    try:
        details = fetch_details(int(movie_id))
        if not isinstance(details, dict):
            raise AdultTraceError("TMDb Details response is not an object.")
        live_trace = trace_details(details, db_path=paths.database_path, scenario="live_movie")
        live_status = "ok"
    except Exception as error:  # Evidence intentionally does not include response or token.
        live_status = f"request_failed:{type(error).__name__}"
    payload = {
        "audit": "TMDB-1.3b",
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "runtime_root": str(isolated),
        "isolation_marker": ".watchbane_qa_isolated",
        "live_status": live_status,
        "fixture_traces": [_public_trace(trace) for trace in traces],
        "live_trace": _public_trace(live_trace) if live_trace else None,
    }
    _write_evidence(output, payload)
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-root", type=Path, required=True, help="New isolated runtime root; never a user profile.")
    parser.add_argument("--movie-id", type=int, required=True, help="Explicit movie ID for one live Details request.")
    parser.add_argument("--output", type=Path, default=Path("evidence/tmdb_matrix_1_3b"))
    args = parser.parse_args(argv)

    def fetch(movie_id: int) -> dict[str, Any]:
        from apis.tmdb.client import get_movie_details
        return get_movie_details(movie_id, language="ru-RU")

    try:
        payload = run_audit(args.runtime_root, output=args.output.resolve(), movie_id=args.movie_id, fetch_details=fetch)
    except (AdultTraceError, ValueError, OSError) as error:
        parser.error(str(error))
    print(json.dumps({"audit": payload["audit"], "live_status": payload["live_status"], "evidence": str(args.output.resolve())}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

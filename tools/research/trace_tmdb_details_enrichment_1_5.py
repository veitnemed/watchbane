"""TMDB-1.5 isolated live acceptance for bounded deck Details enrichment.

Uses production composition:
  build_deck_details_enricher → RecommendationDeckService → merge → SQLite.

Evidence contains only aggregates and field-presence statuses. It never stores
titles, TMDb IDs, raw API responses, tokens, production paths, or user history.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

TASK_ID = "TMDB-1.5"
ACTIVE_LIMIT = 2
RESERVE_SIZE = 2
FILLER_COUNT = 20
# Well-known stable catalog IDs used only in-process; never written to evidence.
_MOVIE_FOCUS_IDS = (550, 278)
_TV_FOCUS_IDS = (1396, 1399)
_EXTRA_MOVIE_IDS = (680, 155, 13, 122, 424, 497)
_EXTRA_TV_IDS = (66732, 63174, 60735, 1418, 82856, 85271)


class TraceError(RuntimeError):
    """Raised when the acceptance harness cannot run safely."""


def _field_status(record: dict[str, Any], name: str) -> str:
    if name not in record:
        return "absent"
    value = record.get(name)
    if value is None:
        return "null"
    if value in ("", [], {}):
        return "empty"
    return "present"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _fingerprint_path(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    stat = path.stat()
    return {
        "exists": True,
        "sha256": _sha256_file(path),
        "size_bytes": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }


def _production_db_path() -> Path:
    from config.app_paths import DB_FILENAME, get_app_paths

    environment = {key: value for key, value in os.environ.items() if key != "WATCHBANE_DATA_DIR"}
    paths = get_app_paths(environ=environment)
    active_file = paths.data_dir / "active_profile.json"
    profile = "main"
    try:
        data = json.loads(active_file.read_text(encoding="utf-8-sig"))
        if isinstance(data, dict):
            raw = str(data.get("active_profile") or "main").strip().casefold()
            if raw and all(ch.isalnum() or ch in "_-" for ch in raw):
                profile = raw
    except (OSError, ValueError, json.JSONDecodeError):
        pass
    data_dir = paths.data_dir if profile == "main" else paths.data_dir / "profiles" / profile
    return data_dir / DB_FILENAME


def _redact_runtime(path: Path) -> str:
    return f"…/{path.name}/"


def _partial_candidate(
    *,
    slot: str,
    media_type: str,
    tmdb_id: int,
    final_score: float,
) -> dict[str, Any]:
    """Discover-like partial payload: no Details-only fields."""
    year = 2010 + (int(tmdb_id) % 14)
    return {
        "title": f"Partial {slot}",
        "original_title": f"Partial {slot}",
        "year": year,
        "media_type": media_type,
        "tmdb_id": int(tmdb_id),
        "final_score": float(final_score),
        "tmdb_score": 7.5,
        "tmdb_votes": 1000,
        "tmdb_popularity": 40.0,
        "country": "US",
        "country_codes": ["US"],
        "genres_tmdb": ["Drama"],
        "genres": ["Drama"],
        "poster_path": f"/partial-{slot}.jpg",
        "description": "Partial discover-shaped seed for TMDB-1.5 live acceptance.",
        "source": "tmdb_details_enrichment_1_5",
    }


def _build_seed_pool() -> dict[str, dict[str, Any]]:
    pool: dict[str, dict[str, Any]] = {}
    score = 200.0
    for index, tmdb_id in enumerate(_MOVIE_FOCUS_IDS):
        slot = f"movie_focus_{index + 1}"
        pool[slot] = _partial_candidate(slot=slot, media_type="movie", tmdb_id=tmdb_id, final_score=score)
        score -= 1.0
    for index, tmdb_id in enumerate(_TV_FOCUS_IDS):
        slot = f"tv_focus_{index + 1}"
        pool[slot] = _partial_candidate(slot=slot, media_type="tv", tmdb_id=tmdb_id, final_score=score)
        score -= 1.0
    extras: list[tuple[str, int]] = [("movie", item) for item in _EXTRA_MOVIE_IDS] + [
        ("tv", item) for item in _EXTRA_TV_IDS
    ]
    for index, (media_type, tmdb_id) in enumerate(extras):
        slot = f"window_{media_type}_{index + 1}"
        pool[slot] = _partial_candidate(slot=slot, media_type=media_type, tmdb_id=tmdb_id, final_score=score)
        score -= 1.0
    for index in range(FILLER_COUNT):
        slot = f"filler_{index + 1}"
        pool[slot] = _partial_candidate(
            slot=slot,
            media_type="movie" if index % 2 == 0 else "tv",
            tmdb_id=900_100 + index,
            final_score=20.0 - index,
        )
    return pool


def _preflight_token_and_network() -> dict[str, Any]:
    from apis.tmdb.client import check_api_available, load_tmdb_credentials

    try:
        load_tmdb_credentials()
    except Exception as error:  # noqa: BLE001 — map to SKIPPED without leaking secrets
        return {"ok": False, "reason": "no_token", "error_type": type(error).__name__}
    availability = check_api_available()
    if availability.get("ok") is True:
        return {"ok": True, "reason": None, "error_type": None}
    error_code = str(availability.get("error") or "network_error")
    if error_code == "missing_token":
        return {"ok": False, "reason": "no_token", "error_type": error_code}
    return {"ok": False, "reason": "network_error", "error_type": error_code}


def _movie_field_report(record: dict[str, Any]) -> dict[str, str]:
    return {
        "details_enrichment_contract_version": (
            "ok" if record.get("details_enrichment_contract_version") == 1 else "bad"
        ),
        "details_enrichment_status": (
            "ok" if record.get("details_enrichment_status") == "success" else "bad"
        ),
        "details_enriched_at": _field_status(record, "details_enriched_at"),
        "runtime": _field_status(record, "runtime"),
        "content_rating": _field_status(record, "content_rating"),
        "keywords": _field_status(record, "keywords"),
        "adult": _field_status(record, "adult"),
    }


def _tv_field_report(record: dict[str, Any]) -> dict[str, str]:
    return {
        "details_enrichment_contract_version": (
            "ok" if record.get("details_enrichment_contract_version") == 1 else "bad"
        ),
        "details_enrichment_status": (
            "ok" if record.get("details_enrichment_status") == "success" else "bad"
        ),
        "details_enriched_at": _field_status(record, "details_enriched_at"),
        "episode_run_time": _field_status(record, "episode_run_time"),
        "number_of_seasons": _field_status(record, "number_of_seasons"),
        "number_of_episodes": _field_status(record, "number_of_episodes"),
        "content_rating": _field_status(record, "content_rating"),
        "keywords": _field_status(record, "keywords"),
        "adult": _field_status(record, "adult"),
    }


def _is_enriched(record: dict[str, Any]) -> bool:
    return (
        record.get("details_enrichment_contract_version") == 1
        and record.get("details_enrichment_status") == "success"
        and bool(record.get("details_enriched_at"))
    )


def _focus_reports(reloaded: dict[str, dict[str, Any]]) -> dict[str, Any]:
    movies = []
    tvs = []
    for key, record in reloaded.items():
        if not isinstance(record, dict) or not _is_enriched(record):
            continue
        media = str(record.get("media_type") or "")
        if media == "movie" and len(movies) < 2:
            movies.append(_movie_field_report(record))
        elif media == "tv" and len(tvs) < 2:
            tvs.append(_tv_field_report(record))
    return {"movie_enriched_samples": movies, "tv_enriched_samples": tvs}


def _write_evidence(output: Path, payload: dict[str, Any]) -> None:
    output.mkdir(parents=True, exist_ok=True)
    (output / "live_acceptance.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    summary = {
        "task_id": TASK_ID,
        "verdict": payload.get("verdict"),
        "skip_reason": payload.get("skip_reason"),
        "preliminary_pool_size": (payload.get("counters") or {}).get("preliminary_candidates"),
        "details_request_cap": (payload.get("counters") or {}).get("details_request_cap"),
        "details_requests": (payload.get("counters") or {}).get("details_requests"),
        "enriched_after_reload": payload.get("enriched_after_reload"),
        "unenriched_after_reload": payload.get("unenriched_after_reload"),
        "production_unchanged": payload.get("production_immutability", {}).get("unchanged"),
    }
    (output / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _walk_forbidden(node: Any, *, path: str = "$") -> None:
    forbidden_keys = {
        "title",
        "original_title",
        "tmdb_id",
        "id",
        "name",
        "token",
        "authorization",
        "poster_path",
        "overview",
        "description",
    }
    if isinstance(node, dict):
        for key, value in node.items():
            key_text = str(key)
            if key_text.casefold() in forbidden_keys:
                raise TraceError(f"Evidence contains forbidden key {key_text!r} at {path}")
            _walk_forbidden(value, path=f"{path}.{key_text}")
        return
    if isinstance(node, list):
        for index, value in enumerate(node):
            _walk_forbidden(value, path=f"{path}[{index}]")
        return
    if isinstance(node, str):
        lowered = node.casefold()
        if "bearer " in lowered or "localappdata" in lowered or "appdata" in lowered:
            raise TraceError(f"Evidence contains forbidden string at {path}")
        if lowered.startswith("partial "):
            raise TraceError(f"Evidence leaked seed title at {path}")


def _assert_evidence_safe(output: Path) -> None:
    """Fail closed if evidence accidentally contains forbidden material."""
    for path in output.glob("*.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        _walk_forbidden(payload)


def run_live_acceptance(runtime_root: Path, *, output: Path) -> dict[str, Any]:
    from candidates.onboarding_service import build_deck_details_enricher
    from candidates.recommendation_deck_service import RecommendationDeckService
    from config.app_paths import get_app_paths
    from storage.sqlite.candidate_pool_repository import load_candidate_pool_dict, save_candidate_pool_dict
    from tools.qa.isolation import apply_isolated_data_dir, assert_runtime_is_isolated, write_isolation_marker

    production_before = _fingerprint_path(_production_db_path())
    isolated = assert_runtime_is_isolated(runtime_root)
    apply_isolated_data_dir(isolated)
    paths = get_app_paths()
    if paths.root != isolated:
        raise TraceError("WATCHBANE_DATA_DIR did not resolve to the requested isolated runtime.")
    write_isolation_marker(
        isolated,
        meta={"audit": TASK_ID, "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds")},
    )

    preflight = _preflight_token_and_network()
    base_payload: dict[str, Any] = {
        "task_id": TASK_ID,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "runtime_root_redacted": _redact_runtime(isolated),
        "isolation_marker": ".watchbane_qa_isolated",
        "composition": [
            "build_deck_details_enricher",
            "RecommendationDeckService",
            "candidate_pool_repository.merge",
        ],
        "active_limit": ACTIVE_LIMIT,
        "reserve_size": RESERVE_SIZE,
    }
    if not preflight["ok"]:
        payload = {
            **base_payload,
            "verdict": "SKIPPED",
            "skip_reason": preflight["reason"],
            "skip_error_type": preflight["error_type"],
            "counters": {},
            "production_immutability": {
                "before": production_before,
                "after": _fingerprint_path(_production_db_path()),
                "unchanged": _fingerprint_path(_production_db_path()) == production_before,
            },
        }
        _write_evidence(output, payload)
        _assert_evidence_safe(output)
        return payload

    seed = _build_seed_pool()
    preliminary_size = len(seed)
    db_path = paths.database_path
    save_candidate_pool_dict(seed, path=db_path, purge_watched=False)

    def pool_loader() -> dict[str, dict[str, Any]]:
        return load_candidate_pool_dict(path=db_path)

    service = RecommendationDeckService(
        pool_loader=pool_loader,
        db_path=db_path,
        candidate_enricher=build_deck_details_enricher(data_language="ru-RU"),
    )
    now = datetime.now(timezone.utc)
    deck = service.build_deck(
        {},
        now,
        limit_active=ACTIVE_LIMIT,
        reserve_size=RESERVE_SIZE,
    )
    counters = dict(deck.get("details_enrichment") or {})
    active_count = len(list(deck.get("active") or []))
    reserve_count = len(list(deck.get("reserve") or []))

    # Force connection turnover before reload checks.
    del service
    reloaded = load_candidate_pool_dict(path=db_path)
    enriched = [item for item in reloaded.values() if isinstance(item, dict) and _is_enriched(item)]
    unenriched = [item for item in reloaded.values() if isinstance(item, dict) and not _is_enriched(item)]
    focus = _focus_reports(reloaded)

    production_after = _fingerprint_path(_production_db_path())
    production_unchanged = production_after == production_before
    pool_not_fully_enriched = len(unenriched) > 0 and len(enriched) < preliminary_size
    cap_respected = int(counters.get("details_requests") or 0) <= int(counters.get("details_request_cap") or 0)
    movie_ok = len(focus["movie_enriched_samples"]) >= 2 and all(
        sample.get("details_enrichment_status") == "ok"
        and sample.get("details_enrichment_contract_version") == "ok"
        and sample.get("details_enriched_at") == "present"
        for sample in focus["movie_enriched_samples"]
    )
    tv_ok = len(focus["tv_enriched_samples"]) >= 2 and all(
        sample.get("details_enrichment_status") == "ok"
        and sample.get("details_enrichment_contract_version") == "ok"
        and sample.get("details_enriched_at") == "present"
        for sample in focus["tv_enriched_samples"]
    )

    passed = bool(
        production_unchanged
        and pool_not_fully_enriched
        and cap_respected
        and movie_ok
        and tv_ok
        and int(counters.get("details_success") or 0) >= 4
    )
    payload = {
        **base_payload,
        "verdict": "PASSED" if passed else "FAILED",
        "skip_reason": None,
        "counters": {
            "preliminary_candidates": int(counters.get("preliminary_candidates") or preliminary_size),
            "details_request_cap": int(counters.get("details_request_cap") or 0),
            "details_considered": int(counters.get("details_considered") or 0),
            "details_requests": int(counters.get("details_requests") or 0),
            "details_success": int(counters.get("details_success") or 0),
            "details_failed": int(counters.get("details_failed") or 0),
            "details_reused": int(counters.get("details_reused") or 0),
            "rejected_after_details": int(counters.get("rejected_after_details") or 0),
            "request_cap_reached": int(counters.get("request_cap_reached") or 0),
            "persisted_successes": int(counters.get("persisted_successes") or 0),
            "active_count": active_count,
            "reserve_count": reserve_count,
        },
        "enriched_after_reload": len(enriched),
        "unenriched_after_reload": len(unenriched),
        "pool_not_fully_enriched": pool_not_fully_enriched,
        "cap_respected": cap_respected,
        "focus_after_reload": focus,
        "checks": {
            "movie_ok": movie_ok,
            "tv_ok": tv_ok,
            "production_unchanged": production_unchanged,
            "pool_not_fully_enriched": pool_not_fully_enriched,
            "cap_respected": cap_respected,
        },
        "production_immutability": {
            "before": production_before,
            "after": production_after,
            "unchanged": production_unchanged,
            "production_db_absent": production_before is None,
        },
    }
    _write_evidence(output, payload)
    _assert_evidence_safe(output)
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--runtime-root",
        type=Path,
        required=True,
        help="New isolated runtime root; never a user profile.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("evidence/tmdb_matrix_1_5"),
        help="Ignored evidence directory (default: evidence/tmdb_matrix_1_5).",
    )
    args = parser.parse_args(argv)
    try:
        payload = run_live_acceptance(args.runtime_root, output=args.output.resolve())
    except (TraceError, ValueError, OSError) as error:
        parser.error(str(error))
    print(
        json.dumps(
            {
                "task_id": TASK_ID,
                "verdict": payload.get("verdict"),
                "skip_reason": payload.get("skip_reason"),
                "evidence": str(args.output.resolve()),
                "runtime_root_redacted": payload.get("runtime_root_redacted"),
            },
            ensure_ascii=False,
        )
    )
    if payload.get("verdict") == "FAILED":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

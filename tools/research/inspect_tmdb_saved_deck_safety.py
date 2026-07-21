"""Inspect active/reserve safety anomalies in an explicit SQLite copy.

TMDB-1.3c is an audit only.  The report is deliberately anonymised: it
contains signal states and decision categories, never title, TMDb ID, overview,
keywords, identity keys, or copied user history.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from candidates.models.keys import candidate_state_identity_keys
from candidates.recommendation_deck_service import RecommendationDeckService
from candidates.safety.explicit_content import evaluate_explicit_sexual_content
from storage.sqlite.candidate_pool_repository import save_candidate_pool_dict
from tools.research.export_tmdb_pool_snapshot import (
    ExportError,
    _fingerprint,
    _has_table,
    _json,
    _saved_states,
    resolve_source,
)


TASK_ID = "TMDB-1.3c"


def _state(value: Any) -> str:
    if value is None:
        return "null"
    if value in ("", [], {}):
        return "empty"
    return "present"


def _signal_summary(candidate: dict[str, Any]) -> dict[str, Any]:
    decision = evaluate_explicit_sexual_content(candidate)
    signals = tuple(decision.signals)
    return {
        "adult": {"stored_state": _state(candidate.get("adult")), "triggered": any(item == "adult=true" for item in signals)},
        "content_rating": {"stored_state": _state(candidate.get("content_rating")), "triggered": decision.reason_code == "explicit_content_rating"},
        "keywords": {"stored_state": _state(candidate.get("keywords")), "count": len(candidate.get("keywords") or []), "triggered": decision.reason_code == "explicit_keyword"},
        "overview": {"stored_state": _state(candidate.get("overview") or candidate.get("description")), "triggered": decision.reason_code == "explicit_phrase"},
        "decision": {"blocked": bool(decision.blocked), "reason_code": decision.reason_code, "signal_count": len(signals)},
    }


def _current_deck_result(pool: dict[str, dict[str, Any]], candidate: dict[str, Any], root: Path) -> dict[str, Any]:
    """Rebuild a disposable deck from stored candidates, never source DB."""
    db_path = root / "data" / "watchbane.sqlite3"
    save_candidate_pool_dict(pool, path=db_path, purge_watched=False)
    deck = RecommendationDeckService(pool_loader=lambda: pool, db_path=db_path).build_deck(
        {}, datetime.now(timezone.utc), limit_active=10, reserve_size=70
    )
    identities = set(candidate_state_identity_keys(candidate))
    shown = [item for item in list(deck.get("active") or []) + list(deck.get("reserve") or []) if identities.intersection(candidate_state_identity_keys(item))]
    return {
        "rebuilt_with_current_gate": True,
        "candidate_in_active_or_reserve": bool(shown),
        "explicit_content_excluded_count": int((deck.get("excluded") or {}).get("explicit_content") or 0),
    }


def inspect_database(database: Path, *, output: Path) -> dict[str, Any]:
    """Read a copied database and emit anonymised evidence for current anomalies."""
    output.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(f"{database.resolve().as_uri()}?mode=ro", uri=True)
    try:
        before = _fingerprint(database, conn)
        if not _has_table(conn, "candidate_records"):
            raise ExportError("Source database has no candidate_records table.")
        conn.row_factory = sqlite3.Row
        states = _saved_states(conn)
        pool: dict[str, dict[str, Any]] = {}
        anomalies: list[tuple[dict[str, Any], set[str], bool]] = []
        for row in conn.execute("SELECT pool_key, payload_json, created_at FROM candidate_records ORDER BY rowid"):
            payload, error = _json(row["payload_json"], {})
            if error or not isinstance(payload, dict):
                continue
            pool[str(row["pool_key"])] = payload
            identities = set(candidate_state_identity_keys(payload))
            states_here = {state for state in ("active", "reserve") if identities.intersection(states[state])}
            if states_here and evaluate_explicit_sexual_content(payload).blocked:
                anomalies.append((payload, states_here, bool(row["created_at"])))
        after = _fingerprint(database, conn)
        if before != after:
            raise ExportError("Read-only proof failed: source database changed during inspection.")
    finally:
        conn.close()

    reports = []
    for index, (candidate, saved_states, record_created_at_present) in enumerate(anomalies, start=1):
        with tempfile.TemporaryDirectory(prefix="tmdb-1.3c-", dir=output) as temp_root:
            rebuilt = _current_deck_result(pool, candidate, Path(temp_root))
        reports.append({
            "anomaly_ordinal": index,
            "current_saved_states": sorted(saved_states),
            "stored_safety": _signal_summary(candidate),
            "deck_provenance": {
                "candidate_record_created_at_present": record_created_at_present,
                "candidate_entered_deck_at": "not_reconstructible_from_current_deck_state",
                "safety_gate_historical_version": "not_reconstructible_from_stored_data",
            },
            "current_rebuild": rebuilt,
        })
    payload = {
        "task_id": TASK_ID,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_database": database.name,
        "read_only_proof": before == after,
        "anomaly_count": len(reports),
        "reports": reports,
    }
    (output / "saved_deck_safety_report.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "run_manifest.json").write_text(json.dumps({"task_id": TASK_ID, "source_database": database.name, "source_fingerprint": before, "read_only_proof": True, "command": "inspect_tmdb_saved_deck_safety.py --database <copy> --output <ignored evidence dir>"}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True, help="Explicit SQLite copy; production runtime is rejected.")
    parser.add_argument("--output", type=Path, default=Path("evidence/tmdb_matrix_1_3c"))
    args = parser.parse_args(argv)
    try:
        database = resolve_source(database=args.database, runtime_root=None)
        result = inspect_database(database, output=args.output.resolve())
    except (ExportError, OSError, sqlite3.Error, ValueError) as error:
        parser.error(str(error))
    print(json.dumps({"anomaly_count": result["anomaly_count"], "evidence": str(args.output.resolve())}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

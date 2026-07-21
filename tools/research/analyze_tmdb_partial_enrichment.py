"""Audit partial TMDb candidate enrichment from an explicit SQLite copy.

TMDB-1.3d is offline. It never calls TMDb and emits aggregate, privacy-safe
evidence only: no titles, IDs, identity keys, profile answers, or request params.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import sys
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.research.export_tmdb_pool_snapshot import ExportError, _connect_readonly, _fingerprint, _has_table, _json, resolve_source


TASK_ID = "TMDB-1.3d"
TRACED_FIELDS = ("runtime", "content_rating", "keywords")


def _present(value: Any) -> bool:
    return value not in (None, "", [], {})


def _cohort(payload: dict[str, Any]) -> str:
    states = tuple(_present(payload.get(field)) for field in TRACED_FIELDS)
    return "full" if all(states) else "partial" if not any(states) else "mixed"


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})")} if _has_table(conn, table) else set()


def _summary(values: list[dict[str, Any]]) -> dict[str, Any]:
    if not values:
        return {"records": 0}
    return {
        "records": len(values),
        **{f"{field}_count": len({value.get(field) for value in values}) for field in ("source", "source_version", "bucket", "profile", "created_at", "updated_at")},
        "details_enriched": {
            "true": sum(value["details_enriched"] is True for value in values),
            "false": sum(value["details_enriched"] is False for value in values),
            "missing_or_other": sum(value["details_enriched"] not in {True, False} for value in values),
        },
        "field_presence": {field: sum(value["fields"][field] for value in values) for field in TRACED_FIELDS},
        "sql_payload_conflicts": sum(value["sql_payload_conflict"] for value in values),
        "invalid_payloads": sum(value["invalid_payload"] for value in values),
        "source_query_present": sum(value["source_query_present"] for value in values),
        "completeness_present": sum(value["completeness_present"] for value in values),
    }


def _static_path_contract() -> dict[str, Any]:
    """Source-level facts; no acquisition path is executed."""
    return {
        "onboarding_discover_details": {
            "path": "Discover -> _fetch_details_for_result -> _merge_details_into_discover_result -> build_candidate_record_from_result -> merge_candidate_pool_dict",
            "details_appends": ["external_ids"], "copies_traced_fields": [],
            "evidence": ["candidates/onboarding/autofill.py:_details_append_to_response", "candidates/onboarding/autofill.py:_merge_details_into_discover_result", "candidates/onboarding/autofill.py:build_candidate_record_from_result", "storage/sqlite/candidate_pool_repository.py:merge_candidate_pool_dict"],
        },
        "filter_replenish_details": {
            "path": "Discover -> Details normalizer -> _merge_details_into_candidate -> merge_candidate_pool_dict",
            "copies_traced_fields": list(TRACED_FIELDS),
            "evidence": ["candidates/replenish/filter_replenisher.py:_merge_details_into_candidate"],
        },
        "full_tmdb_normalizer_importer": {
            "path": "Details -> normalizer -> importer/storage", "copies_traced_fields": list(TRACED_FIELDS),
            "evidence": ["candidates/sources/tmdb/normalizer.py", "candidates/sources/tmdb/importer.py"],
        },
        "legacy_or_historical": {
            "path": "legacy JSON import / older writer", "copies_traced_fields": "not_reconstructible_from_current_candidate_records",
            "evidence": ["storage/legacy_json/importer.py"],
        },
    }


def _request_summary(conn: sqlite3.Connection) -> dict[str, Any]:
    if not _has_table(conn, "candidate_autofill_requests"):
        return {"available": False, "details_requests_recorded": "not_reconstructible"}
    rows = list(conn.execute("SELECT endpoint, status, accepted_count, rejected_count FROM candidate_autofill_requests"))
    categories = Counter("details" if "/movie/" in str(row[0]) or "/tv/" in str(row[0]) else str(row[0]) for row in rows)
    return {
        "available": True, "request_count": len(rows), "endpoint_categories": dict(sorted(categories.items())),
        "status_counts": dict(sorted(Counter(str(row[1]) for row in rows).items())),
        "accepted_count": sum(int(row[2] or 0) for row in rows), "rejected_count": sum(int(row[3] or 0) for row in rows),
        "details_requests_recorded": "details" in categories,
        "limitation": "Discover audit rows do not prove whether per-candidate Details calls happened.",
    }


def _verdict(cohorts: dict[str, dict[str, Any]], requests: dict[str, Any], *, same_provenance: bool) -> dict[str, Any]:
    full, partial = cohorts["full"], cohorts["partial"]
    marker_conflict = full.get("details_enriched", {}).get("false", 0) > 0 or partial.get("details_enriched", {}).get("true", 0) > 0
    if same_provenance:
        return {
            "primary_category": "E_different_acquisition_or_historical_contract",
            "confidence": "strong_for_current_code_contract; limited_for_historical_writer_identity",
            "root_cause": "Current onboarding Details merge and candidate builder do not persist runtime, content_rating, or keywords. Full records therefore cannot be created solely by this current onboarding merge; they require a different or historical enrichment/write contract. Partial records are compatible with the current onboarding contract.",
            "details_enriched_reliability": "not_reliable" if marker_conflict else "cohort_consistent_only",
            "details_call_verdict": "not_reconstructible_from_stored_audit" if not requests.get("details_requests_recorded") else "details_audit_present",
            "next_product_task": "Ensure Details enrichment contract for persisted recommendation candidates",
        }
    return {"primary_category": "inconclusive", "confidence": "insufficient cohort separation in supplied database", "root_cause": "No split full/partial cohorts with common source provenance was available.", "details_enriched_reliability": "not_assessed", "details_call_verdict": "not_reconstructible_from_stored_audit", "next_product_task": None}


def analyze_database(database: Path, *, output: Path) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    conn = _connect_readonly(database)
    try:
        conn.row_factory = sqlite3.Row
        before = _fingerprint(database, conn)
        if not _has_table(conn, "candidate_records"):
            raise ExportError("Source database has no candidate_records table.")
        columns = _columns(conn, "candidate_records")
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        anomalies: list[dict[str, Any]] = []
        for row in conn.execute("SELECT rowid, * FROM candidate_records ORDER BY rowid"):
            payload, error = _json(row["payload_json"] if "payload_json" in row.keys() else None, {})
            payload = payload if isinstance(payload, dict) else {}
            sql = lambda key: row[key] if key in columns else None
            item = {"source": payload.get("source") or sql("source"), "source_version": payload.get("source_version"), "bucket": payload.get("source_bucket_id") or sql("source_bucket_id"), "profile": payload.get("onboarding_profile_id"), "created_at": sql("created_at"), "updated_at": sql("updated_at"), "details_enriched": payload.get("details_enriched"), "fields": {field: _present(payload.get(field)) for field in TRACED_FIELDS}, "invalid_payload": error is not None, "source_query_present": isinstance(payload.get("source_query"), dict), "completeness_present": "is_complete" in payload or "missing_fields" in payload, "sql_payload_conflict": any(field in columns and sql(field) not in (None, "") and payload.get(field) not in (None, "") and sql(field) != payload.get(field) for field in ("tmdb_id", "tmdb_score", "tmdb_votes"))}
            cohort = "invalid" if error else _cohort(payload)
            groups[cohort].append(item)
            if error:
                anomalies.append({"kind": "invalid_payload", "cohort": cohort})
            elif item["sql_payload_conflict"]:
                anomalies.append({"kind": "sql_payload_conflict", "cohort": cohort})
            elif item["details_enriched"] is True and cohort == "partial":
                anomalies.append({"kind": "details_marker_partial_fields", "cohort": cohort})
            elif item["details_enriched"] is False and cohort == "full":
                anomalies.append({"kind": "details_marker_full_fields", "cohort": cohort})
        after = _fingerprint(database, conn)
        if before != after:
            raise ExportError("Read-only proof failed: source database changed during analysis.")
        requests = _request_summary(conn)
    finally:
        conn.close()
    cohorts = {name: _summary(groups.get(name, [])) for name in ("full", "partial", "mixed", "invalid")}
    provenance_keys = ("source", "source_version", "bucket", "profile")
    same_provenance = bool(groups["full"] and groups["partial"]) and all(
        {item[key] for item in groups["full"]} == {item[key] for item in groups["partial"]} and len({item[key] for item in groups["full"]}) == 1
        for key in provenance_keys
    )
    verdict, paths = _verdict(cohorts, requests, same_provenance=same_provenance), _static_path_contract()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    manifest = {"task_id": TASK_ID, "run_at": now, "source_database": database.name, "source_fingerprint": before, "read_only_proof": True, "network_used": False, "command": "analyze_tmdb_partial_enrichment.py --database <copy> --output evidence/tmdb_matrix_1_3d"}
    result = {"task_id": TASK_ID, "cohorts": cohorts, "request_audit": requests, "path_contract": paths, "verdict": verdict}
    (output / "run_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "cohort_summary.json").write_text(json.dumps({"cohorts": cohorts, "request_audit": requests}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "path_comparison.json").write_text(json.dumps(paths, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "anomalies.jsonl").write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in anomalies), encoding="utf-8")
    (output / "verdict.json").write_text(json.dumps(verdict, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True, help="Explicit SQLite copy; production runtime is rejected.")
    parser.add_argument("--output", type=Path, default=Path("evidence/tmdb_matrix_1_3d"))
    args = parser.parse_args(argv)
    try:
        database = resolve_source(database=args.database, runtime_root=None)
        result = analyze_database(database, output=args.output.resolve())
    except (ExportError, OSError, sqlite3.Error, ValueError) as error:
        parser.error(str(error))
    print(json.dumps({"verdict": result["verdict"]["primary_category"], "evidence": str(args.output.resolve())}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

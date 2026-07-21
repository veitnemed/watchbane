"""Export a read-only tracing snapshot of an explicitly supplied candidate DB."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
from typing import Any

# Support both ``py -m tools.research...`` and the documented direct script
# invocation from the repository root.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from candidates.models.keys import candidate_state_identity_keys
from candidates.safety.explicit_content import evaluate_explicit_sexual_content
from config.app_paths import DB_FILENAME, get_app_paths
from desktop.candidates.presenters import build_candidate_readonly_card
from desktop.shared.detail.main_info import build_main_info_items, build_title_meta_text
from dataset.language import choose_display_overview, choose_display_title
from tools.qa.isolation import IsolationError, assert_runtime_is_isolated, real_watchbane_profile_root


TASK_ID = "TMDB-1.3"
SCHEMA_VERSION = "1.0"
EXPORTER_VERSION = "1.0"
RAW_UNAVAILABLE = "not_available_in_local_snapshot"
SNAPSHOT_FIELDS = (
    "adult", "title", "overview", "poster", "content_rating", "keywords",
    "runtime", "countries", "providers", "credits",
)


class ExportError(ValueError):
    """A source is unsafe or does not meet the read-only export contract."""


def _json(value: Any, default: Any) -> tuple[Any, str | None]:
    if value in (None, ""):
        return default, "missing_json"
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return default, "invalid_json"
    return parsed, None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _fingerprint(path: Path, conn: sqlite3.Connection) -> dict[str, Any]:
    stat = path.stat()
    return {
        "sha256": _sha256(path),
        "size_bytes": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "data_version": int(conn.execute("PRAGMA data_version").fetchone()[0]),
    }


def _connect_readonly(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)


def _has_table(conn: sqlite3.Connection, name: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)
    ).fetchone() is not None


def resolve_source(*, database: Path | None, runtime_root: Path | None) -> Path:
    if (database is None) == (runtime_root is None):
        raise ExportError("Specify exactly one of --database or --runtime-root.")
    production_root = real_watchbane_profile_root().resolve()
    production_db = get_app_paths(
        environ={key: value for key, value in __import__("os").environ.items() if key != "WATCHBANE_DATA_DIR"}
    ).database_path.resolve()
    if runtime_root is not None:
        try:
            root = assert_runtime_is_isolated(runtime_root, real_root=production_root)
        except IsolationError as error:
            raise ExportError(str(error)) from error
        path = (root / "data" / DB_FILENAME).resolve()
    else:
        path = Path(database).expanduser().resolve()
        if path == production_db or path.is_relative_to(production_root):
            raise ExportError("Refusing a database in the real Watchbane production runtime.")
    if not path.is_file():
        raise ExportError(f"Candidate database does not exist: {path}")
    return path


def _state(value: Any) -> str:
    if value is None:
        return "null"
    if value == "" or value == [] or value == {}:
        return "empty"
    return "present"


def _trace(value: Any, source: str | None, ui_value: Any = None) -> dict[str, Any]:
    state = _state(value)
    return {
        "raw_api": {"state": RAW_UNAVAILABLE, "value": None, "source_field": None},
        "normalized": {"state": state, "value": value, "source_field": source},
        "stored": {"state": state, "value": value, "source_field": f"payload_json.{source}" if source else None},
        "ui_projection": {"state": _state(ui_value), "value": ui_value, "source_field": "production_presenter"},
    }


def _selection(value: Any, source: str | None, *, fallback: str = "none", reason: str) -> dict[str, Any]:
    return {
        "selected_value": str(value) if value not in (None, "") else None,
        "source_field": source,
        "source_language": "ru" if fallback == "requested" else ("en" if fallback == "english" else None),
        "source_region": "RU" if fallback == "requested" else None,
        "fallback_level": fallback,
        "selection_reason": reason,
    }


def _numbers(values: Any) -> list[float]:
    return [float(value) for value in values or [] if isinstance(value, (int, float)) and not isinstance(value, bool)]


def _names(values: Any) -> list[str]:
    result = []
    for value in values or []:
        name = value.get("name") if isinstance(value, dict) else value
        if name not in (None, ""):
            result.append(str(name))
    return result


def _identity(row: dict[str, Any], payload: dict[str, Any]) -> tuple[str, str, bool]:
    media_type = str(row.get("media_type") or payload.get("media_type") or "").strip().lower()
    tmdb_id = row.get("tmdb_id") if row.get("tmdb_id") is not None else payload.get("tmdb_id")
    if tmdb_id not in (None, ""):
        return f"{media_type}:tmdb:{tmdb_id}", "tmdb", False
    title = str(payload.get("title") or row.get("title") or "").strip().casefold()
    return f"{media_type}:legacy:{title}:{row.get('year') or payload.get('year') or ''}", "legacy", True


def _saved_states(conn: sqlite3.Connection) -> dict[str, set[str]]:
    states: dict[str, set[str]] = {"active": set(), "reserve": set(), "watchlist": set(), "hidden": set(), "shown": set(), "watched": set()}
    if _has_table(conn, "candidate_actions"):
        for identity, action in conn.execute("SELECT identity_key, action FROM candidate_actions"):
            if action in states:
                states[str(action)].add(str(identity))
    if _has_table(conn, "candidate_impressions"):
        states["shown"] = {str(row[0]) for row in conn.execute("SELECT identity_key FROM candidate_impressions")}
    if _has_table(conn, "watched_records"):
        for media_type, tmdb_id in conn.execute("SELECT media_type, tmdb_id FROM watched_records WHERE tmdb_id IS NOT NULL"):
            states["watched"].add(f"{media_type}:tmdb:{tmdb_id}")
    if _has_table(conn, "recommendation_deck_state"):
        row = conn.execute("SELECT state_json FROM recommendation_deck_state WHERE singleton_id = 1").fetchone()
        deck, _ = _json(row[0], {}) if row else ({}, "missing_json")
        if isinstance(deck, dict):
            for bucket in ("active", "reserve"):
                for candidate in deck.get(bucket) or []:
                    if isinstance(candidate, dict):
                        states[bucket].update(candidate_state_identity_keys(candidate))
    return states


def _ui_projection(payload: dict[str, Any]) -> dict[str, Any]:
    card = build_candidate_readonly_card(payload, data_language="ru")
    title = choose_display_title(payload, "ru")
    overview = choose_display_overview(payload, "ru")
    return {
        "display_title": title,
        "overview": overview,
        "title_meta": build_title_meta_text(card, data_language="ru"),
        "main_info": build_main_info_items(card, data_language="ru"),
        "poster_state": "present" if card.get("poster_url") or card.get("poster_path") else "missing",
    }


def _snapshot(row: dict[str, Any], states: dict[str, set[str]], now: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    payload, json_error = _json(row.get("payload_json"), {})
    payload = payload if isinstance(payload, dict) else {}
    identity, reliability, legacy = _identity(row, payload)
    media_type = str(row.get("media_type") or payload.get("media_type") or "tv").lower()
    tmdb_id = row.get("tmdb_id") if row.get("tmdb_id") not in (None, "") else payload.get("tmdb_id")
    ui = _ui_projection(payload) if json_error is None else {"projection_status": "not_available_invalid_payload"}
    display_title = ui.get("display_title")
    title_fallback = "requested" if display_title == payload.get("title") else "first_available"
    runtime = payload.get("episode_run_time") if media_type == "tv" else payload.get("runtime") or payload.get("runtime_minutes")
    episodes = _numbers(payload.get("episode_run_time")) if media_type == "tv" else []
    providers = _names(payload.get("watch_providers") or payload.get("watch_providers_ru"))
    safety = evaluate_explicit_sexual_content(payload) if json_error is None else None
    own_identities = set(candidate_state_identity_keys(payload)) if payload else {identity}
    own_identities.add(identity)
    status = {name: bool(own_identities.intersection(values)) for name, values in states.items()}
    anomalies: list[dict[str, Any]] = []
    if json_error:
        anomalies.append({"identity": identity, "kind": json_error})
    for field, sql_name in (("tmdb_id", "tmdb_id"), ("tmdb_score", "tmdb_score"), ("tmdb_votes", "tmdb_votes")):
        if row.get(sql_name) is not None and payload.get(field) is not None and row[sql_name] != payload[field]:
            anomalies.append({"identity": identity, "kind": "sql_payload_conflict", "field": field})
    if legacy:
        anomalies.append({"identity": identity, "kind": "legacy_identity"})
    if not display_title:
        anomalies.append({"identity": identity, "kind": "missing_display_title"})
    if safety and safety.blocked and (status["active"] or status["reserve"]):
        anomalies.append({"identity": identity, "kind": "saved_deck_safety_anomaly", "reason": safety.reason_code})
    raw = {"status": RAW_UNAVAILABLE, "reason": "raw TMDb response is not stored with candidate_records"}
    traces = {field: _trace(payload.get(field), field, ui.get("display_title") if field == "title" else ui.get("overview") if field == "overview" else None) for field in SNAPSHOT_FIELDS}
    snapshot = {
        "snapshot_schema_version": SCHEMA_VERSION,
        "snapshot_id": identity,
        "record_id": str(row.get("pool_key") or identity),
        "tmdb_id": int(tmdb_id) if str(tmdb_id or "").isdigit() else None,
        "media_type": media_type if media_type in {"movie", "tv"} else "tv",
        "sample_group": "local_candidate_pool",
        "fetched_at": now,
        "app_commit": _git_commit(),
        "app_version": _app_version(),
        "request": {"endpoint": "not_available_in_local_snapshot", "append_to_response": [], "request_language": None, "request_region": None, "original_language": payload.get("original_language")},
        "identity_reliability": reliability,
        "raw_api": raw,
        "layers": {"raw_api": raw, "normalized": {"source": "reconstructed_from_stored_payload", "fields": payload}, "stored": {"sql_columns": {key: value for key, value in row.items() if key != "payload_json"}, "payload_fields": payload, "meta_fields": {}}, "ui_projection": ui},
        "field_traces": traces,
        "provenance": {"title": _selection(display_title, "payload_json.title", fallback=title_fallback, reason="existing display-title helper"), "overview": _selection(ui.get("overview"), "payload_json.overview", fallback="first_available", reason="existing display-overview helper"), "poster": _selection(payload.get("poster_path") or payload.get("poster_url"), "payload_json.poster_path", fallback="requested", reason="readonly card poster hints"), "certification": _selection(payload.get("content_rating"), "payload_json.content_rating", reason="stored normalized field"), "providers": _selection(", ".join(providers) if providers else None, "payload_json.watch_providers", reason="stored normalized provider names")},
        "diagnostics": {"adult": {"raw_adult": None, "normalized_adult": payload.get("adult") if isinstance(payload.get("adult"), bool) else None, "stored_adult": payload.get("adult") if isinstance(payload.get("adult"), bool) else None, "safety_adult_signal_used": bool(safety and payload.get("adult") is not None), "adult_lost_in_normalization": False}, "certification": {"available_ratings": [], "selected_rating": payload.get("content_rating") if isinstance(payload.get("content_rating"), str) else None, "selected_country": None, "selection_reason": "local normalized field only"}, "countries": {"origin_country_codes": [str(v) for v in payload.get("origin_country") or []], "production_country_codes": [str(v.get("iso_3166_1")) for v in payload.get("production_countries") or [] if isinstance(v, dict) and v.get("iso_3166_1")], "normalized_country_codes": [str(v) for v in payload.get("country_codes") or []]}, "tv_runtime": {"episode_run_time_raw": episodes, "episode_run_time_selected": episodes[0] if episodes else None, "selection_strategy": "first_value" if episodes else "not_applicable" if media_type == "movie" else "none"}, "providers": {"provider_region": None, "provider_checked_at": None, "providers": [{"provider_type": "flatrate", "provider_names": providers}] if providers else []}, "credits": {"raw_credits_type": "not_requested", "actors_extracted": _names(payload.get("actors_top")), "crew_extracted": _names(payload.get("crew_top")), "extraction_strategy": "stored normalized payload"}},
        "saved_state": status,
    }
    return snapshot, anomalies


def _git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _app_version() -> str:
    try:
        return (Path(__file__).resolve().parents[2] / "VERSION.md").read_text(encoding="utf-8").splitlines()[0].strip()
    except OSError:
        return "unknown"


def export_snapshot(database: Path, output: Path) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    conn = _connect_readonly(database)
    try:
        before = _fingerprint(database, conn)
        if not _has_table(conn, "candidate_records"):
            raise ExportError("Source database has no candidate_records table.")
        conn.row_factory = sqlite3.Row
        rows = [dict(row) for row in conn.execute("SELECT rowid, * FROM candidate_records ORDER BY rowid")]
        states = _saved_states(conn)
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        seen: set[str] = set()
        snapshots: list[dict[str, Any]] = []
        anomalies: list[dict[str, Any]] = []
        for row in rows:
            payload, _ = _json(row.get("payload_json"), {})
            identity, _, _ = _identity(row, payload if isinstance(payload, dict) else {})
            if identity in seen:
                anomalies.append({"identity": identity, "kind": "duplicate_identity", "rowid": row["rowid"]})
                continue
            seen.add(identity)
            snapshot, row_anomalies = _snapshot(row, states, now)
            snapshots.append(snapshot)
            anomalies.extend(row_anomalies)
        after = _fingerprint(database, conn)
        if before != after:
            raise ExportError("Read-only proof failed: source database changed during export.")
    finally:
        conn.close()
    _write_evidence(output, snapshots, anomalies, before, database, len(rows), now)
    return {"records": len(rows), "exported": len(snapshots), "anomalies": len(anomalies), "output": str(output)}


def _write_evidence(output: Path, snapshots: list[dict[str, Any]], anomalies: list[dict[str, Any]], fingerprint: dict[str, Any], database: Path, record_count: int, now: str) -> None:
    (output / "pool_snapshot.jsonl").write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in snapshots), encoding="utf-8")
    (output / "anomalies.jsonl").write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in anomalies), encoding="utf-8")
    def missing(item: dict[str, Any], field: str) -> bool:
        return item["layers"]["stored"]["payload_fields"].get(field) in (None, "", [], {})

    def aggregate(items: list[dict[str, Any]]) -> dict[str, int]:
        return {
            "records": len(items),
            "legacy_records": sum(item["identity_reliability"] == "legacy" for item in items),
            "missing_title": sum(not item["layers"]["ui_projection"].get("display_title") for item in items),
            "missing_overview": sum(not item["layers"]["ui_projection"].get("overview") for item in items),
            "missing_poster": sum(item["layers"]["ui_projection"].get("poster_state") == "missing" for item in items),
            "missing_country_codes": sum(missing(item, "country_codes") for item in items),
            "missing_runtime": sum(missing(item, "runtime") and missing(item, "episode_run_time") for item in items),
            "missing_content_rating": sum(missing(item, "content_rating") for item in items),
            "missing_adult": sum(missing(item, "adult") for item in items),
            "missing_keywords": sum(missing(item, "keywords") for item in items),
            "missing_providers": sum(missing(item, "watch_providers") and missing(item, "watch_providers_ru") for item in items),
            "ui_projection_omissions": sum(not item["layers"]["ui_projection"].get("display_title") for item in items),
        }

    movie = [item for item in snapshots if item["media_type"] == "movie"]
    tv = [item for item in snapshots if item["media_type"] == "tv"]
    summary = {
        "candidate_records": record_count,
        "unique_identities": len(snapshots),
        "duplicates": record_count - len(snapshots),
        "invalid_payloads": sum(item["kind"] == "invalid_json" for item in anomalies),
        "sql_payload_metric_conflicts": sum(item["kind"] == "sql_payload_conflict" for item in anomalies),
        "active_reserve_safety_anomalies": sum(item["kind"] == "saved_deck_safety_anomaly" for item in anomalies),
        "localization_fallback": {"requested": sum(item["provenance"]["title"]["fallback_level"] == "requested" for item in snapshots), "english": sum(item["provenance"]["title"]["fallback_level"] == "english" for item in snapshots), "original_or_other": sum(item["provenance"]["title"]["fallback_level"] not in {"requested", "english"} for item in snapshots)},
        "all": aggregate(snapshots),
        "movie": aggregate(movie),
        "tv": aggregate(tv),
        "anomaly_count": len(anomalies),
    }
    (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest = {"task_id": TASK_ID, "schema_version": SCHEMA_VERSION, "exporter_version": EXPORTER_VERSION, "run_at": now, "source_database": database.name, "source_fingerprint": fingerprint, "record_count": record_count, "export_count": len(snapshots), "error_count": len(anomalies), "read_only_proof": True, "command": "export_tmdb_pool_snapshot.py --database <copy> --output <ignored evidence dir>"}
    (output / "run_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with (output / "pool_snapshot.csv").open("w", newline="", encoding="utf-8") as target:
        writer = csv.DictWriter(target, fieldnames=["record_id", "media_type", "tmdb_id", "identity_reliability", "adult_missing", "content_rating_missing", "ui_projection_missing"])
        writer.writeheader()
        for item in snapshots:
            payload = item["layers"]["stored"]["payload_fields"]
            writer.writerow({"record_id": item["record_id"], "media_type": item["media_type"], "tmdb_id": item["tmdb_id"], "identity_reliability": item["identity_reliability"], "adult_missing": payload.get("adult") is None, "content_rating_missing": not payload.get("content_rating"), "ui_projection_missing": not item["layers"]["ui_projection"].get("display_title")})
    with (output / "summary.csv").open("w", newline="", encoding="utf-8") as target:
        fields = ["candidate_records", "unique_identities", "duplicates", "invalid_payloads", "sql_payload_metric_conflicts", "active_reserve_safety_anomalies", "anomaly_count"]
        writer = csv.DictWriter(target, fieldnames=fields)
        writer.writeheader(); writer.writerow({field: summary[field] for field in fields})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--database", type=Path)
    source.add_argument("--runtime-root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        database = resolve_source(database=args.database, runtime_root=args.runtime_root)
        result = export_snapshot(database, args.output.resolve())
    except (ExportError, OSError, sqlite3.Error) as error:
        parser.error(str(error))
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

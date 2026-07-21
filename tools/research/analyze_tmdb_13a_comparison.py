"""Build privacy-safe TMDB-1.3a comparison artifacts from ignored evidence."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sqlite3
from typing import Any


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _lines(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _missing(payload: dict[str, Any], field: str) -> bool:
    return payload.get(field) in (None, "", [], {})


def _real_metrics(snapshots: list[dict[str, Any]], summary: dict[str, Any]) -> dict[str, Any]:
    payloads = [item["layers"]["stored"]["payload_fields"] for item in snapshots]
    movie = [payload for payload in payloads if payload.get("media_type") == "movie"]
    tv = [payload for payload in payloads if payload.get("media_type") == "tv"]
    return {
        "records": len(payloads),
        "movie_count": len(movie), "tv_count": len(tv),
        "poster_missing": sum(_missing(p, "poster_path") and _missing(p, "poster_url") for p in payloads),
        "movie_runtime_missing": sum(_missing(p, "runtime") and _missing(p, "runtime_minutes") for p in movie),
        "tv_runtime_missing": sum(_missing(p, "episode_run_time") for p in tv),
        "providers_missing": sum(_missing(p, "watch_providers") and _missing(p, "watch_providers_ru") for p in payloads),
        "keywords_missing": sum(_missing(p, "keywords") for p in payloads),
        "adult_missing": sum(_missing(p, "adult") for p in payloads),
        "content_rating_missing": sum(_missing(p, "content_rating") for p in payloads),
        "en_fallback": int(summary["localization_fallback"]["english"]),
        "invalid_payload": int(summary["invalid_payloads"]),
        "safety_anomalies": int(summary["active_reserve_safety_anomalies"]),
        "country_codes_missing": sum(_missing(p, "country_codes") for p in payloads),
        "provider_region_missing": sum(True for _ in payloads),
        "provider_timestamp_missing": sum(True for _ in payloads),
    }


def _synthetic_metrics(summary: dict[str, Any]) -> dict[str, Any]:
    all_values = summary["all"]
    return {
        "records": int(summary["candidate_records"]),
        "poster_missing": int(all_values["missing_poster"]),
        "movie_runtime_missing": int(summary["movie"]["missing_runtime"]),
        "tv_runtime_missing": int(summary["tv"]["missing_runtime"]),
        "providers_missing": int(all_values["missing_providers"]),
        "keywords_missing": int(all_values["missing_keywords"]),
        "adult_missing": int(all_values["missing_adult"]),
        "content_rating_missing": int(all_values["missing_content_rating"]),
        "en_fallback": int(summary["localization_fallback"]["english"]),
        "invalid_payload": int(summary["invalid_payloads"]),
    }


def build_comparison(real_dir: Path, synthetic_dirs: list[Path], output: Path, snapshot_db: Path | None = None) -> dict[str, Any]:
    real_summary = _load(real_dir / "summary.json")
    snapshots = _lines(real_dir / "pool_snapshot.jsonl")
    real = _real_metrics(snapshots, real_summary)
    synthetic = {path.name: _synthetic_metrics(_load(path / "summary.json")) for path in synthetic_dirs}
    output.mkdir(parents=True, exist_ok=True)
    traces = []
    for kind, predicate in (("poster", lambda p: not _missing(p, "poster_path") or not _missing(p, "poster_url")), ("movie_runtime", lambda p: p.get("media_type") == "movie"), ("tv_runtime", lambda p: p.get("media_type") == "tv")):
        item = next((snap for snap in snapshots if predicate(snap["layers"]["stored"]["payload_fields"])), None)
        if item is None:
            traces.append({"kind": kind, "status": "not_applicable_no_matching_real_record"})
            continue
        payload = item["layers"]["stored"]["payload_fields"]
        ui = item["layers"]["ui_projection"]
        traces.append({"kind": kind, "status": "available", "stored": {"poster_path": bool(payload.get("poster_path")), "poster_url": bool(payload.get("poster_url")), "runtime": payload.get("runtime") is not None or payload.get("runtime_minutes") is not None, "episode_runtime_count": len(payload.get("episode_run_time") or [])}, "ui": {"poster_state": ui.get("poster_state"), "title_present": bool(ui.get("display_title")), "overview_present": bool(ui.get("overview"))}})
    cache_entries = None
    if snapshot_db is not None:
        conn = sqlite3.connect(f"{snapshot_db.resolve().as_uri()}?mode=ro", uri=True)
        try:
            cache_entries = int(conn.execute("SELECT COUNT(*) FROM poster_cache_entries").fetchone()[0])
        finally:
            conn.close()
    result = {"real_pool": real, "poster_cache_entries": cache_entries, "synthetic": synthetic, "finding_classes": {"poster_metadata": "synthetic-only limitation" if real["poster_missing"] == 0 else "real-pool data gap", "adult": "confirmed production data gap" if real["adult_missing"] else "not applicable", "tv_runtime": "not applicable" if real["tv_count"] == 0 else "real-pool data gap", "raw_api": "inconclusive without raw API"}, "representative_trace_count": len(traces)}
    (output / "synthetic_vs_real.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "representative_traces.json").write_text(json.dumps(traces, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    fields = ["profile", "records", "poster_missing", "movie_runtime_missing", "tv_runtime_missing", "providers_missing", "keywords_missing", "adult_missing", "content_rating_missing", "en_fallback", "invalid_payload"]
    with (output / "synthetic_vs_real.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields); writer.writeheader()
        for profile, values in synthetic.items(): writer.writerow({"profile": profile, **values})
        writer.writerow({"profile": "Real pool", **{key: real.get(key) for key in fields if key != "profile"}})
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--real", type=Path, required=True)
    parser.add_argument("--synthetic", type=Path, nargs=3, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--snapshot-db", type=Path)
    args = parser.parse_args(argv)
    print(json.dumps(build_comparison(args.real, args.synthetic, args.output, args.snapshot_db), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

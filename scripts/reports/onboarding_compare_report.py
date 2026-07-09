"""Build before/after onboarding scenario comparison reports."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


REPORT_ROOT = Path("reports/onboarding")
RAW_DIR = REPORT_ROOT / "raw"
ANALYSIS_DIR = REPORT_ROOT / "analysis"
BASELINES_DIR = REPORT_ROOT / "baselines"
NOT_CAPTURED = "not_captured"

COMPARE_METRICS: dict[str, tuple[str, str, str]] = {
    "jp_kr_garbage_rate": ("scenario", "ru-manual-jp-kr", "garbage_rate"),
    "us_gb_new_movies_garbage_rate": ("scenario", "ru-foreign-new-movies-us-gb", "garbage_rate"),
    "ru_tv_manual_serious_2010_created_count": ("scenario", "ru-tv-manual-serious-2010", "created_count"),
    "details_requests": ("sum", "*", "details_requests"),
    "missing_overview_after_fallback": ("sum", "*", "missing_overview_after_fallback"),
    "country_hit_rate": ("avg", "*", "country_hit_rate"),
}


def _results_by_scenario(results: list[dict[str, Any]] | dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    if isinstance(results, dict):
        return {str(key): dict(value or {}) for key, value in results.items()}
    return {
        str(item.get("scenario") or f"scenario_{index}"): dict(item)
        for index, item in enumerate(results, start=1)
        if isinstance(item, dict)
    }


def _number_or_none(value: Any) -> float | None:
    if value in (None, "", NOT_CAPTURED, "unknown"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _metric_value(results: dict[str, dict[str, Any]], spec: tuple[str, str, str]) -> Any:
    mode, scenario, field = spec
    if mode == "scenario":
        value = results.get(scenario, {}).get(field, NOT_CAPTURED)
        return NOT_CAPTURED if value in (None, "") else value
    values = [
        _number_or_none(item.get(field))
        for item in results.values()
        if isinstance(item, dict)
    ]
    numbers = [value for value in values if value is not None]
    if not numbers:
        return NOT_CAPTURED
    if mode == "sum":
        return round(sum(numbers), 4)
    if mode == "avg":
        return round(sum(numbers) / len(numbers), 4)
    raise ValueError(f"Unsupported metric mode: {mode}")


def _delta(current: Any, baseline: Any) -> Any:
    current_number = _number_or_none(current)
    baseline_number = _number_or_none(baseline)
    if current_number is None or baseline_number is None:
        return NOT_CAPTURED
    return round(current_number - baseline_number, 4)


def build_compare_rows(
    current_results: list[dict[str, Any]] | dict[str, dict[str, Any]],
    baseline: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    current_by_scenario = _results_by_scenario(current_results)
    baseline = dict(baseline or {})
    rows: list[dict[str, Any]] = []
    for metric_key, spec in COMPARE_METRICS.items():
        current = _metric_value(current_by_scenario, spec)
        before = baseline.get(metric_key, NOT_CAPTURED)
        rows.append({
            "metric": metric_key,
            "baseline": before if before not in (None, "") else NOT_CAPTURED,
            "current": current,
            "delta": _delta(current, before),
        })
    return rows


def build_baseline_snapshot(
    current_results: list[dict[str, Any]] | dict[str, dict[str, Any]],
) -> dict[str, Any]:
    rows = build_compare_rows(current_results, baseline={})
    return {row["metric"]: row["current"] for row in rows}


def build_analysis_markdown(
    current_results: list[dict[str, Any]] | dict[str, dict[str, Any]],
    rows: list[dict[str, Any]],
) -> str:
    current_by_scenario = _results_by_scenario(current_results)
    lines = [
        "# Onboarding Before/After Compare",
        "",
        f"- Generated: {datetime.now(timezone.utc).isoformat()}",
        f"- Scenarios: {len(current_by_scenario)}",
        "",
        "| Metric | Baseline | Current | Delta |",
        "| --- | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(f"| `{row['metric']}` | {row['baseline']} | {row['current']} | {row['delta']} |")

    failed = [
        (name, data)
        for name, data in sorted(current_by_scenario.items())
        if data.get("ok") is False or str(data.get("status") or "").casefold() in {"failed", "error"}
    ]
    lines.extend(["", "## Conclusions", ""])
    if failed:
        lines.append(f"- Failed scenarios are present: {', '.join(name for name, _data in failed)}.")
    else:
        lines.append("- No failed scenarios reported.")
    for row in rows:
        if row["baseline"] == NOT_CAPTURED:
            lines.append(f"- `{row['metric']}` has no captured baseline yet.")
        elif row["delta"] != NOT_CAPTURED:
            lines.append(f"- `{row['metric']}` changed by {row['delta']}.")
    return "\n".join(lines)


def build_compare_report(
    current_results: list[dict[str, Any]] | dict[str, dict[str, Any]],
    baseline: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rows = build_compare_rows(current_results, baseline=baseline)
    return {
        "rows": rows,
        "analysis_markdown": build_analysis_markdown(current_results, rows),
        "baseline_snapshot": build_baseline_snapshot(current_results),
    }


def write_compare_report(report: dict[str, Any], *, root: Path = REPORT_ROOT) -> dict[str, str]:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    raw_path = root / "raw" / f"onboarding_compare_{timestamp}.json"
    analysis_path = root / "analysis" / f"onboarding_compare_{timestamp}.md"
    baseline_path = root / "baselines" / "current_onboarding_compare_baseline.json"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    analysis_path.parent.mkdir(parents=True, exist_ok=True)
    baseline_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(json.dumps(report["rows"], ensure_ascii=False, indent=2), encoding="utf-8")
    analysis_path.write_text(str(report["analysis_markdown"]), encoding="utf-8")
    baseline_path.write_text(json.dumps(report["baseline_snapshot"], ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "raw": str(raw_path),
        "analysis": str(analysis_path),
        "baseline": str(baseline_path),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("current_json", type=Path)
    parser.add_argument("--baseline-json", type=Path)
    parser.add_argument("--root", type=Path, default=REPORT_ROOT)
    args = parser.parse_args(argv)

    current = json.loads(args.current_json.read_text(encoding="utf-8"))
    baseline = None
    if args.baseline_json is not None and args.baseline_json.is_file():
        baseline = json.loads(args.baseline_json.read_text(encoding="utf-8"))
    paths = write_compare_report(build_compare_report(current, baseline=baseline), root=args.root)
    print(json.dumps(paths, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

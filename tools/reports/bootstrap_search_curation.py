"""Export and auto-label search curation JSON for FTS calibration.

Writes one JSON per query under reports/search/curation/. Labeling is
rule-based from query metadata (title/genre/overview hints) — suitable for
bootstrap baseline; refine review fields manually when needed.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tools.reports.export_search_top_results import (  # noqa: E402
    build_item,
    candidate_service_default_filters,
    rank_candidates,
)

DEFAULT_OUTPUT_DIR = ROOT_DIR / "reports" / "search" / "curation"

# ~25 diverse queries: exact title, genre, overview, alias, typo, year-ish, weak
CALIBRATION_SPECS: list[dict] = [
    {"query": "бригада", "title_any": ["бригада", "brigada"]},
    {"query": "метод", "title_any": ["метод", "method"]},
    {"query": "шерлок", "title_any": ["шерлок", "sherlock"]},
    {"query": "игра престолов", "title_any": ["игра престолов", "game of thrones"]},
    {"query": "loki", "title_any": ["loki"]},
    {"query": "halo", "title_any": ["halo"]},
    {"query": "андор", "title_any": ["andor", "андор"]},
    {"query": "криминал", "text_any": ["кримин", "crime", "criminal"]},
    {"query": "детектив", "text_any": ["детектив", "mystery", "detective"]},
    {"query": "комедия", "text_any": ["комед", "comedy"]},
    {"query": "фантастика", "text_any": ["фантаст", "sci-fi", "sci fi", "science fiction"]},
    {"query": "драма", "text_any": ["драм", "drama"]},
    {"query": "анимация", "text_any": ["анимац", "animation", "animated"]},
    {"query": "война", "text_any": ["войн", "war"]},
    {"query": "полиция", "text_any": ["полиц", "police", "swat", "s.w.a.t"]},
    {"query": "москва", "text_any": ["москв", "moscow"]},
    {"query": "россия", "text_any": ["росси", "russia", "russian"]},
    {"query": "2020", "year": 2020},
    {"query": "2019", "year": 2019},
    {"query": "сериал про", "text_any": ["сериал", "series", "season"]},
    {"query": "one piece", "title_any": ["one piece"]},
    {"query": "911", "title_any": ["9-1-1", "911"]},
    {"query": "csi", "title_any": ["csi"]},
    {"query": "brigada", "title_any": ["бригада", "brigada"]},
    {"query": "sherlock", "title_any": ["шерлок", "sherlock"]},
    {"query": "несуществующийтайтлxyz", "title_any": ["несуществующийтайтлxyz"], "expect_empty": True},
]


def _haystack(candidate: dict) -> str:
    parts = [
        candidate.get("title"),
        candidate.get("name"),
        candidate.get("original_title"),
        candidate.get("original_name"),
        candidate.get("overview"),
    ]
    genres = candidate.get("genres_tmdb") or candidate.get("genres") or []
    if isinstance(genres, list):
        parts.extend(genres)
    localized = candidate.get("localized")
    if isinstance(localized, dict):
        for block in localized.values():
            if isinstance(block, dict):
                parts.append(block.get("overview"))
    return " ".join(str(p) for p in parts if p not in (None, "")).casefold()


def _matches_any(haystack: str, patterns: list[str]) -> bool:
    for pattern in patterns:
        if str(pattern).casefold() in haystack:
            return True
    return False


def label_items(items: list[dict], spec: dict) -> list[dict]:
    title_any = list(spec.get("title_any") or [])
    text_any = list(spec.get("text_any") or [])
    year_equals = spec.get("year")
    patterns = title_any + text_any
    labeled: list[dict] = []
    for item in items:
        row = dict(item)
        if year_equals is not None:
            try:
                row["review"] = "relevant" if int(row.get("year") or 0) == int(year_equals) else "irrelevant"
            except (TypeError, ValueError):
                row["review"] = "irrelevant"
            labeled.append(row)
            continue
        title = str(row.get("title") or "")
        original = str(row.get("original_title") or "")
        genres = " ".join(str(g) for g in (row.get("genres") or []))
        haystack = f"{title} {original} {genres}".casefold()
        matched_fields = row.get("matched_fields") or []
        if matched_fields:
            haystack = f"{haystack} {' '.join(str(f) for f in matched_fields)}"
        if patterns and _matches_any(haystack, patterns):
            row["review"] = "relevant"
        elif patterns:
            row["review"] = "irrelevant"
        else:
            row["review"] = "missing"
        labeled.append(row)
    return labeled


def slugify(query: str) -> str:
    text = re.sub(r"[^\w\u0400-\u04ff]+", "_", str(query).strip().casefold())
    return text.strip("_") or "query"


def export_one(spec: dict, *, output_dir: Path, top: int, sort_mode: str) -> Path:
    query = str(spec["query"])
    filters = dict(candidate_service_default_filters())
    ranked, _overview = rank_candidates(query, filters, sort_mode)
    top_items = ranked[:top]
    items = [build_item(candidate, rank) for rank, candidate in enumerate(top_items, start=1)]
    items = label_items(items, spec)

    from candidates.onboarding.request_log import current_git_commit
    from datetime import datetime, timezone

    payload = {
        "query": query,
        "filters": filters,
        "sort_mode": sort_mode,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "git_commit": current_git_commit(),
        "count": len(items),
        "calibration_spec": {k: v for k, v in spec.items() if k != "query"},
        "items": items,
    }
    output_path = output_dir / f"search_{slugify(query)}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    return output_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bootstrap FTS calibration JSON exports.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--top", type=int, default=20)
    parser.add_argument("--sort-mode", default="relevance")
    args = parser.parse_args(argv)

    output_dir = Path(args.output_dir)
    paths: list[str] = []
    for spec in CALIBRATION_SPECS:
        path = export_one(
            spec,
            output_dir=output_dir,
            top=max(1, args.top),
            sort_mode=args.sort_mode,
        )
        paths.append(str(path))
    print(json.dumps({"exported": len(paths), "output_dir": str(output_dir), "files": paths}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

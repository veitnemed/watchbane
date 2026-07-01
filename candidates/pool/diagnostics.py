"""Read-only duplicate and poster diagnostics for saved candidate pool."""

from __future__ import annotations

from difflib import SequenceMatcher

from candidates.models.keys import normalize_key_part
from candidates.pool.dataset_overlap import build_dataset_entries_by_title_key
from candidates.pool.dedupe import (
    candidate_title,
    compact_title_key,
    normalized_title_key,
)
from candidates.pool.queries import get_all_candidates
from candidates.schema import coerce_candidate_number, normalize_candidate_record, resolve_canonical_year
from candidates.scoring.sort_keys import candidate_sort_score


def find_cross_year_title_groups(candidates: list | None = None) -> list[dict]:
    """Группирует кандидатов с одним normalized title, но разными canonical year."""
    if candidates is None:
        source_candidates = get_all_candidates()
    else:
        source_candidates = [
            normalize_candidate_record(candidate)
            for candidate in candidates
            if isinstance(candidate, dict)
        ]

    groups_by_title: dict[str, list[dict]] = {}
    for candidate in source_candidates:
        title_key = normalize_key_part(candidate_title(candidate))
        if title_key == "":
            continue
        groups_by_title.setdefault(title_key, []).append(candidate)

    groups: list[dict] = []
    for title_key, entries in groups_by_title.items():
        if len(entries) < 2:
            continue
        years = [resolve_canonical_year(entry) for entry in entries]
        if len(set(years)) <= 1:
            continue
        best_entry = max(entries, key=candidate_sort_score)
        display_title = candidate_title(best_entry) or title_key
        groups.append({
            "title": display_title,
            "title_key": title_key,
            "years": sorted({year for year in years if year is not None}),
            "entries": entries,
            "best_entry": best_entry,
        })

    groups.sort(key=lambda item: (item["title"].casefold(), item["years"]))
    return groups


def find_title_duplicate_groups(
    candidates: list | None = None,
    *,
    include_dataset: bool = True,
    dataset_by_title_key: dict[str, list[dict]] | None = None,
) -> list[dict]:
    """Группирует pool-кандидатов и совпадения из датасета по normalized title."""
    if candidates is None:
        source_candidates = get_all_candidates()
    else:
        source_candidates = [
            normalize_candidate_record(candidate)
            for candidate in candidates
            if isinstance(candidate, dict)
        ]

    pool_by_title: dict[str, list[dict]] = {}
    for candidate in source_candidates:
        title_key = normalize_key_part(candidate_title(candidate))
        if title_key == "":
            continue
        pool_by_title.setdefault(title_key, []).append(candidate)

    dataset_index = dataset_by_title_key
    if include_dataset and dataset_index is None:
        dataset_index = build_dataset_entries_by_title_key()
    if dataset_index is None:
        dataset_index = {}

    title_keys: set[str] = set()
    for title_key, entries in pool_by_title.items():
        if len(entries) >= 2:
            title_keys.add(title_key)
    if include_dataset:
        for title_key in pool_by_title:
            if pool_by_title[title_key] and dataset_index.get(title_key):
                title_keys.add(title_key)

    groups: list[dict] = []
    for title_key in title_keys:
        entries = pool_by_title.get(title_key) or []
        dataset_entries = list(dataset_index.get(title_key) or [])
        years = [resolve_canonical_year(entry) for entry in entries]
        for dataset_entry in dataset_entries:
            year = dataset_entry.get("year")
            coerced_year = coerce_candidate_number(year)
            if isinstance(coerced_year, int):
                years.append(coerced_year)
        best_entry = max(entries, key=candidate_sort_score) if entries else None
        display_title = (
            candidate_title(best_entry)
            if best_entry is not None
            else (dataset_entries[0].get("title") if dataset_entries else title_key)
        )
        entry_count = len(entries)
        groups.append({
            "title": display_title or title_key,
            "title_key": title_key,
            "entry_count": entry_count,
            "extra_entries": max(0, entry_count - 1),
            "dataset_count": len(dataset_entries),
            "in_dataset": len(dataset_entries) > 0,
            "years": sorted({year for year in years if isinstance(year, int)}),
            "entries": entries,
            "dataset_entries": dataset_entries,
            "best_entry": best_entry,
        })

    groups.sort(
        key=lambda item: (
            0 if item["entry_count"] >= 2 else 1,
            -item["entry_count"],
            -item["dataset_count"],
            item["title"].casefold(),
        )
    )
    return groups


def build_title_duplicate_summary(groups: list[dict]) -> dict:
    """Сводка по группам дублей с одним normalized title."""
    pool_duplicate_groups = [group for group in groups if int(group.get("entry_count") or 0) >= 2]
    extra_entries = sum(int(group.get("extra_entries") or 0) for group in pool_duplicate_groups)
    dataset_overlap_count = sum(1 for group in groups if group.get("in_dataset"))
    return {
        "group_count": len(pool_duplicate_groups),
        "extra_entries": extra_entries,
        "reported_groups": len(groups),
        "dataset_overlap_count": dataset_overlap_count,
    }


def find_suspicious_duplicates() -> list:
    """Ищет подозрительно похожие пары кандидатов в общем пуле."""
    candidates = get_all_candidates()
    suspicious_pairs = []

    for left_index in range(len(candidates)):
        left = candidates[left_index]
        left_title = candidate_title(left)
        left_year = left.get("year") or ""
        if left_title == "":
            continue

        for right_index in range(left_index + 1, len(candidates)):
            right = candidates[right_index]
            right_title = candidate_title(right)
            right_year = right.get("year") or ""
            if right_title == "":
                continue
            if left_year != right_year:
                continue

            left_normalized = normalized_title_key(left_title)
            right_normalized = normalized_title_key(right_title)
            if left_normalized == right_normalized:
                continue

            ratio = SequenceMatcher(
                None,
                compact_title_key(left_title),
                compact_title_key(right_title),
            ).ratio()

            if ratio < 0.80:
                continue

            suspicious_pairs.append({
                "left": left,
                "right": right,
                "ratio": ratio,
            })

    suspicious_pairs.sort(key=lambda item: item["ratio"], reverse=True)
    return suspicious_pairs


def classify_candidate_poster_state(candidate: dict) -> dict:
    """Classify one pool candidate poster state for read-only diagnostics."""
    from pathlib import Path

    from dataset.title_resolve import build_poster_hints_from_candidate
    from posters.download_images import local_preview_poster_path_if_cached

    hints = build_poster_hints_from_candidate(candidate)
    status = hints.get("status") or "missing"
    poster_url = hints.get("poster_url")
    poster_path = hints.get("poster_path")
    source = hints.get("source")

    local_path = None
    for key in ("poster_path", "poster_src"):
        value = candidate.get(key)
        if value in (None, ""):
            continue
        text = str(value).strip()
        if text.startswith(("http://", "https://")):
            continue
        path = Path(text)
        if path.is_file():
            local_path = str(path)
            break

    if local_path is None and poster_url not in (None, ""):
        cached = local_preview_poster_path_if_cached(str(poster_url))
        if cached not in (None, ""):
            local_path = cached

    if local_path not in (None, ""):
        display_state = "displayable"
    elif status == "missing":
        display_state = "missing"
    else:
        display_state = "metadata_only"

    return {
        "display_state": display_state,
        "status": status,
        "source": source,
        "poster_url": poster_url,
        "poster_path": poster_path,
        "local_path": local_path,
    }


def build_candidate_poster_diagnostics(candidates: list) -> dict:
    """Summarize poster coverage for saved pool candidates without network/JSON writes."""
    rows = []
    counts = {
        "displayable": 0,
        "metadata_only": 0,
        "missing": 0,
    }
    source_counts: dict[str, int] = {}

    for candidate in candidates:
        state = classify_candidate_poster_state(candidate)
        counts[state["display_state"]] += 1
        source_key = str(state.get("source") or "—")
        source_counts[source_key] = source_counts.get(source_key, 0) + 1
        rows.append({
            "candidate": candidate,
            **state,
        })

    problem_rows = [row for row in rows if row["display_state"] != "displayable"]

    return {
        "total": len(candidates),
        "counts": counts,
        "source_counts": source_counts,
        "rows": rows,
        "problem_rows": problem_rows,
        "is_empty": len(candidates) == 0,
    }


def collect_unique_pool_poster_urls(candidates: list) -> list[str]:
    """Collect unique HTTP poster URLs from saved pool candidates."""
    from dataset.title_resolve import build_poster_hints_from_candidate

    urls: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        hints = build_poster_hints_from_candidate(candidate)
        poster_url = hints.get("poster_url")
        if poster_url in (None, ""):
            continue
        text = str(poster_url).strip()
        if text.startswith(("http://", "https://")) is False:
            continue
        if text in seen:
            continue
        seen.add(text)
        urls.append(text)
    return urls

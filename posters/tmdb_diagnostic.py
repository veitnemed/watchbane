"""Read-only TMDb diagnostics for unresolved watched metadata lookups."""

from __future__ import annotations

from urllib.error import HTTPError, URLError

from apis import tmdb_api
from candidates.models.keys import title_identity_key
from dataset.resolve.identity import extract_api_identity_titles, title_identity_match
from posters.cache import load_poster_cache
from posters.fetch_watched_tmdb import (
    _fetch_override_details,
    _needs_tmdb_fetch,
    _search_result_year,
    _years_compatible,
    match_tmdb_search_result,
)
from posters.tmdb_overrides import get_watched_tmdb_override, load_watched_tmdb_overrides
from storage import data as storage_data

TOP_CANDIDATES = 5
OVERVIEW_PREVIEW_LEN = 120


def build_diagnostic_query_variants(title: str) -> list[str]:
    """Build read-only search query variants for diagnostic output."""
    variants: list[str] = []

    def add(value: str) -> None:
        text = str(value or "").strip()
        if text != "" and text not in variants:
            variants.append(text)

    add(title)

    no_quotes = (
        str(title)
        .replace("«", " ")
        .replace("»", " ")
        .replace('"', " ")
        .replace("'", " ")
    )
    while "  " in no_quotes:
        no_quotes = no_quotes.replace("  ", " ")
    add(no_quotes.strip())

    no_dots = no_quotes.strip().strip(".")
    while ".." in no_dots:
        no_dots = no_dots.replace("..", ".")
    add(no_dots.strip())

    if "." in no_dots:
        add(no_dots.split(".", 1)[0].strip())

    collapsed = " ".join(no_dots.split())
    add(collapsed)

    return variants


def _short_overview(value) -> str:
    text = str(value or "").strip().replace("\n", " ")
    if len(text) <= OVERVIEW_PREVIEW_LEN:
        return text
    return text[: OVERVIEW_PREVIEW_LEN - 3].rstrip() + "..."


def _candidate_titles(result: dict) -> tuple[str | None, str | None]:
    name = result.get("name") or result.get("title")
    original = result.get("original_name") or result.get("original_title")
    return (
        str(name).strip() if name not in (None, "") else None,
        str(original).strip() if original not in (None, "") else None,
    )


def _candidate_air_date(result: dict) -> str | None:
    value = result.get("first_air_date") or result.get("release_date")
    if value in (None, ""):
        return None
    return str(value).strip()


def _title_matches_dataset(title: str, result: dict) -> bool:
    result_titles = extract_api_identity_titles(result)
    return any(title_identity_match(title, candidate_title) for candidate_title in result_titles)


def explain_candidate_rejection(
    title: str,
    year,
    result: dict,
    *,
    matched: list[dict] | None = None,
    match_status: str | None = None,
) -> str:
    """Explain why one TMDb candidate was not auto-selected."""
    if isinstance(result, dict) is False:
        return "other"

    title_ok = _title_matches_dataset(title, result)
    result_year = _search_result_year(result)
    year_ok = _years_compatible(year, result_year)

    if title_ok is False:
        return "title_mismatch"

    if year_ok is False:
        return "year_mismatch"

    matched = matched or []
    if len(matched) > 1 and any(item.get("id") == result.get("id") for item in matched):
        if match_status == "uncertain_match":
            return "multiple_candidates"
        if year not in (None, ""):
            exact_year_matches = [item for item in matched if _search_result_year(item) == int(year)]
            if len(exact_year_matches) != 1:
                return "multiple_candidates"

    if len(matched) == 1 and matched[0].get("id") == result.get("id"):
        return "accepted_by_policy"

    if title_ok and year_ok:
        return "no_safe_match"

    return "other"


def build_candidate_diagnostic(title: str, year, result: dict, *, matched, match_status: str) -> dict:
    """Build one candidate diagnostic row."""
    name, original_name = _candidate_titles(result)
    poster_path = result.get("poster_path")
    return {
        "tmdb_id": result.get("id"),
        "name": name,
        "original_name": original_name,
        "first_air_date": _candidate_air_date(result),
        "calculated_year": _search_result_year(result),
        "has_poster_path": poster_path not in (None, ""),
        "overview": _short_overview(result.get("overview")),
        "rejection_reason": explain_candidate_rejection(
            title,
            year,
            result,
            matched=matched,
            match_status=match_status,
        ),
        "media_type": "tv",
    }


def _collect_matched_candidates(title: str, year, results: list[dict]) -> list[dict]:
    matched: list[dict] = []
    for result in results:
        if isinstance(result, dict) is False:
            continue
        if _title_matches_dataset(title, result) is False:
            continue
        if _years_compatible(year, _search_result_year(result)) is False:
            continue
        matched.append(result)
    return matched


def infer_unresolved_reason(
    title: str,
    year,
    *,
    meta_obj: dict | None,
    override: dict | None,
    search_func,
    details_func,
) -> str:
    """Infer step-7 style reason without writing data."""
    if override is not None:
        try:
            raw_details = _fetch_override_details(override, details_func)
        except (HTTPError, URLError, OSError, RuntimeError, KeyError, TypeError, ValueError):
            return "manual_override_failed"
        if isinstance(raw_details, dict) is False:
            return "manual_override_failed"
        return "manual_override_pending"

    try:
        results = search_func(title)
    except (HTTPError, URLError, OSError, RuntimeError):
        return "network_error"

    _, match_status = match_tmdb_search_result(title, year, results)
    return match_status if match_status in {"not_found", "uncertain_match"} else "not_found"


def diagnose_search_queries(
    title: str,
    year,
    *,
    search_func,
) -> tuple[str, list[dict], str, list[dict]]:
    """Run primary and variant TV searches read-only."""
    primary_query = title
    try:
        primary_results = search_func(primary_query)
    except (HTTPError, URLError, OSError, RuntimeError):
        primary_results = []

    _, match_status = match_tmdb_search_result(title, year, primary_results)
    matched = _collect_matched_candidates(title, year, primary_results)

    query_variants: list[dict] = []
    for query in build_diagnostic_query_variants(title):
        if query == primary_query:
            query_variants.append(
                {
                    "query": query,
                    "result_count": len(primary_results),
                    "matched_count": len(matched),
                    "is_primary": True,
                }
            )
            continue
        try:
            variant_results = search_func(query)
        except (HTTPError, URLError, OSError, RuntimeError):
            variant_results = []
        variant_matched = _collect_matched_candidates(title, year, variant_results)
        query_variants.append(
            {
                "query": query,
                "result_count": len(variant_results),
                "matched_count": len(variant_matched),
                "is_primary": False,
            }
        )

    return primary_query, primary_results, match_status, query_variants


def build_override_snippet(title: str, year, tmdb_id, media_type: str = "tv") -> str:
    """Build manual override JSON snippet for copy/paste."""
    identity = title_identity_key({"title": title, "year": year})
    return (
        f'"{identity}": {{\n'
        f'  "tmdb_id": {int(tmdb_id)},\n'
        f'  "media_type": "{media_type}",\n'
        f'  "note": "manual confirmed"\n'
        f"}}"
    )


def diagnose_watched_tmdb_unresolved(
    *,
    search_func=None,
    details_func=None,
    progress_callback=None,
) -> dict:
    """Collect read-only diagnostics for watched records still missing TMDb metadata."""
    search_func = search_func or tmdb_api.search_tv_by_name
    details_func = details_func or tmdb_api.get_tv_details

    data = storage_data.load_dataset()
    meta = storage_data.load_meta()
    poster_cache = load_poster_cache()
    overrides = load_watched_tmdb_overrides()

    entries: list[dict] = []
    total = len(data)
    processed = 0

    for dataset_key, movie in data.items():
        processed += 1
        main_info = movie.get("main_info") or {}
        title = str(main_info.get("title") or movie.get("title") or dataset_key).strip()
        year = main_info.get("year", movie.get("year"))

        _, meta_obj = _find_meta_entry(meta, title)
        if _needs_tmdb_fetch(meta_obj, title, year) is False:
            if progress_callback is not None:
                progress_callback(processed, total, title)
            continue

        override = get_watched_tmdb_override(title, year, overrides=overrides)
        reason = infer_unresolved_reason(
            title,
            year,
            meta_obj=meta_obj,
            override=override,
            search_func=search_func,
            details_func=details_func,
        )

        primary_query, primary_results, match_status, query_variants = diagnose_search_queries(
            title,
            year,
            search_func=search_func,
        )
        matched = _collect_matched_candidates(title, year, primary_results)

        candidates: list[dict] = []
        for result in primary_results[:TOP_CANDIDATES]:
            if isinstance(result, dict) is False:
                continue
            candidate = build_candidate_diagnostic(
                title,
                year,
                result,
                matched=matched,
                match_status=match_status,
            )
            if candidate.get("tmdb_id") not in (None, ""):
                candidate["override_snippet"] = build_override_snippet(
                    title,
                    year,
                    candidate["tmdb_id"],
                    media_type="tv",
                )
            candidates.append(candidate)

        if reason == "manual_override_pending":
            reason = "manual_override_failed"

        entries.append(
            {
                "dataset_title": title,
                "dataset_year": year,
                "dataset_key": dataset_key,
                "search_query": primary_query,
                "reason": reason,
                "match_status": match_status,
                "query_variants": query_variants,
                "candidates": candidates,
                "has_override": override is not None,
                "note": "tv_search_only",
            }
        )

        if progress_callback is not None:
            progress_callback(processed, total, title)

    return {
        "total_checked": total,
        "total_unresolved": len(entries),
        "entries": entries,
    }


def _find_meta_entry(meta: dict, title: str) -> tuple[str | None, dict | None]:
    expected = title.strip().lower()
    for meta_title, meta_obj in meta.items():
        if meta_title.strip().lower() != expected:
            continue
        if isinstance(meta_obj, dict):
            return meta_title, meta_obj
    return None, None


def format_watched_tmdb_diagnostic_report(report: dict) -> str:
    """Format diagnostic report for console output."""
    lines = [
        f"Unresolved записей: {report.get('total_unresolved', 0)} / {report.get('total_checked', 0)}",
        "Поиск: TMDb TV only (movie не проверяется автоматически).",
        "",
    ]

    entries = report.get("entries") or []
    if len(entries) == 0:
        lines.append("Нерешённых записей нет.")
        return "\n".join(lines)

    for index, entry in enumerate(entries, start=1):
        title = entry.get("dataset_title") or "?"
        year = entry.get("dataset_year")
        year_label = year if year not in (None, "") else "—"
        lines.append("=" * 60)
        lines.append(f"{index}. {title} ({year_label})")
        lines.append(f"   reason: {entry.get('reason')}")
        lines.append(f"   search query: {entry.get('search_query')}")
        if entry.get("has_override"):
            lines.append("   override: configured in watched_tmdb_overrides.json")

        lines.append("   query variants:")
        for variant in entry.get("query_variants") or []:
            marker = "primary" if variant.get("is_primary") else "variant"
            lines.append(
                f"     - [{marker}] {variant.get('query')} "
                f"-> results={variant.get('result_count')}, matched={variant.get('matched_count')}"
            )

        candidates = entry.get("candidates") or []
        if len(candidates) == 0:
            lines.append("   top candidates: нет")
        else:
            lines.append("   top candidates:")
            for candidate in candidates:
                lines.append(
                    f"     - id={candidate.get('tmdb_id')} | "
                    f"{candidate.get('name') or '?'} / {candidate.get('original_name') or '—'} | "
                    f"date={candidate.get('first_air_date') or '—'} | "
                    f"year={candidate.get('calculated_year') if candidate.get('calculated_year') is not None else '—'} | "
                    f"poster={'yes' if candidate.get('has_poster_path') else 'no'}"
                )
                if candidate.get("overview"):
                    lines.append(f"       overview: {candidate.get('overview')}")
                lines.append(f"       reject: {candidate.get('rejection_reason')}")
                if candidate.get("override_snippet"):
                    lines.append("       override snippet:")
                    for snippet_line in str(candidate.get("override_snippet")).splitlines():
                        lines.append(f"         {snippet_line}")

        lines.append("")

    return "\n".join(lines).rstrip()

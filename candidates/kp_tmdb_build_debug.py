"""TEMPORARY: KP API attempt diagnostics for TMDb build. Safe to delete after KP tuning."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from urllib.request import urlopen

from apis import kp_api
from candidates import kp_enrichment

MATCH_THRESHOLD = 0.78
YEAR_TOLERANCE = 1


def new_attempt_record(
    candidate: dict[str, Any],
    query: str,
    country: str,
    year: int | None,
) -> dict[str, Any]:
    """Returns empty trace record for one KP lookup attempt."""
    return {
        "candidate_title": candidate.get("title"),
        "candidate_original_title": candidate.get("original_title"),
        "candidate_alternative_title": candidate.get("alternative_title"),
        "candidate_year": kp_enrichment.candidate_year(candidate),
        "kp_country": country,
        "kp_query": str(query),
        "kp_year_filter": year,
        "kp_results_total": 0,
        "kp_series_count": 0,
        "kp_first_title": None,
        "kp_first_year": None,
        "kp_selected_title": None,
        "kp_selected_year": None,
        "choose_reason": None,
        "api_ok": None,
        "api_error": None,
        "lookup_status": None,
        "reject_reason": None,
        "match_is_safe": None,
        "title_similarity": None,
        "title_similarity_required": MATCH_THRESHOLD,
        "matched_candidate_title": None,
        "matched_kp_title": None,
        "matched_kp_year": None,
        "year_delta": None,
        "year_tolerance": YEAR_TOLERANCE,
        "rejection_summary": None,
        "kp_raw_type_samples": [],
        "expected_country": country,
        "kp_candidate_countries": [],
    }


def make_tracing_find_series_raw(
    attempt: dict[str, Any],
    *,
    token: str | None = None,
    opener=urlopen,
) -> Callable[..., dict[str, Any]]:
    """Same flow as kp_api.find_series_raw, but fills attempt metadata (no logic changes)."""

    def tracing_find_series_raw(
        title,
        country,
        year=None,
        token: str = kp_api.TOKEN,
        opener=urlopen,
    ) -> dict[str, Any]:
        if token is None:
            token = kp_api.TOKEN

        validation = kp_api.validate_series_request(title, country)
        if validation["ok"] is False:
            attempt["api_ok"] = False
            attempt["api_error"] = validation.get("error")
            attempt["rejection_summary"] = _format_api_error_summary(attempt)
            return validation

        title = validation["data"]["title"]
        country = validation["data"]["country"]
        attempt["kp_query"] = title
        attempt["kp_country"] = country

        url = kp_api.build_search_url(title)
        response = kp_api.fetch_json(url, token=token, opener=opener)
        if response["ok"] is False:
            attempt["api_ok"] = False
            attempt["api_error"] = response.get("error")
            attempt["rejection_summary"] = _format_api_error_summary(attempt)
            return response

        docs = kp_api.get_docs(response["data"])
        attempt["kp_raw_type_samples"] = [
            kp_api.describe_kp_type_filter(doc)
            for doc in docs[:5]
            if isinstance(doc, dict)
        ]
        series_docs = [
            movie for movie in docs
            if isinstance(movie, dict) and kp_api.is_series(movie)
        ]
        attempt["kp_results_total"] = len(docs)
        attempt["kp_series_count"] = len(series_docs)

        if len(series_docs) > 0:
            first = series_docs[0]
            attempt["kp_first_title"] = first.get("name")
            attempt["kp_first_year"] = first.get("year")

        if len(series_docs) == 0:
            attempt["api_ok"] = False
            attempt["api_error"] = "not_found"
            attempt["rejection_summary"] = _format_api_error_summary(attempt)
            if attempt["kp_raw_type_samples"]:
                rejected_types = ", ".join(
                    f"{sample.get('type') or '-'}({sample.get('type_filter_reason')})"
                    for sample in attempt["kp_raw_type_samples"][:3]
                )
                attempt["rejection_summary"] += f". Type samples: {rejected_types}"
            return kp_api.make_response(False, error="not_found", details="series_not_found")

        selected, reason = kp_api.choose_best_series(
            series_docs,
            country=country,
            title=title,
            year=year,
        )
        attempt["choose_reason"] = reason
        attempt["expected_country"] = country
        if selected is not None:
            attempt["kp_candidate_countries"] = kp_enrichment.extract_kp_country_values(selected)
        elif reason == "country_not_found":
            attempt["kp_candidate_countries"] = kp_enrichment.unique_non_empty([
                country_label
                for doc in series_docs
                for country_label in kp_enrichment.extract_kp_country_values(doc)
            ])

        if selected is None:
            attempt["api_ok"] = False
            attempt["api_error"] = reason
            attempt["rejection_summary"] = _format_api_error_summary(attempt)
            return kp_api.make_response(False, error=reason, details=f"series_{reason}")

        attempt["api_ok"] = True
        attempt["kp_selected_title"] = selected.get("name")
        attempt["kp_selected_year"] = selected.get("year")
        return kp_api.make_response(True, data=selected)

    return tracing_find_series_raw


def fill_match_trace(
    attempt: dict[str, Any],
    candidate: dict[str, Any],
    movie: dict[str, Any],
    is_safe: bool,
    reason: str | None,
    *,
    lookup_status: str,
) -> None:
    """Adds match-check diagnostics without changing match-check itself."""
    attempt["lookup_status"] = lookup_status
    attempt["match_is_safe"] = is_safe
    attempt["reject_reason"] = reason
    attempt["matched_kp_title"] = movie.get("name")
    attempt["matched_kp_year"] = movie.get("year")
    attempt["expected_country"] = attempt.get("expected_country") or attempt.get("kp_country")
    attempt["kp_candidate_countries"] = kp_enrichment.extract_kp_country_values(movie)

    candidate_titles = kp_enrichment.unique_non_empty([
        candidate.get("title"),
        candidate.get("original_title"),
    ])
    title_score = 0.0
    best_title = None
    for title in candidate_titles:
        score = kp_api.title_match_score(str(title), movie)
        if score >= title_score:
            title_score = score
            best_title = str(title)
    attempt["title_similarity"] = round(title_score, 4)
    attempt["matched_candidate_title"] = best_title

    expected_year = kp_enrichment.candidate_year(candidate)
    kp_year = kp_enrichment.safe_int(movie.get("year"))
    if expected_year is not None and kp_year is not None:
        attempt["year_delta"] = abs(kp_year - expected_year)

    attempt["rejection_summary"] = _format_rejection_summary(attempt, is_safe, reason)


def _format_api_error_summary(attempt: dict[str, Any]) -> str:
    error = attempt.get("api_error") or "unknown"
    return (
        f'Искали: "{attempt.get("kp_query")}", country="{attempt.get("kp_country")}", '
        f'year={attempt.get("kp_year_filter")!r}. '
        f"KP вернул series={attempt.get('kp_series_count')}/{attempt.get('kp_results_total')}. "
        f"API error: {error}"
        + (f", choose_reason={attempt.get('choose_reason')}" if attempt.get("choose_reason") else "")
    )


def _format_rejection_summary(
    attempt: dict[str, Any],
    is_safe: bool,
    reason: str | None,
) -> str:
    if is_safe:
        return (
            f'Искали: "{attempt.get("kp_query")}", country="{attempt.get("kp_country")}", '
            f'year={attempt.get("kp_year_filter")!r}. '
            f'KP selected: "{attempt.get("kp_selected_title")}", year={attempt.get("kp_selected_year")!r}. '
            f"Match OK (similarity={attempt.get('title_similarity')})."
        )

    if reason == "title_mismatch":
        return (
            f'Искали: "{attempt.get("kp_query")}", country="{attempt.get("kp_country")}", '
            f'year={attempt.get("kp_year_filter")!r}. '
            f'KP вернул: "{attempt.get("matched_kp_title")}", year={attempt.get("matched_kp_year")!r}. '
            f"Отклонено: title_mismatch, similarity={attempt.get('title_similarity')}, "
            f"нужно >= {MATCH_THRESHOLD} (сравнивали с {attempt.get('matched_candidate_title')!r})."
        )

    if reason == "year_mismatch":
        return (
            f'Искали: "{attempt.get("kp_query")}", country="{attempt.get("kp_country")}", '
            f'year={attempt.get("kp_year_filter")!r}. '
            f'KP вернул: "{attempt.get("matched_kp_title")}", year={attempt.get("matched_kp_year")!r}. '
            f"Отклонено: year_mismatch, delta={attempt.get('year_delta')}, "
            f"допустимо <= {YEAR_TOLERANCE}."
        )

    if reason == "not_series":
        return (
            f'Искали: "{attempt.get("kp_query")}", country="{attempt.get("kp_country")}". '
            f'KP вернул: "{attempt.get("matched_kp_title")}". '
            f"Отклонено: not_series."
        )

    return (
        f'Искали: "{attempt.get("kp_query")}", country="{attempt.get("kp_country")}". '
        f"Отклонено: {reason or 'unknown'}."
    )


class KpBuildDebugSession:
    """Collects per-candidate KP traces during one TMDb build run."""

    def __init__(self, *, country: str, criteria_name: str | None = None) -> None:
        self.country_iso2 = country
        self.criteria_name = criteria_name
        self.created_at = datetime.now().isoformat(timespec="seconds")
        self._entries: list[dict[str, Any]] = []
        self._current: dict[str, Any] | None = None

    @property
    def current_attempts(self) -> list[dict[str, Any]] | None:
        if self._current is None:
            return None
        return self._current["attempts"]

    def start_candidate(self, candidate: dict[str, Any], kp_country: str) -> None:
        self._current = {
            "title": candidate.get("title"),
            "original_title": candidate.get("original_title"),
            "alternative_title": candidate.get("alternative_title"),
            "year": kp_enrichment.candidate_year(candidate),
            "tmdb_id": candidate.get("tmdb_id"),
            "imdb_id": candidate.get("imdb_id"),
            "kp_country": kp_country,
            "final_kp_status": None,
            "final_lookup_status": None,
            "attempts": [],
        }

    def finish_candidate(self, candidate: dict[str, Any], lookup: dict[str, Any]) -> None:
        if self._current is None:
            return
        self._current["final_kp_status"] = candidate.get("kp_status")
        self._current["final_lookup_status"] = lookup.get("status")
        self._current["final_lookup_error"] = lookup.get("error")
        self._entries.append(self._current)
        self._current = None

    def to_report(self) -> dict[str, Any]:
        return {
            "created_at": self.created_at,
            "country_iso2": self.country_iso2,
            "criteria_name": self.criteria_name,
            "candidate_count": len(self._entries),
            "entries": self._entries,
        }


def format_kp_debug_lines(report: dict[str, Any], *, limit: int = 20) -> list[str]:
    """Human-readable lines for console output."""
    lines = [
        "",
        "KP API debug (temporary diagnostics):",
        "-" * 80,
    ]
    for entry in (report.get("entries") or [])[:limit]:
        title = entry.get("title") or "?"
        year = entry.get("year") or "?"
        lines.append(f"{title} ({year}) | country={entry.get('kp_country')}")
        for index, attempt in enumerate(entry.get("attempts") or [], start=1):
            summary = attempt.get("rejection_summary") or attempt.get("api_error") or "-"
            lines.append(f"  attempt {index}: {summary}")
        lines.append("")
    return lines


def save_kp_debug_report(report: dict[str, Any], base_json_path: str | Path) -> Path:
    """Saves *_kp_debug.json next to TMDb build result."""
    base_path = Path(base_json_path)
    debug_path = base_path.with_name(f"{base_path.stem}_kp_debug.json")
    debug_path.parent.mkdir(parents=True, exist_ok=True)
    with open(debug_path, "w", encoding="utf-8") as file:
        json.dump(report, file, ensure_ascii=False, indent=2)
    return debug_path

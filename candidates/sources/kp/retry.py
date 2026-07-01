"""Retry KP enrichment for incomplete saved pool candidates."""

from __future__ import annotations

from datetime import datetime

from apis import kp_api as api
from candidates import country_schema
from candidates.pool.normalization import normalize_storage_pool
from candidates.pool.queries import get_incomplete_candidates
from candidates.schema import normalize_candidate_record
from candidates.sources.kp import enrichment as kp_enrichment


def _country_label_from_value(value) -> str:
    text = str(value or "").strip()
    if text == "":
        return ""
    iso2 = country_schema.country_value_to_iso2(text)
    if iso2 is not None:
        return country_schema.build_country_display([iso2]) or text
    return text


def _candidate_retry_country(candidate: dict) -> str:
    normalized = normalize_candidate_record(candidate)
    for code in normalized.get("country_codes") or []:
        label = _country_label_from_value(code)
        if label:
            return label

    for field_name in ("country_display", "countries", "country"):
        values = normalized.get(field_name)
        if isinstance(values, (list, tuple, set)):
            for value in values:
                label = _country_label_from_value(value)
                if label:
                    return label
            continue
        label = _country_label_from_value(values)
        if label:
            return label
    return ""


def _criteria_country(criteria_name: str | None) -> str:
    from candidates import candidate_pool as pool_compat

    if criteria_name is None:
        return "Россия"

    criteria = pool_compat.load_candidate_criteria().get(criteria_name, {})
    return _country_label_from_value(criteria.get("country")) or "Россия"


def _retry_country(candidate: dict, criteria_name: str | None) -> str:
    return _candidate_retry_country(candidate) or _criteria_country(criteria_name)


def _mark_kp_retry_attempt(candidate: dict) -> None:
    candidate["kp_attempts"] = int(candidate.get("kp_attempts") or 0) + 1
    candidate["last_kp_attempt_at"] = datetime.now().isoformat(timespec="seconds")


def _append_signal(candidate: dict, signal: str) -> None:
    signals = candidate.setdefault("signals", [])
    if signal not in signals:
        signals.append(signal)


def retry_kp_enrichment_for_pool(limit: int = 10, criteria_name: str | None = None) -> dict:
    """Повторно добирает KP-данные для неполных кандидатов в общем candidate_pool."""
    from candidates import candidate_pool as pool_compat

    pool = normalize_storage_pool(pool_compat.load_candidate_pool())
    incomplete_candidates = get_incomplete_candidates(pool, criteria_name=criteria_name)
    selected_candidates = incomplete_candidates[:max(0, int(limit))]
    stats = {
        "incomplete_found": len(incomplete_candidates),
        "attempted": 0,
        "kp_found": 0,
        "kp_not_found": 0,
        "api_errors": 0,
        "became_complete": 0,
        "remaining_incomplete": 0,
    }

    for candidate in selected_candidates:
        stats["attempted"] += 1
        _mark_kp_retry_attempt(candidate)

        country = _retry_country(candidate, candidate.get("criteria_name") or criteria_name)
        queries = kp_enrichment.candidate_kp_queries(candidate, include_alternative_title=True)
        if len(queries) == 0:
            candidate["kp_status"] = "not_found"
            candidate["last_kp_error"] = "empty_query"
            _append_signal(candidate, "kp_api_not_found_retry")
            candidate.update(normalize_candidate_record(candidate))
            stats["kp_not_found"] += 1
            continue

        lookup = kp_enrichment.lookup_kp_via_api(
            candidate,
            queries,
            country,
            find_series_raw=api.find_series_raw,
            continue_on_reject=True,
        )

        if lookup["status"] == "found":
            kp_enrichment.fill_candidate_from_kp_api(candidate, lookup["movie"] or {})
            candidate["kp_score"] = candidate.get("kp_rating")
            candidate["kp_status"] = "done"
            candidate.pop("last_kp_error", None)
            _append_signal(candidate, "kp_api_hit_retry")
            candidate.update(normalize_candidate_record(candidate))
            stats["kp_found"] += 1
            if candidate["is_complete"]:
                stats["became_complete"] += 1
            continue

        if lookup["status"] == "error":
            error_code = lookup.get("error") or "unknown"
            candidate["kp_status"] = "error"
            candidate["last_kp_error"] = error_code
            _append_signal(candidate, "kp_api_error_retry")
            candidate.update(normalize_candidate_record(candidate))
            stats["api_errors"] += 1
            continue

        last_error = lookup.get("error") or "not_found"
        reject_reason = lookup.get("reject_reason")
        if reject_reason:
            last_error = f"rejected_{reject_reason}"
            _append_signal(candidate, f"kp_api_retry_rejected_{reject_reason}")

        candidate["kp_status"] = "not_found"
        candidate["last_kp_error"] = last_error
        _append_signal(candidate, "kp_api_not_found_retry")
        candidate.update(normalize_candidate_record(candidate))
        stats["kp_not_found"] += 1

    stats["remaining_incomplete"] = len(get_incomplete_candidates(pool, criteria_name=criteria_name))
    if stats["attempted"] > 0:
        pool_compat.save_candidate_pool(pool)
    return stats

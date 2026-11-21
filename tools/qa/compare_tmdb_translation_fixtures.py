"""Offline comparison of the detached Details route and appended translations.

Byte payloads are supplied by the caller, not downloaded. 'Attempt' here is a
simulated HTTP launch. Tag evidence is provider metadata as represented in a
fixture, not independent linguistic review, catalog clearance, or live proof.
"""
from collections import Counter
from dataclasses import dataclass
from math import ceil

from apis.tmdb.detached_transport import DetachedTmdbError
from web.tmdb_hydration import _detail, _fetch
from web.tmdb_ids import QueueItem
from web.tmdb_translation_extract import MAX_BODY_BYTES, TypedFixture, _decode, select_translation


MAX_CASES = 500


@dataclass(frozen=True)
class PairedCase:
    item: QueueItem
    ru_details: bytes
    en_details: bytes
    appended_details: bytes


class _Attempts:
    def __init__(self, cap, body_cap):
        self.cap = cap
        self.body_cap = body_cap
        self.sizes = []

    def use(self, response):
        if len(self.sizes) >= self.cap:
            raise DetachedTmdbError("budget_exhausted")
        self.sizes.append(len(response))
        if len(response) > self.body_cap:
            raise DetachedTmdbError("oversized")
        return response

    def summary(self):
        sizes = sorted(self.sizes)
        return {
            "attempted_launches": len(sizes),
            "total_body_bytes": sum(sizes),
            "p95_body_bytes_nearest_rank": sizes[ceil(.95 * len(sizes)) - 1] if sizes else None,
        }


class _BaselineFixture:
    def __init__(self, case, attempts):
        self.case, self.attempts = case, attempts

    def get(self, path, params):
        item = self.case.item
        if path != f"/{item.media_type}/{item.tmdb_id}" or params not in (
            {"language": "ru-RU"}, {"language": "en-US"},
        ):
            raise AssertionError("Unplanned fixture dispatch")
        source = self.case.ru_details if params["language"] == "ru-RU" else self.case.en_details
        return _decode(TypedFixture(item, self.attempts.use(source)))


def _baseline(case, attempts):
    import json

    status, payload = _fetch(_BaselineFixture(case, attempts), case.item)
    if status != "hydrated":
        return status, None
    return "eligible_untagged", json.loads(payload)["requested_locale"]


def _candidate(case, attempts):
    fixture = TypedFixture(case.item, attempts.use(case.appended_details))
    body = _decode(fixture)

    class Appended:
        def get(self, *_):
            return body

    detail, title = _detail(Appended(), case.item, "ru-RU")
    if detail.get("adult") is not False:
        return "ineligible", None
    if len(title) > 512:
        raise ValueError("Invalid title")
    selected = select_translation(fixture)
    if selected is not None:
        return "eligible_tagged", selected.locale_tag
    return ("eligible_untagged" if str(detail.get("overview") or "").strip() else "missing_overview"), None


def compare_translation_fixtures(
    cases: tuple[PairedCase, ...], *, attempt_cap: int, body_cap: int = MAX_BODY_BYTES,
) -> dict:
    """Compare the same ordered unique typed cases under independent equal caps."""
    if type(attempt_cap) is not int or not 0 <= attempt_cap <= 2 * MAX_CASES:
        raise ValueError("Invalid fixture attempt cap")
    if type(body_cap) is not int or not 1 <= body_cap <= MAX_BODY_BYTES:
        raise ValueError("Invalid fixture body cap")
    if not 1 <= len(cases) <= MAX_CASES:
        raise ValueError("Invalid fixture case count")
    seen = set()
    for case in cases:
        if not isinstance(case, PairedCase) or not isinstance(case.item, QueueItem):
            raise ValueError("Invalid typed fixture case")
        item = case.item
        if (item.media_type not in ("movie", "tv") or type(item.tmdb_id) is not int
                or not 0 < item.tmdb_id < 2**31 or item in seen
                or any(not isinstance(body, bytes) for body in
                       (case.ru_details, case.en_details, case.appended_details))):
            raise ValueError("Invalid or duplicate typed fixture case")
        seen.add(item)

    report = {}
    for label, evaluator in (("baseline", _baseline), ("appended", _candidate)):
        attempts = _Attempts(attempt_cap, body_cap)
        statuses, locales = Counter(), Counter()
        for case in cases:
            try:
                status, locale = evaluator(case, attempts)
            except DetachedTmdbError as error:
                status, locale = (error.code if error.code in ("oversized", "budget_exhausted")
                                  else "invalid_fixture"), None
            except ValueError:
                status, locale = "invalid_fixture", None
            statuses[status] += 1
            if locale is not None:
                locales[locale] += 1
        coverage_field = "requested_locale_only" if label == "baseline" else "provider_tagged_locale"
        report[label] = {
            **attempts.summary(),
            **{key: statuses[key] for key in ("eligible_tagged", "eligible_untagged", "missing_overview",
                                              "ineligible", "oversized", "invalid_fixture", "budget_exhausted")},
            coverage_field: dict(sorted(locales.items())),
        }
    return {"cases": len(cases), "attempt_cap_per_route": attempt_cap,
            "body_cap_bytes": body_cap, "simulated_fixture_only": True, **report}

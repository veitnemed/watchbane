"""Private bounded read of reviewed current refresh rows; never activates them."""
from collections.abc import Mapping
from contextlib import closing
from dataclasses import dataclass
from datetime import date
from hashlib import sha256
import json
from pathlib import Path
import sqlite3

from web.tmdb_catalog_audit import ReviewedLanguage
from web.tmdb_change_windows import _reject_payload_constant, _unique_payload_object
from web.tmdb_ids import QueueItem


MAX_REVIEWED_REFRESH = 500
MAX_REVIEWED_ROW_BYTES = 64 * 1024
_LANGUAGES = {"ru": "ru-RU", "en": "en-US"}
_LOCALES = {"ru-RU", "en-US"}


@dataclass(frozen=True)
class ReviewedRefresh:
    version: int
    requested_locale: str
    language: ReviewedLanguage


@dataclass(frozen=True)
class RefreshSeedRow:
    item: QueueItem
    version: int
    language: str
    title: str
    overview: str
    year: int | None


def read_reviewed_refresh(
    *, checkpoint: Path, reviewed: Mapping[QueueItem, ReviewedRefresh],
) -> tuple[RefreshSeedRow, ...]:
    """Read one coherent snapshot for only the explicitly language-reviewed IDs.

    The requested locale is provider metadata, not evidence of the actual
    synopsis language. An old staged row is not eligible while another update
    for the same typed ID is pending. No file or live catalog is published.
    A consumer must re-check freshness before activation after this read.
    """
    if not isinstance(reviewed, Mapping) or not 1 <= len(reviewed) <= MAX_REVIEWED_REFRESH:
        raise ValueError("A bounded non-empty set of refresh reviews is required")
    reviews = tuple(reviewed.items())
    if len(reviews) != len(reviewed):
        raise ValueError("Invalid refresh reviews")
    for item, review in reviews:
        if (not isinstance(item, QueueItem) or item.media_type not in ("movie", "tv")
                or type(item.tmdb_id) is not int or not 0 < item.tmdb_id < 2**31
                or not isinstance(review, ReviewedRefresh) or type(review.version) is not int
                or not 0 <= review.version <= date.max.toordinal()
                or type(review.requested_locale) is not str or review.requested_locale not in _LOCALES
                or not isinstance(review.language, ReviewedLanguage)
                or type(review.language.language) is not str or review.language.language not in _LANGUAGES):
            raise ValueError("Invalid typed refresh review")
    results = []
    with closing(sqlite3.connect(Path(checkpoint).resolve().as_uri() + "?mode=ro", uri=True)) as conn:
        conn.execute("BEGIN")
        tables = {name for name, in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if tables != {"change_watermark", "change_pending", "change_completed"}:
            raise ValueError("Expected a detached staged refresh checkpoint")
        for item, review in sorted(reviews, key=lambda pair: (pair[0].media_type, pair[0].tmdb_id)):
            row = conn.execute("""
                SELECT c.version, CASE WHEN typeof(c.payload)='blob' AND length(c.payload)<=? THEN c.payload END
                FROM change_completed c
                WHERE c.media=? AND c.tmdb_id=? AND NOT EXISTS (
                    SELECT 1 FROM change_pending p WHERE p.media=c.media AND p.tmdb_id=c.tmdb_id
                )
            """, (MAX_REVIEWED_ROW_BYTES, item.media_type, item.tmdb_id)).fetchone()
            if row is None or row[0] != review.version:
                raise ValueError("Missing, pending, or superseded refresh review")
            try:
                if row[1] is None:
                    raise ValueError
                payload = json.loads(row[1].decode("utf-8"), object_pairs_hook=_unique_payload_object,
                                     parse_constant=_reject_payload_constant)
                title, overview, year = (payload.get(key) for key in ("title", "overview", "year"))
                if (payload.get("media_type") != item.media_type
                        or type(payload.get("tmdb_id")) is not int or payload["tmdb_id"] != item.tmdb_id
                        or payload.get("requested_locale") != review.requested_locale
                        or (year is not None and (type(year) is not int or not 1800 <= year <= 2200))
                        or any(type(value) is not str or not value.strip() or "\0" in value or len(value) > limit
                               for value, limit in ((title, 512), (overview, 8192)))):
                    raise ValueError
                title.encode("utf-8")
                fingerprint = sha256(overview.encode("utf-8")).hexdigest()
                if fingerprint != review.language.synopsis_sha256:
                    raise ValueError
            except (AttributeError, TypeError, ValueError, RecursionError):
                raise ValueError("Refresh payload does not match the exact review") from None
            results.append(RefreshSeedRow(item, review.version, _LANGUAGES[review.language.language],
                                          title, overview, year))
    return tuple(results)

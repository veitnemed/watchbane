"""Offline typed changed-ID ingestion; not a live transport or deletion feed."""
from collections.abc import Mapping, Sequence
from contextlib import closing
from dataclasses import dataclass
from datetime import date, timedelta
from hashlib import sha256
import json
from pathlib import Path
import sqlite3

from web.tmdb_ids import QueueItem


KINDS = ("movie", "tv")
MAX_DAYS = 14
MAX_PAGES = 500
MAX_ROWS_PER_PAGE = 1000


@dataclass(frozen=True)
class ChangeCommit:
    completed_through: date
    distinct_changed: int
    newly_queued: int
    replayed: bool


def _validated_kind(media, pages):
    if not isinstance(pages, Sequence) or isinstance(pages, (str, bytes)) or not 1 <= len(pages) <= MAX_PAGES:
        raise ValueError("A complete bounded set of pages is required for each media type")
    declared = None
    ident = set()
    for page_index, response in enumerate(pages, 1):
        if not isinstance(response, Mapping):
            raise ValueError("Invalid change response")
        page, total = response.get("page"), response.get("total_pages")
        rows = response.get("results")
        if (type(page) is not int or page != page_index or type(total) is not int
                or not 0 <= total <= MAX_PAGES or (declared is not None and declared != total)
                or len(pages) != max(1, total) or not isinstance(rows, list)
                or len(rows) > MAX_ROWS_PER_PAGE or (total == 0 and rows)):
            raise ValueError("Missing or inconsistent pagination in a change response")
        declared = total
        for row in rows:
            value = row.get("id") if isinstance(row, Mapping) else None
            if (type(value) is not int or not 0 < value < 2**31
                    or row.get("media_type", media) != media):
                raise ValueError("Invalid or cross-typed changed ID")
            ident.add(value)
    return tuple(QueueItem(media, value) for value in sorted(ident))


def _validate(start, end, pages_by_media):
    if type(start) is not date or type(end) is not date or not 0 <= (end - start).days < MAX_DAYS:
        raise ValueError("A change window must contain 1 to 14 inclusive calendar dates")
    if not isinstance(pages_by_media, Mapping) or set(pages_by_media) != set(KINDS):
        raise ValueError("Both movie and TV pages are required")
    return tuple(item for media in KINDS for item in _validated_kind(media, pages_by_media[media]))


def commit_change_window(
    *, checkpoint: Path, start: date, end: date, pages_by_media: Mapping,
) -> ChangeCommit:
    """Commit one fully supplied window and its watermark in one transaction.

    Pages for each typed response must be in ascending provider page order.
    Validates the supplied fixture, not provenance, provider snapshot stability
    or a guarantee of no missing changes. Overlapping/touching windows are allowed;
    a skipped date requires reconciliation, not a watermark jump. The pending
    queue accumulates typed IDs; missing IDs never mean deletion. This function
    deliberately has no live fetch or hydrate path.
    """
    items = _validate(start, end, pages_by_media)
    signature = sha256(json.dumps([start.isoformat(), end.isoformat(), [i.key for i in items]],
                                  separators=(",", ":")).encode("ascii")).hexdigest()
    tables_expected = {"change_watermark", "change_pending"}
    with closing(sqlite3.connect(checkpoint, timeout=0)) as conn:
        conn.execute("BEGIN IMMEDIATE")
        with conn:
            tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not tables:
                conn.execute("""CREATE TABLE change_watermark (
                    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                    completed_through TEXT NOT NULL, signature TEXT NOT NULL
                )""")
                conn.execute("""CREATE TABLE change_pending (
                    media TEXT NOT NULL CHECK (media IN ('movie', 'tv')),
                    tmdb_id INTEGER NOT NULL CHECK (tmdb_id > 0),
                    PRIMARY KEY (media, tmdb_id)
                )""")
            elif tables != tables_expected:
                raise ValueError("Use a dedicated change-window checkpoint")
            previous = conn.execute("SELECT completed_through, signature FROM change_watermark").fetchone()
            if previous:
                watermark = date.fromisoformat(previous[0])
                if end == watermark and signature == previous[1]:
                    return ChangeCommit(end, len(items), 0, True)
                if end <= watermark or (start - watermark) > timedelta(days=1):
                    raise ValueError("Change window must advance the watermark without a calendar gap")
            before = conn.total_changes
            conn.executemany("INSERT OR IGNORE INTO change_pending VALUES (?, ?)",
                             ((item.media_type, item.tmdb_id) for item in items))
            queued = conn.total_changes - before
            conn.execute("""
                INSERT INTO change_watermark VALUES (1, ?, ?)
                ON CONFLICT(singleton) DO UPDATE SET
                    completed_through=excluded.completed_through, signature=excluded.signature
            """, (end.isoformat(), signature))
    return ChangeCommit(end, len(items), queued, False)

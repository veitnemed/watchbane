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
MAX_COMPLETION_BYTES = 2 * 1024 * 1024
_LEGACY_TABLES = {"change_watermark", "change_pending"}
_TABLES = _LEGACY_TABLES | {"change_completed"}


@dataclass(frozen=True)
class ChangeCommit:
    completed_through: date
    distinct_changed: int
    newly_queued: int
    replayed: bool


@dataclass(frozen=True)
class PendingChange:
    """Ticket for one typed item, valid only within its source checkpoint."""

    item: QueueItem
    version: int


def _table_names(conn):
    return {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def _ensure_schema(conn, tables):
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
    elif tables not in (_LEGACY_TABLES, _TABLES):
        raise ValueError("Use a dedicated change-window checkpoint")
    if tables == _LEGACY_TABLES:
        pending_columns = tuple(r[1] for r in conn.execute("PRAGMA table_info(change_pending)"))
        watermark_columns = tuple(r[1] for r in conn.execute("PRAGMA table_info(change_watermark)"))
        if pending_columns != ("media", "tmdb_id") or watermark_columns != (
            "singleton", "completed_through", "signature"
        ):
            raise ValueError("Unrecognized legacy change-window checkpoint schema")
    if tables != _TABLES:
        # Legacy pending requests have an unknown window; version zero is a
        # stable reserved baseline before any newly observed date.
        conn.execute("ALTER TABLE change_pending ADD COLUMN version INTEGER NOT NULL DEFAULT 0 CHECK(version >= 0)")
        conn.execute("""CREATE TABLE change_completed (
            media TEXT NOT NULL CHECK (media IN ('movie', 'tv')),
            tmdb_id INTEGER NOT NULL CHECK (tmdb_id > 0),
            version INTEGER NOT NULL CHECK (version >= 0),
            payload BLOB NOT NULL,
            PRIMARY KEY (media, tmdb_id)
        )""")


def _item_key(item):
    if (not isinstance(item, QueueItem) or item.media_type not in KINDS
            or type(item.tmdb_id) is not int or not 0 < item.tmdb_id < 2**31):
        raise ValueError("Invalid typed change ID")
    return item.media_type, item.tmdb_id


def pending_change(checkpoint: Path, item: QueueItem) -> PendingChange | None:
    """Read an exact current ticket without claiming it or holding a writer lock."""
    key = _item_key(item)
    with closing(sqlite3.connect(Path(checkpoint).resolve().as_uri() + "?mode=ro", uri=True)) as conn:
        conn.execute("BEGIN")
        tables = _table_names(conn)
        if tables not in (_LEGACY_TABLES, _TABLES):
            raise ValueError("Use a dedicated change-window checkpoint")
        version_column = "version" if tables == _TABLES else "0"
        row = conn.execute(
            f"SELECT {version_column} FROM change_pending WHERE media=? AND tmdb_id=?", key
        ).fetchone()
    return PendingChange(item, row[0]) if row is not None else None


def _unique_payload_object(pairs):
    result = dict(pairs)
    if len(result) != len(pairs):
        raise ValueError
    return result


def _reject_payload_constant(_value):
    raise ValueError


def stage_and_ack_change(checkpoint: Path, ticket: PendingChange, *, staged_payload: bytes) -> bool:
    """Publish only a still-current result and acknowledge it in one transaction.

    Payload must already be a private typed hydrated result from the caller.
    This checks its shape and ticket identity, not provider provenance or rights,
    and does not update any
    active search catalog. A stale/duplicate completion returns False.
    """
    if (not isinstance(ticket, PendingChange) or type(ticket.version) is not int
            or not 0 <= ticket.version <= date.max.toordinal()
            or not isinstance(staged_payload, bytes) or not 0 < len(staged_payload) <= MAX_COMPLETION_BYTES):
        raise ValueError("Invalid detached change completion")
    key = _item_key(ticket.item)
    try:
        payload = json.loads(staged_payload.decode("utf-8"), object_pairs_hook=_unique_payload_object,
                             parse_constant=_reject_payload_constant)
        if (not isinstance(payload, dict) or payload.get("media_type") != key[0]
                or type(payload.get("tmdb_id")) is not int or payload["tmdb_id"] != key[1]
                or payload.get("requested_locale") not in ("ru-RU", "en-US")):
            raise ValueError
        for field, limit in (("title", 512), ("overview", 8192)):
            value = payload.get(field)
            if not isinstance(value, str) or not value.strip() or len(value) > limit or "\0" in value:
                raise ValueError
            value.encode("utf-8")
    except (ValueError, RecursionError):
        raise ValueError("Invalid typed hydrated change completion") from None
    target = Path(checkpoint).resolve().as_uri() + "?mode=rw"
    with closing(sqlite3.connect(target, timeout=0, uri=True)) as conn:
        conn.execute("BEGIN IMMEDIATE")
        with conn:
            tables = _table_names(conn)
            if tables not in (_LEGACY_TABLES, _TABLES):
                raise ValueError("Use a dedicated change-window checkpoint")
            _ensure_schema(conn, tables)
            consumed = conn.execute(
                "DELETE FROM change_pending WHERE media=? AND tmdb_id=? AND version=?", (*key, ticket.version)
            )
            if consumed.rowcount != 1:
                return False
            conn.execute("""
                INSERT INTO change_completed VALUES (?, ?, ?, ?)
                ON CONFLICT(media, tmdb_id) DO UPDATE SET version=excluded.version, payload=excluded.payload
            """, (*key, ticket.version, staged_payload))
    return True


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
    with closing(sqlite3.connect(checkpoint, timeout=0)) as conn:
        conn.execute("BEGIN IMMEDIATE")
        with conn:
            tables = _table_names(conn)
            if tables and tables not in (_LEGACY_TABLES, _TABLES):
                raise ValueError("Use a dedicated change-window checkpoint")
            previous = conn.execute(
                "SELECT completed_through, signature FROM change_watermark"
            ).fetchone() if tables else None
            if previous:
                watermark = date.fromisoformat(previous[0])
                if end == watermark and signature == previous[1]:
                    return ChangeCommit(end, len(items), 0, True)
                if end <= watermark or (start - watermark) > timedelta(days=1):
                    raise ValueError("Change window must advance the watermark without a calendar gap")
            _ensure_schema(conn, tables)
            before = conn.total_changes
            conn.executemany("INSERT OR IGNORE INTO change_pending(media, tmdb_id, version) VALUES (?, ?, ?)",
                             ((item.media_type, item.tmdb_id, end.toordinal()) for item in items))
            queued = conn.total_changes - before
            # The watermark advances strictly, so its ordinal is a monotonic,
            # non-reusable generation even after a prior item was completed.
            conn.executemany("UPDATE change_pending SET version=? WHERE media=? AND tmdb_id=? AND version<>?",
                             ((end.toordinal(), item.media_type, item.tmdb_id, end.toordinal()) for item in items))
            conn.execute("""
                INSERT INTO change_watermark VALUES (1, ?, ?)
                ON CONFLICT(singleton) DO UPDATE SET
                    completed_through=excluded.completed_through, signature=excluded.signature
            """, (end.isoformat(), signature))
    return ChangeCommit(end, len(items), queued, False)

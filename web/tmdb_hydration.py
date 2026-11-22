"""Detached typed Detail checkpoint; not wired to the web app or profile DB."""
from contextlib import closing
from dataclasses import dataclass
from datetime import date
import json
import re
from pathlib import Path
import sqlite3

from apis.tmdb.detached_transport import DetachedTmdbError, DetachedTmdbTransport
from web.tmdb_ids import IdPlan, MAX_PER_MEDIA, QueueItem


@dataclass(frozen=True)
class HydrationRun:
    complete: bool
    stop_reason: str | None
    attempts_this_run: int
    completed: int
    hydrated: int
    ineligible: int
    missing_overview: int
    unavailable: int = 0


def _detail(transport, item, locale):
    row = transport.get(f"/{item.media_type}/{item.tmdb_id}", {"language": locale})
    title_key = "title" if item.media_type == "movie" else "name"
    if (type(row.get("id")) is not int or row["id"] != item.tmdb_id
            or row.get("media_type", item.media_type) != item.media_type
            or not isinstance(row.get(title_key), str) or not row[title_key].strip()):
        raise DetachedTmdbError("invalid_typed_detail")
    return row, row[title_key].strip()


_COUNTRY_CODE = re.compile(r"[A-Z]{2}", flags=re.ASCII)


def normalize_country_codes(codes):
    """Recognize a bounded, wholly shaped country-code list, not a locale."""
    if (not isinstance(codes, list) or not 1 <= len(codes) <= 256
            or any(not isinstance(code, str) or not _COUNTRY_CODE.fullmatch(code) for code in codes)):
        return ()
    return tuple(sorted(set(codes)))


def _fetch(transport, item):
    origin_sets = set()
    for locale in ("ru-RU", "en-US"):
        try:
            row, title = _detail(transport, item, locale)
        except DetachedTmdbError as error:
            # EN follows a successful typed RU response; a later 404 is
            # ambiguous/conflicting and must not persist resource absence.
            if locale == "ru-RU" and error.code == "http" and error.status == 404 and error.resource_missing:
                return "unavailable", None
            raise
        if row.get("adult") is not False:
            return "ineligible", None
        if item.media_type == "tv" and (codes := normalize_country_codes(row.get("origin_country"))):
            origin_sets.add(codes)
        overview = row.get("overview")
        if overview is None or (isinstance(overview, str) and not overview.strip()):
            continue
        if not isinstance(overview, str) or len(overview) > 8192 or len(title) > 512:
            raise DetachedTmdbError("invalid_typed_detail")
        raw_date = row.get("release_date" if item.media_type == "movie" else "first_air_date")
        try:
            year = date.fromisoformat(raw_date).year if isinstance(raw_date, str) else None
        except ValueError:
            year = None
        return "hydrated", json.dumps({
            "media_type": item.media_type, "tmdb_id": item.tmdb_id,
            "title": title, "overview": overview.strip(), "year": year,
            # Keep disagreement between locales unknown rather than merging.
            **({"origin_country_codes": next(iter(origin_sets))} if len(origin_sets) == 1 else {}),
            "requested_locale": locale,  # not proof of synopsis language
        }, ensure_ascii=False, sort_keys=True)
    return "missing_overview", None


HYDRATION_STATES = ("hydrated", "ineligible", "missing_overview", "unavailable")
_ITEMS_SQL = """CREATE TABLE hydration_items (
    media TEXT NOT NULL CHECK(media IN ('movie', 'tv')),
    tmdb_id INTEGER NOT NULL CHECK(tmdb_id > 0),
    status TEXT NOT NULL CHECK(status IN ('hydrated', 'ineligible', 'missing_overview', 'unavailable')),
    payload TEXT, PRIMARY KEY(media, tmdb_id),
    CHECK ((status = 'hydrated') = (payload IS NOT NULL))
)"""
_LEGACY_ITEMS_SQL = _ITEMS_SQL.replace(", 'unavailable'", "")


def _setup(conn, manifest):
    conn.execute("BEGIN IMMEDIATE")
    with conn:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not tables:
            conn.execute("CREATE TABLE hydration_plan (singleton INTEGER PRIMARY KEY CHECK(singleton=1), manifest TEXT NOT NULL)")
            conn.execute(_ITEMS_SQL)
            conn.execute("INSERT INTO hydration_plan VALUES (1, ?)", (manifest,))
        elif tables != {"hydration_plan", "hydration_items"} or conn.execute(
            "SELECT manifest FROM hydration_plan WHERE singleton=1"
        ).fetchone() != (manifest,):
            raise ValueError("Hydration checkpoint differs from the ID plan; use a separate checkpoint")
        else:
            schema, = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='hydration_items'").fetchone()
            normalized = " ".join(schema.split())
            if normalized == " ".join(_LEGACY_ITEMS_SQL.split()):
                conn.execute("ALTER TABLE hydration_items RENAME TO hydration_items_legacy")
                conn.execute(_ITEMS_SQL)
                conn.execute("INSERT INTO hydration_items SELECT media,tmdb_id,status,payload FROM hydration_items_legacy")
                conn.execute("DROP TABLE hydration_items_legacy")
            elif normalized != " ".join(_ITEMS_SQL.split()):
                raise ValueError("Unrecognized hydration items schema; use a separate checkpoint")


def hydrate_id_plan(
    *, plan: IdPlan, checkpoint: Path, transport: DetachedTmdbTransport,
) -> HydrationRun:
    """Hydrate through the supplied guarded transport; no implicit credentials.

    Use a dedicated private checkpoint, not the app database. One
    transaction per title contains its terminal result (not its partial RU/EN
    phase). If the second locale is stopped, the next run starts the title
    again. Do not reuse a throttled transport; the caller controls when to
    resume and can supply a new attempt budget. This is not catalog publication.
    """
    if not isinstance(transport, DetachedTmdbTransport):
        raise TypeError("Supply a guarded detached TMDb transport")
    cap = plan.per_media_limit
    if type(cap) is not int or not 1 <= cap <= MAX_PER_MEDIA or len(plan.queue) > 2 * cap:
        raise ValueError("Invalid bounded ID queue")
    counts = {"movie": 0, "tv": 0}
    identities = set()
    for item in plan.queue:
        if (not isinstance(item, QueueItem) or item.media_type not in counts
                or type(item.tmdb_id) is not int or not 0 < item.tmdb_id < 2**31
                or item in identities):
            raise ValueError("Invalid typed ID queue")
        identities.add(item)
        counts[item.media_type] += 1
        if counts[item.media_type] > cap:
            raise ValueError("Invalid bounded ID queue")
    manifest = json.dumps(plan.manifest(), sort_keys=True, separators=(",", ":"))
    start = transport.attempts
    stop = None
    with closing(sqlite3.connect(checkpoint, timeout=0)) as conn:
        _setup(conn, manifest)
        for item in plan.queue:
            try:
                # Serialize across callers before checking completion. A
                # concurrent process receives SQLITE_BUSY, not duplicate I/O.
                conn.execute("BEGIN IMMEDIATE")
                with conn:
                    key = (item.media_type, item.tmdb_id)
                    if conn.execute("SELECT 1 FROM hydration_items WHERE media=? AND tmdb_id=?", key).fetchone():
                        continue
                    status, payload = _fetch(transport, item)
                    conn.execute("INSERT INTO hydration_items VALUES (?, ?, ?, ?)", (*key, status, payload))
            except DetachedTmdbError as error:
                stop = error.code
                break
        statuses = dict(conn.execute("SELECT status, COUNT(*) FROM hydration_items GROUP BY status"))
    completed = sum(statuses.values())
    return HydrationRun(completed == len(plan.queue), stop, transport.attempts - start,
                        completed, statuses.get("hydrated", 0), statuses.get("ineligible", 0),
                        statuses.get("missing_overview", 0), statuses.get("unavailable", 0))

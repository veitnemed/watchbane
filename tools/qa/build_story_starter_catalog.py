"""Operator-only TMDb starter corpus builder; never opens Watchbane data stores."""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import closing
from dataclasses import asdict, dataclass
from datetime import date, timezone
from email.utils import parsedate_to_datetime
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import time
from urllib.error import HTTPError, URLError


MEDIA = ("movie", "tv")
# TV has composite action/adventure and sci-fi/fantasy genres. "|" is TMDb OR.
GENRES = {
    "movie": ("28|12", "35", "80|9648|53", "18|10749", "878|14|27", "16|10751", "99|36|10752"),
    "tv": ("10759", "35", "80|9648", "18|10766", "10765", "16|10751|10762", "99|10768"),
}
FIRST_DECADE = 1960
VERSION = 1


@dataclass(frozen=True)
class Plan:
    target: int = 5000
    through: str = date.today().isoformat()
    max_pages: int = 12
    min_overview: int = 50
    min_votes: int = 10

    def validate(self):
        end = date.fromisoformat(self.through)
        if not (1 <= self.target <= 5000 and 1 <= self.max_pages <= 100 and
                1 <= self.min_overview <= 500 and 0 <= self.min_votes <= 100 and
                FIRST_DECADE <= end.year and end <= date.today()):
            raise ValueError("Недопустимые параметры плана.")
        return end


@dataclass(frozen=True)
class Bucket:
    media: str
    start: str
    end: str
    genre: str

    @property
    def key(self):
        return f"{self.media}:{self.start[:4]}:{self.genre}"

    def request(self, page, min_votes):
        boundary = "primary_release_date" if self.media == "movie" else "first_air_date"
        return {
            "page": page, "language": "ru-RU", "include_adult": "false",
            "sort_by": "vote_count.desc", "vote_count.gte": min_votes, "with_genres": self.genre,
            f"{boundary}.gte": self.start, f"{boundary}.lte": self.end,
        }


def buckets(plan):
    end = plan.validate()
    for decade in range(FIRST_DECADE, end.year + 1, 10):
        start = f"{decade}-01-01"
        stop = min(date(decade + 9, 12, 31), end).isoformat()
        for m, t in zip(GENRES["movie"], GENRES["tv"], strict=True):
            yield Bucket("movie", start, stop, m)
            yield Bucket("tv", start, stop, t)


class AcquisitionError(RuntimeError):
    pass


def _caused_by(error, kinds):
    while error is not None:
        if isinstance(error, kinds):
            return error
        error = error.__cause__
    return None


def _retry_delay(error, attempt, clock):
    value = error.headers.get("Retry-After") if error and error.headers else None
    if value:
        try:
            return max(0.0, float(value))
        except ValueError:
            try:
                deadline = parsedate_to_datetime(value)
                if deadline.tzinfo is None:
                    deadline = deadline.replace(tzinfo=timezone.utc)
                return max(0.0, deadline.timestamp() - clock())
            except (ValueError, TypeError, OverflowError):
                pass
    return 2.0 ** attempt


class Acquisition:
    def __init__(self, get, *, retries=3, sleep=time.sleep, clock=time.time):
        self.get, self.retries, self.sleep, self.clock = get, retries, sleep, clock
        self.requests = self.detail_requests = 0

    def request(self, path, params, *, detail=False):
        for attempt in range(self.retries + 1):
            self.requests += 1
            self.detail_requests += int(detail)
            try:
                return self.get(path, params, retries=0, timeout=12)
            except (RuntimeError, OSError) as exc:
                http = _caused_by(exc, HTTPError)
                status = http.code if http else None
                if detail and status == 404:
                    return None
                retryable = status in {429, 500, 502, 503, 504} or (
                    status is None and _caused_by(exc, (URLError, TimeoutError)) is not None)
                if not retryable or attempt == self.retries:
                    raise AcquisitionError(f"TMDb: {'HTTP ' + str(status) if status else 'запрос не выполнен'}; "
                                           "готовые страницы сохранены в контрольной точке.") from None
                wait = _retry_delay(http, attempt, self.clock)
                # A longer server-requested cooldown is a stop, not a shorter retry.
                if not wait <= 60:
                    raise AcquisitionError("TMDb: длительный Retry-After; повторите запуск позже.") from None
                self.sleep(wait)
        raise AssertionError("unreachable")


def _id(row):
    if isinstance(row, dict):
        identifier = row.get("id")
        if type(identifier) is int and identifier > 0:
            return identifier
    return None


def _overview(row, minimum, language):
    text = " ".join(str(row.get("overview") or "").split())
    if len(text) < minimum:
        return ""
    letters = [ch for ch in text.casefold() if ch.isalpha()]
    script = sum(("а" <= ch <= "я" or ch == "ё") if language == "ru-RU"
                 else "a" <= ch <= "z" for ch in letters)
    if letters and script * 2 > len(letters):
        return text
    return ""


def _blocked(row):
    from candidates.safety.explicit_content import is_blocked_explicit_sexual_content
    return row.get("adult") is True or is_blocked_explicit_sexual_content({
        "adult": row.get("adult"), "title": row.get("title") or row.get("name"),
        "overview": row.get("overview"),
    })


def _origin_codes(value):
    from candidates.models.country_reference import COUNTRY_NAME_BY_ISO2

    if not isinstance(value, list):
        return []
    return sorted({code for item in value if isinstance(item, str)
                   if (code := item.strip().upper()) in COUNTRY_NAME_BY_ISO2})


def _record(api, bucket, row, plan, rejected):
    identifier = _id(row)
    if not identifier or _blocked(row):
        return None
    media = bucket.media
    title_key, date_key = ("title", "release_date") if media == "movie" else ("name", "first_air_date")
    title = str(row.get(title_key) or row.get("original_" + title_key) or "").strip()
    try:
        released = date.fromisoformat(str(row.get(date_key) or ""))
    except ValueError:
        return None
    if not date.fromisoformat(bucket.start) <= released <= date.fromisoformat(bucket.end):
        return None
    overview = _overview(row, plan.min_overview, "ru-RU")
    language = "ru-RU"
    origins = _origin_codes(row.get("origin_country"))
    if not overview:
        remote = api.request(f"/{media}/{identifier}", {"language": "en-US"}, detail=True)
        if remote is None:
            rejected["unusable_overview"] += 1
            return None
        if _id(remote) != identifier:
            raise AcquisitionError("Неожиданный ответ Details; эта страница не сохранена.")
        if _blocked(remote):
            return None
        language = "en-US"
        overview = _overview(remote, plan.min_overview, language)
        title = title or str(remote.get(title_key) or "").strip()
        origins = origins or _origin_codes(remote.get("origin_country"))
    if not overview:
        rejected["unusable_overview"] += 1
        return None
    if not title:
        return None
    poster = row.get("poster_path")
    genre_ids = row.get("genre_ids")
    data = {
        "key": f"tmdb:{media}:{identifier}", "tmdb_id": identifier, "media_type": media,
        "title": title, "overview": overview, "year": released.year, "language": language,
        "source": "tmdb", "discover_bucket": bucket.key,
        "genre_ids": sorted({x for x in genre_ids if type(x) is int and x > 0}) if isinstance(genre_ids, list) else [],
    }
    if origins:
        data["origin_country"] = origins
    if isinstance(poster, str) and poster.startswith("/") and "/" not in poster[1:] and "\\" not in poster:
        data["poster_path"] = poster
    return data


def _setup(conn, plan):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS overview_stats (
            bucket TEXT NOT NULL, page INTEGER NOT NULL, unusable INTEGER NOT NULL, PRIMARY KEY(bucket,page)
        );
        CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS batches (bucket TEXT PRIMARY KEY, next_page INTEGER NOT NULL, exhausted INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS seen (media TEXT NOT NULL, id INTEGER NOT NULL, PRIMARY KEY(media,id));
        CREATE TABLE IF NOT EXISTS entries (
            sequence INTEGER PRIMARY KEY, media TEXT NOT NULL, id INTEGER NOT NULL, payload TEXT NOT NULL,
            UNIQUE(media,id)
        );
    """)
    expected = json.dumps({"version": VERSION, "plan": asdict(plan), "genres": GENRES}, sort_keys=True)
    old = conn.execute("SELECT value FROM settings WHERE key='plan'").fetchone()
    if old and old[0] != expected:
        raise ValueError("Контрольная точка создана с другим планом. Укажите прежние параметры или другой файл.")
    conn.execute("INSERT OR IGNORE INTO settings VALUES ('plan',?)", (expected,))
    conn.commit()


def _page(conn, api, bucket, page, remaining, plan):
    response = api.request(f"/discover/{bucket.media}", bucket.request(page, plan.min_votes))
    if not isinstance(response, dict) or not isinstance(response.get("results"), list):
        raise AcquisitionError("Неожиданный ответ Discover; эта страница не сохранена.")
    returned = response["results"][:20]  # documented Discover page size
    accepted, processed, rejected = [], set(), Counter()
    for row in returned:
        identifier = _id(row)
        if identifier is None or identifier in processed or conn.execute(
                "SELECT 1 FROM seen WHERE media=? AND id=?", (bucket.media, identifier)).fetchone():
            continue
        processed.add(identifier)
        record = _record(api, bucket, row, plan, rejected)
        if record:
            accepted.append((bucket.media, identifier, json.dumps(record, ensure_ascii=False, sort_keys=True)))
            if len(accepted) == remaining:
                break
    pages = response.get("total_pages")
    exhausted = not returned or (type(pages) is int and page >= pages) or page >= plan.max_pages
    with conn:
        conn.executemany("INSERT INTO seen VALUES (?,?)", ((bucket.media, ident) for ident in processed))
        conn.executemany("INSERT INTO entries(media,id,payload) VALUES (?,?,?)", accepted)
        conn.execute("INSERT INTO overview_stats VALUES (?,?,?)", (bucket.key, page, rejected["unusable_overview"]))
        conn.execute("INSERT OR REPLACE INTO batches VALUES (?,?,?)", (bucket.key, page + 1, int(exhausted)))
    return len(accepted)


def _export(conn, output):
    output.parent.mkdir(parents=True, exist_ok=True)
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n", dir=output.parent, delete=False) as f:
            tmp = Path(f.name)
            for payload, in conn.execute("SELECT payload FROM entries ORDER BY sequence"):
                f.write(payload + "\n")
            f.flush()
            os.fsync(f.fileno())
        tmp.replace(output)
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)



def _coverage(conn):
    locales = Counter()
    tv_ru = tv_unknown = 0
    for media, payload in conn.execute("SELECT media,payload FROM entries"):
        record = json.loads(payload)
        locales[record["language"]] += 1
        if media == "tv":
            origins = record.get("origin_country", [])
            tv_ru += "RU" in origins
            tv_unknown += not origins
    committed, = conn.execute("SELECT COALESCE(SUM(next_page - 1), 0) FROM batches").fetchone()
    tracked, unusable = conn.execute("SELECT count(*), COALESCE(SUM(unusable), 0) FROM overview_stats").fetchone()
    return {"by_locale": {loc: locales[loc] for loc in ("ru-RU", "en-US")},
            "tv_russia_origin": tv_ru, "tv_unknown_origin": tv_unknown,
            "unusable_overview_count": unusable if tracked == committed else None}

def build_catalog(checkpoint, output, plan, *, get=None, sleep=time.sleep, progress=None):
    if get is None:
        from apis.tmdb_api import tmdb_get as get
    checkpoint, output = Path(checkpoint), Path(output)
    if checkpoint.resolve() == output.resolve():
        raise ValueError("Контрольная точка и JSONL должны лежать в разных файлах.")
    plan_buckets = tuple(buckets(plan))
    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    api = Acquisition(get, sleep=sleep)
    with closing(sqlite3.connect(checkpoint)) as conn:
        _setup(conn, plan)
        caps = {"movie": (plan.target + 1) // 2, "tv": plan.target // 2}
        counts = Counter(dict(conn.execute("SELECT media, count(*) FROM entries GROUP BY media")))
        while any(counts[x] < caps[x] for x in MEDIA):
            state = {key: (page, exhausted) for key, page, exhausted in
                     conn.execute("SELECT bucket,next_page,exhausted FROM batches")}
            pending = []
            for order, bucket in enumerate(plan_buckets):
                page, exhausted = state.get(bucket.key, (1, False))
                if counts[bucket.media] < caps[bucket.media] and not exhausted:
                    pending.append((page, order, bucket))
            if not pending:
                break
            # Same global round-robin sequence after resume, even mid-cycle.
            page, _, bucket = min(pending)
            need = caps[bucket.media] - counts[bucket.media]
            counts[bucket.media] += _page(conn, api, bucket, page, need, plan)
            if progress:
                progress({m: counts[m] for m in MEDIA} | {"bucket": bucket.key, "page": page, "api_requests": api.requests})
        complete = all(counts[m] == caps[m] for m in MEDIA)
        if complete:
            _export(conn, output)
        return {"complete": complete, "count": sum(counts.values()), "by_media": {m: counts[m] for m in MEDIA},
                "api_requests_this_run": api.requests, "english_detail_requests_this_run": api.detail_requests} | _coverage(conn)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--through", required=True, help="Фиксированная дата YYYY-MM-DD; та же при возобновлении.")
    parser.add_argument("--target", type=int, default=5000)
    parser.add_argument("--max-pages", type=int, default=12)
    parser.add_argument("--ask-token", action="store_true", help="Ввести API Read Access Token в терминале без сохранения.")
    args = parser.parse_args(argv)
    get = None
    try:
        if args.ask_token:
            from functools import partial
            from getpass import getpass
            if not sys.stdin.isatty():
                parser.error("--ask-token требует интерактивный терминал")
            from apis.tmdb_api import tmdb_get
            token = getpass("TMDb API Read Access Token: ").strip()
            if not token:
                parser.error("Токен не введён.")
            get = partial(tmdb_get, token=token)
        result = build_catalog(args.checkpoint, args.output, Plan(args.target, args.through, args.max_pages),
                               get=get,
                               progress=lambda state: print(json.dumps(state, ensure_ascii=False), file=sys.stderr, flush=True))
    except KeyboardInterrupt:
        print("Прервано. Для продолжения используйте ту же контрольную точку.", file=sys.stderr)
        return 130
    except (AcquisitionError, ValueError, sqlite3.Error, OSError) as exc:
        print(f"Не завершено: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["complete"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

"""Dry-run local TMDb Daily ID files or rehearse detached hydration offline.

Plan prints aggregate counts only and never writes. Rehearse uses invented
exports and in-memory HTTP responses: it never contacts TMDb, reads credentials,
or creates a searchable catalog. Choose a disposable owner-controlled directory.
"""
from __future__ import annotations

import argparse
from contextlib import closing
from dataclasses import asdict
from datetime import date
import gzip
from io import BytesIO
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from urllib.error import HTTPError
from urllib.parse import urlsplit

from apis.tmdb.detached_transport import DetachedTmdbTransport
from web.tmdb_catalog_audit import audit_hydration
from web.tmdb_hydration import hydrate_id_plan
from web.tmdb_ids import IdCohort, plan_daily_ids


_REHEARSAL_DATE = date(2026, 1, 10)
_CHECKPOINT_NAME = "synthetic-hydration.sqlite3"


def summarize_plan(plan):
    return {
        "date": plan.date,
        "per_media_limit": plan.per_media_limit,
        "cohort": asdict(plan.cohort) if plan.cohort else None,
        "planned": len(plan.queue),
        "planned_by_media": {media: sum(item.media_type == media for item in plan.queue)
                             for media in ("movie", "tv")},
        "sources": [asdict(source) for source in plan.sources],
        "queue_sha256": plan.manifest()["queue_sha256"],
    }


def _synthetic_plan(root):
    def source(stem, media):
        path = root / f"{stem}_{_REHEARSAL_DATE:%m_%d_%Y}.json.gz"
        data = "".join(json.dumps({"id": identifier, "adult": adult,
                                   "media_type": media}) + "\n"
                       for identifier, adult in ((101, False), (102, False), (103, True)))
        with path.open("wb") as target:
            with gzip.GzipFile(fileobj=target, filename="", mode="wb", mtime=0) as compressed:
                compressed.write(data.encode("utf-8"))
        return path

    return plan_daily_ids(export_date=_REHEARSAL_DATE, movie_file=source("movie_ids", "movie"),
                          tv_file=source("tv_series_ids", "tv"), per_media_limit=2)


class _FixtureOpener:
    """Routes consumed by the real detached HTTP transport; no network opener."""

    def __init__(self, plan, *, resume):
        self.interrupted = False
        self.requests_by_media = dict.fromkeys(("movie", "tv"), 0)
        self.completed_movie_replays = 0
        first_movie, second_movie, first_tv, second_tv = plan.queue
        self.completed_movie = first_movie
        self.routes = {}
        for item, locale, overview in (
            (first_movie, "ru-RU", "Условная история о мастерской."),
            (second_movie, "ru-RU", ""),
            (first_tv, "ru-RU", ""),
            (first_tv, "en-US", "Invented story about a mountain village."),
        ):
            self._row(item, locale, overview)
        if resume:
            self._row(second_movie, "en-US", "")
        else:
            self._route(second_movie, "en-US", 429, {"success": False})
        self._route(second_tv, "ru-RU", 404, {"success": False, "status_code": 34})

    def _route(self, item, locale, status, payload):
        self.routes[(f"/3/{item.media_type}/{item.tmdb_id}", f"language={locale}")] = (
            status, json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        )

    def _row(self, item, locale, overview):
        title_key = "title" if item.media_type == "movie" else "name"
        self._route(item, locale, 200, {"id": item.tmdb_id, "media_type": item.media_type,
                                       title_key: "Synthetic fixture", "adult": False,
                                       "overview": overview})

    def __call__(self, request, *, timeout):
        url = urlsplit(request.full_url)
        if url.scheme != "https" or url.netloc != "api.themoviedb.org":
            raise ValueError("Unexpected fixture origin")
        route = self.routes.get((url.path, url.query))
        if route is None:
            raise ValueError("Unexpected fixture request")
        self.requests_by_media[url.path.split("/")[2]] += 1
        if url.path == f"/3/{self.completed_movie.media_type}/{self.completed_movie.tmdb_id}":
            self.completed_movie_replays += 1
        status, payload = route
        if status != 200:
            self.interrupted |= status == 429
            raise HTTPError(request.full_url, status, "Synthetic fixture",
                            {"Content-Type": "application/json"}, BytesIO(payload))
        return BytesIO(payload)


def rehearse(checkpoint_dir, *, resume):
    directory = Path(checkpoint_dir)
    checkpoint = directory / _CHECKPOINT_NAME
    with TemporaryDirectory(prefix="watchbane-tmdb-fixture-") as temp:
        plan = _synthetic_plan(Path(temp))
        if resume:
            if (directory.is_symlink() or not directory.is_dir() or checkpoint.is_symlink()
                    or not checkpoint.is_file() or checkpoint.stat().st_nlink != 1
                    or {entry.name for entry in directory.iterdir()} != {_CHECKPOINT_NAME}):
                raise ValueError("Expected a dedicated rehearsal checkpoint")
            # Audit the exact fixture manifest before a writable open. Never
            # let resume implicitly create a database or migrate another plan.
            prior = audit_hydration(plan=plan, checkpoint=checkpoint)["distinct_typed_completed"]
            if prior not in (1, len(plan.queue)):
                raise ValueError("Expected interrupted or finished rehearsal")
            # An arbitrary one-row checkpoint is not an interruption proof.
            # Only the first fixture item can have committed before the 429.
            if prior == 1:
                first = plan.queue[0]
                with closing(sqlite3.connect(checkpoint.resolve().as_uri() + "?mode=ro", uri=True)) as conn:
                    terminal = conn.execute("SELECT media, tmdb_id, status FROM hydration_items").fetchall()
                if terminal != [(first.media_type, first.tmdb_id, "hydrated")]:
                    raise ValueError("Expected the rehearsal interruption boundary")
        else:
            # Exclusive directory creation refuses an existing profile, empty
            # directory, or symlink before the SQLite path is opened.
            directory.mkdir(mode=0o700)
            prior = 0
        opener = _FixtureOpener(plan, resume=resume)
        transport = DetachedTmdbTransport(2 * len(plan.queue), bearer=lambda: "offline-fixture", opener=opener)
        run = hydrate_id_plan(plan=plan, checkpoint=checkpoint, transport=transport)
        audit = audit_hydration(plan=plan, checkpoint=checkpoint)
        if resume:
            if not run.complete or opener.interrupted or opener.completed_movie_replays:
                raise RuntimeError("Unexpected fixture resume outcome")
        elif run.stop_reason != "throttled" or not opener.interrupted or run.completed != 1:
            raise RuntimeError("Did not observe the expected 429 fixture boundary")
        return {
            "mode": "synthetic_offline_rehearsal",
            "phase": "already_complete" if prior == len(plan.queue) else "resumed" if resume else "interrupted",
            "planned": len(plan.queue),
            "completed_before": prior,
            **asdict(run),
            "completed_this_run": run.completed - prior,
            "pending": len(plan.queue) - run.completed,
            "http_429_this_run": int(opener.interrupted),
            "requests_by_media_this_run": opener.requests_by_media,
            "audit": audit,
        }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    plan = commands.add_parser("plan", help="read-only deterministic plan of two supplied gzip exports")
    plan.add_argument("--export-date", type=date.fromisoformat, required=True)
    plan.add_argument("--movie", type=Path, required=True)
    plan.add_argument("--tv", type=Path, required=True)
    plan.add_argument("--per-media-limit", type=int, required=True)
    plan.add_argument("--cohort", nargs=2, type=int, metavar=("COUNT", "INDEX"))
    trial = commands.add_parser("rehearse", help="synthetic run stopped by 429; use --resume in a new process")
    trial.add_argument("--checkpoint-dir", type=Path, required=True,
                       help="new disposable directory; only --resume accepts an existing rehearsal")
    trial.add_argument("--resume", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "plan":
            cohort = IdCohort(*args.cohort) if args.cohort is not None else None
            result = {"mode": "read_only_dry_run", **summarize_plan(plan_daily_ids(
                export_date=args.export_date, movie_file=args.movie, tv_file=args.tv,
                per_media_limit=args.per_media_limit, cohort=cohort))}
        else:
            result = rehearse(args.checkpoint_dir, resume=args.resume)
    except (OSError, RuntimeError, TypeError, ValueError, sqlite3.Error) as exc:
        parser.exit(2, f"Detached TMDb preflight failed: {type(exc).__name__}\n")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

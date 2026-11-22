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
        **({"schedule": plan.manifest()["schedule"]} if plan.interleave else {}),
    }


def _synthetic_plan(root, *, interleave):
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
                          tv_file=source("tv_series_ids", "tv"), per_media_limit=2, interleave=interleave)


class _FixtureOpener:
    """Routes consumed by the real detached HTTP transport; no network opener."""

    def __init__(self, plan, *, resume, completed_before):
        self.interrupted = False
        self.requests_by_media = dict.fromkeys(("movie", "tv"), 0)
        self.request_media_order = []
        first_movie, second_movie = (item for item in plan.queue if item.media_type == "movie")
        first_tv, second_tv = (item for item in plan.queue if item.media_type == "tv")
        self.request_order = []
        for item in plan.queue[completed_before:]:
            locales = ("ru-RU",) if item in (first_movie, second_tv) else ("ru-RU", "en-US")
            self.request_order.extend((f"/3/{item.media_type}/{item.tmdb_id}", f"language={locale}")
                                      for locale in locales)
            if item == second_movie and not resume:
                break
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
        key = url.path, url.query
        index = len(self.request_media_order)
        if index >= len(self.request_order) or key != self.request_order[index]:
            raise ValueError("Unexpected fixture request order")
        route = self.routes.get(key)
        if route is None:
            raise ValueError("Unexpected fixture request")
        media = url.path.split("/")[2]
        self.requests_by_media[media] += 1
        self.request_media_order.append(media)
        status, payload = route
        if status != 200:
            self.interrupted |= status == 429
            raise HTTPError(request.full_url, status, "Synthetic fixture",
                            {"Content-Type": "application/json"}, BytesIO(payload))
        return BytesIO(payload)


def rehearse(checkpoint_dir, *, resume, interleave=False):
    directory = Path(checkpoint_dir)
    checkpoint = directory / _CHECKPOINT_NAME
    with TemporaryDirectory(prefix="watchbane-tmdb-fixture-") as temp:
        plan = _synthetic_plan(Path(temp), interleave=interleave)
        # A synthetic 429 always stops during the second movie's English
        # lookup. In the new schedule one TV title has already completed.
        prefix_size = 2 if interleave else 1
        if resume:
            if (directory.is_symlink() or not directory.is_dir() or checkpoint.is_symlink()
                    or not checkpoint.is_file() or checkpoint.stat().st_nlink != 1
                    or {entry.name for entry in directory.iterdir()} != {_CHECKPOINT_NAME}):
                raise ValueError("Expected a dedicated rehearsal checkpoint")
            # Audit the exact fixture manifest before a writable open. Never
            # let resume implicitly create a database or migrate another plan.
            prior = audit_hydration(plan=plan, checkpoint=checkpoint)["distinct_typed_completed"]
            if prior not in (prefix_size, len(plan.queue)):
                raise ValueError("Expected interrupted or finished rehearsal")
            # A count is not an interruption proof. Validate exact typed
            # prefix and terminal state before the next process can write.
            if prior == prefix_size:
                with closing(sqlite3.connect(checkpoint.resolve().as_uri() + "?mode=ro", uri=True)) as conn:
                    terminal = set(conn.execute("SELECT media, tmdb_id, status FROM hydration_items"))
                if terminal != {(item.media_type, item.tmdb_id, "hydrated")
                                for item in plan.queue[:prefix_size]}:
                    raise ValueError("Expected the rehearsal interruption boundary")
        else:
            # Exclusive directory creation refuses an existing profile, empty
            # directory, or symlink before the SQLite path is opened.
            directory.mkdir(mode=0o700)
            prior = 0
        opener = _FixtureOpener(plan, resume=resume, completed_before=prior)
        transport = DetachedTmdbTransport(2 * len(plan.queue), bearer=lambda: "offline-fixture", opener=opener)
        run = hydrate_id_plan(plan=plan, checkpoint=checkpoint, transport=transport)
        audit = audit_hydration(plan=plan, checkpoint=checkpoint)
        if run.attempts_this_run != len(opener.request_order):
            raise RuntimeError("Unexpected fixture attempt count")
        if resume:
            if not run.complete or opener.interrupted:
                raise RuntimeError("Unexpected fixture resume outcome")
        elif run.stop_reason != "throttled" or not opener.interrupted or run.completed != prefix_size:
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
            **({"schedule": plan.manifest()["schedule"], "request_media_order": opener.request_media_order}
               if interleave else {}),
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
    for command in (plan, trial):
        command.add_argument("--interleave", action="store_true",
                             help="alternate movie and TV title starts; keep this option unchanged for resume")
    args = parser.parse_args(argv)
    try:
        if args.command == "plan":
            cohort = IdCohort(*args.cohort) if args.cohort is not None else None
            result = {"mode": "read_only_dry_run", **summarize_plan(plan_daily_ids(
                export_date=args.export_date, movie_file=args.movie, tv_file=args.tv,
                per_media_limit=args.per_media_limit, cohort=cohort, interleave=args.interleave))}
        else:
            result = rehearse(args.checkpoint_dir, resume=args.resume, interleave=args.interleave)
    except (OSError, RuntimeError, TypeError, ValueError, sqlite3.Error) as exc:
        parser.exit(2, f"Detached TMDb preflight failed: {type(exc).__name__}\n")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

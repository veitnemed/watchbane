"""Explicit two-title POSIX operator probe; no implicit credentials or export.

Generate an aggregate local `manifest` first. `run` will only use a fresh
private checkpoint, a pinned approved manifest, and an operator-supplied
owner-only bearer file. It may make up to four live TMDb Details requests.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import date
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import sqlite3
import stat

from apis.tmdb.detached_transport import DetachedTmdbError, DetachedTmdbTransport
from web.tmdb_catalog_audit import audit_hydration
from web.tmdb_hydration import hydrate_id_plan
from web.tmdb_ids import plan_daily_ids


_SHA = re.compile(r"[0-9a-f]{64}")
_CHECKPOINT = "private-tmdb-microprobe.sqlite3"
_ATTEMPTS = 4


def _aggregate_plan(args):
    plan = plan_daily_ids(export_date=args.export_date, movie_file=args.movie,
                          tv_file=args.tv, per_media_limit=1)
    if [item.media_type for item in plan.queue] != ["movie", "tv"]:
        raise ValueError("Exactly one eligible movie and TV title required")
    return plan


def _manifest_bytes(plan):
    return (json.dumps(plan.manifest(), sort_keys=True, separators=(",", ":")) + "\n").encode("ascii")


def _verify_manifest(args, plan):
    if not (_SHA.fullmatch(args.manifest_sha256) and _SHA.fullmatch(args.queue_sha256)):
        raise ValueError("Require exact approved manifest and queue digests")
    approved = _manifest_bytes(plan)
    if (args.queue_sha256 != plan.manifest()["queue_sha256"]
            or args.manifest_sha256 != sha256(approved).hexdigest()):
        raise ValueError("Unapproved manifest or queue")
    # Read exact bytes from a regular local file with a strict bound.
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
    with os.fdopen(os.open(args.manifest, flags), "rb") as source:
        if (not stat.S_ISREG(os.fstat(source.fileno()).st_mode)
                or source.read(len(approved) + 1) != approved):
            raise ValueError("Unapproved manifest bytes")


def _read_bearer(path):
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
    with os.fdopen(os.open(path, flags), "rb") as file:
        info = os.fstat(file.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                or stat.S_IMODE(info.st_mode) not in (0o400, 0o600) or info.st_nlink != 1 or not 1 <= info.st_size <= 4096):
            raise PermissionError("Require a private owner-only credential file")
        token = file.read(4097)
        if len(token) > 4096:
            raise ValueError("Invalid bearer")
    token = token.removesuffix(b"\n").removesuffix(b"\r")
    if not re.fullmatch(rb"[A-Za-z0-9._~-]{20,4096}", token):
        raise ValueError("Invalid bearer")
    return token.decode("ascii")


class _ObservedTransport(DetachedTmdbTransport):
    """Retain only the HTTP status, not exception, URL, response or token."""

    def __init__(self, credential, *, opener):
        self.status = None
        self._credential = credential
        super().__init__(_ATTEMPTS, bearer=lambda: credential, opener=opener)

    def get(self, path, params):
        self.status = None
        try:
            row = super().get(path, params)
            # Credential material reflected by a fixture or provider must
            # not become part of a stored title or description.
            for field in ("title", "name", "overview"):
                value = row.get(field)
                if isinstance(value, str) and self._credential in value:
                    raise DetachedTmdbError("reflected_credential")
            return row
        except DetachedTmdbError as error:
            self.status = error.status
            raise


def _live_run(args, plan, *, opener):
    if (not args.confirm_live_rights or os.name != "posix"
            or not all(hasattr(os, name) for name in ("O_NOFOLLOW", "O_NONBLOCK", "geteuid"))):
        raise PermissionError("Explicit rights approval and POSIX file protections required")
    _verify_manifest(args, plan)
    # Exclusive creation is intentional. No reuse, resume, cleanup, profile
    # migration, or overwrite. The operator must choose a controlled parent.
    parent = args.checkpoint_dir.parent
    parent_info = parent.lstat()
    if (not stat.S_ISDIR(parent_info.st_mode) or parent_info.st_uid != os.geteuid()
            or parent_info.st_mode & 0o022):
        raise PermissionError("Require an owner-controlled checkpoint parent")
    try:
        args.checkpoint_dir.lstat()
    except FileNotFoundError:
        pass
    else:
        raise FileExistsError("Choose a fresh private checkpoint directory")
    bearer = _read_bearer(args.bearer_file)
    # Still use exclusive mkdir after preflight to reject a concurrent creator.
    args.checkpoint_dir.mkdir(mode=0o700)
    checkpoint = args.checkpoint_dir / _CHECKPOINT
    fd = os.open(checkpoint, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    os.close(fd)
    transport = _ObservedTransport(bearer, opener=opener)
    run = hydrate_id_plan(plan=plan, checkpoint=checkpoint, transport=transport)
    # Only aggregate audit output; stored descriptions stay private.
    audit = audit_hydration(plan=plan, checkpoint=checkpoint)
    return {
        "mode": "detached_tmdb_details_microprobe",
        "planned": 2,
        "attempt_limit": _ATTEMPTS,
        **asdict(run),
        "http_stop_status": transport.status if run.stop_reason else None,
        "audit": audit,
    }


def main(argv=None, *, opener=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    manifest = sub.add_parser("manifest", help="read-only canonical bytes for independent operator approval")
    live = sub.add_parser("run", help="explicit live HTTPS to two pinned typed Details resources only")
    for command in (manifest, live):
        command.add_argument("--export-date", type=date.fromisoformat, required=True)
        command.add_argument("--movie", type=Path, required=True)
        command.add_argument("--tv", type=Path, required=True)
    live.add_argument("--manifest", type=Path, required=True)
    live.add_argument("--manifest-sha256", required=True)
    live.add_argument("--queue-sha256", required=True)
    live.add_argument("--checkpoint-dir", type=Path, required=True)
    live.add_argument("--bearer-file", type=Path, required=True, help="operator-only POSIX bearer file, mode 0400 or 0600")
    live.add_argument("--confirm-live-rights", action="store_true",
                      help="operator attests authorized source, account and intended private use")
    args = parser.parse_args(argv)
    try:
        plan = _aggregate_plan(args)
        if args.action == "manifest":
            print(_manifest_bytes(plan).decode("ascii"), end="")
            return 0
        result = _live_run(args, plan, opener=opener)
    except (OSError, ValueError, TypeError, RuntimeError, sqlite3.Error) as error:
        parser.exit(2, f"TMDb microprobe refused: {type(error).__name__}\n")
    print(json.dumps(result, sort_keys=True))
    return 0 if result["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

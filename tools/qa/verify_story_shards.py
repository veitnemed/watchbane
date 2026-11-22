"""Verify exact offline catalogue shard bytes on POSIX; never publish or activate."""
import argparse
import hashlib
import json
import os
import re
import sqlite3
import stat
import tempfile

from candidates.story_seed_snapshot import (
    MAX_FILE_BYTES, MAX_LINE_BYTES, MAX_ROWS, _row,
)

MAX_SHARDS = 16
MAX_MANIFEST = 32 * 1024
MAX_TOTAL_ROWS = 100_000
MAX_TOTAL_BYTES = 256 * 1024**2
MAX_SQLITE_PAGES = 65_536  # 256 MiB at the explicit 4096-byte page size.
MANIFEST_NAME = "manifest.json"
SHA256 = re.compile(r"[0-9a-f]{64}")


class ShardVerificationError(ValueError):
    pass


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(_value):
    raise ValueError("invalid JSON constant")


def _parse(raw):
    return json.loads(raw.decode("utf-8"), object_pairs_hook=_unique, parse_constant=_reject_constant)


def _int(num, minimum, maximum):
    return type(num) is int and minimum <= num <= maximum


def _stats(obj, row_cap, byte_cap):
    return (all(_int(obj[name], 0, row_cap) for name in ("movie", "tv"))
            and _int(obj["rows"], 1, row_cap) and _int(obj["bytes"], 1, byte_cap)
            and obj["rows"] == obj["movie"] + obj["tv"])


def _manifest(raw):
    result = _parse(raw)
    counters = {"rows", "bytes", "movie", "tv"}
    if (not isinstance(result, dict) or set(result) != {"version", "shards", "total"}
            or not _int(result["version"], 1, 1)
            or not isinstance(result["shards"], list) or not 1 <= len(result["shards"]) <= MAX_SHARDS
            or not isinstance(result["total"], dict) or set(result["total"]) != counters
            or not _stats(result["total"], MAX_TOTAL_ROWS, MAX_TOTAL_BYTES)):
        raise ShardVerificationError("invalid manifest schema")
    for number, entry in enumerate(result["shards"]):
        if (not isinstance(entry, dict) or set(entry) != counters | {"file", "sha256"}
                or entry["file"] != f"part-{number:05d}.jsonl"
                or not isinstance(entry["sha256"], str) or not SHA256.fullmatch(entry["sha256"])
                or not _stats(entry, MAX_ROWS, MAX_FILE_BYTES)):
            raise ShardVerificationError("invalid shard declaration")
    if any(sum(entry[key] for entry in result["shards"]) != result["total"][key] for key in counters):
        raise ShardVerificationError("inconsistent manifest totals")
    return result


def _identity(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_size, info.st_nlink,
            info.st_mtime_ns, info.st_ctime_ns)


def _supported():
    return (os.name == "posix" and {os.open, os.stat} <= os.supports_dir_fd
            and os.stat in os.supports_follow_symlinks
            and all(hasattr(os, name) for name in ("O_NOFOLLOW", "O_NONBLOCK", "O_DIRECTORY")))


def _open_regular(directory, name, limit):
    listed = os.stat(name, dir_fd=directory, follow_symlinks=False)
    if (not stat.S_ISREG(listed.st_mode) or listed.st_nlink != 1
            or not 0 < listed.st_size <= limit):
        raise ShardVerificationError("input is not a bounded singly linked regular file")
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
    try:
        info = os.fstat(fd)
        if _identity(info) != _identity(listed):
            raise ShardVerificationError("input changed before open")
        return os.fdopen(fd, "rb"), info
    except BaseException:
        os.close(fd)
        raise


def _check_input(stream, start):
    if _identity(os.fstat(stream.fileno())) != _identity(start):
        raise ShardVerificationError("input changed during verification")


def _read_shard(root_fd, entry, ids, seen_inodes):
    stream, start = _open_regular(root_fd, entry["file"], entry["bytes"])
    with stream:
        inode = (start.st_dev, start.st_ino)
        if inode in seen_inodes or start.st_size != entry["bytes"]:
            raise ShardVerificationError("reused input inode or wrong declared size")
        seen_inodes.add(inode)
        digest = hashlib.sha256()
        records = {"rows": 0, "bytes": 0, "movie": 0, "tv": 0}
        while line := stream.readline(MAX_LINE_BYTES + 1):
            records["rows"] += 1
            records["bytes"] += len(line)
            if (len(line) > MAX_LINE_BYTES or records["rows"] > entry["rows"]
                    or records["bytes"] > entry["bytes"]):
                raise ShardVerificationError("shard exceeds declaration")
            digest.update(line)
            _key, row = _row(_parse(line))
            media = row["media_type"]
            records[media] += 1
            try:
                ids.execute("INSERT INTO typed VALUES (?, ?)", (media, str(row["tmdb_id"])))
            except sqlite3.IntegrityError:
                raise ShardVerificationError("duplicate typed ID") from None
        _check_input(stream, start)
        if any(records[key] != entry[key] for key in records) or digest.hexdigest() != entry["sha256"]:
            raise ShardVerificationError("shard counters or pin mismatch")


def verify_shards(directory, expected_sha256):
    """Verify observations from opened descriptors, not future path authorization."""
    if not _supported():
        raise ShardVerificationError("required POSIX file opening semantics unavailable")
    if not isinstance(expected_sha256, str) or not SHA256.fullmatch(expected_sha256):
        raise ShardVerificationError("invalid manifest pin")
    try:
        root_fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            mfile, info = _open_regular(root_fd, MANIFEST_NAME, MAX_MANIFEST)
            with mfile:
                raw = mfile.read(MAX_MANIFEST + 1)
                _check_input(mfile, info)
            if len(raw) > MAX_MANIFEST or hashlib.sha256(raw).hexdigest() != expected_sha256:
                raise ShardVerificationError("manifest pin mismatch")
            manifest = _manifest(raw)
            seen_inodes = {(info.st_dev, info.st_ino)}
            # Private disposable uniqueness index, not a generation or a profile.
            with tempfile.TemporaryDirectory(prefix="watchbane-shard-check-") as scratch:
                ids = sqlite3.connect(os.path.join(scratch, "typed.sqlite"))
                try:
                    ids.execute("PRAGMA page_size=4096")
                    ids.execute("PRAGMA cache_size=-2048")
                    ids.execute("PRAGMA journal_mode=OFF")
                    if ids.execute(f"PRAGMA max_page_count={MAX_SQLITE_PAGES}").fetchone() != (MAX_SQLITE_PAGES,):
                        raise ShardVerificationError("temporary uniqueness bound unavailable")
                    ids.execute("CREATE TABLE typed (media TEXT, id TEXT, PRIMARY KEY(media,id)) WITHOUT ROWID")
                    for entry in manifest["shards"]:
                        _read_shard(root_fd, entry, ids, seen_inodes)
                finally:
                    ids.close()
            return {"status": "VERIFIED_BYTES_ONLY", "manifest_sha256": expected_sha256,
                    "shards": len(manifest["shards"]), **manifest["total"]}
        finally:
            os.close(root_fd)
    except ShardVerificationError:
        raise
    except (OSError, sqlite3.Error, UnicodeError, ValueError, RecursionError, OverflowError):
        raise ShardVerificationError("invalid or unreadable shard input") from None


def main(argv=None):
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--directory", required=True)
    cli.add_argument("--manifest-sha256", required=True)
    args = cli.parse_args(argv)
    try:
        result = verify_shards(args.directory, args.manifest_sha256)
    except ShardVerificationError as exc:
        cli.exit(1, f"Verification rejected: {exc}\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()

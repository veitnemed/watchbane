"""Compose a private reviewed seed generation without replacing an active one."""
from collections.abc import Mapping
from contextlib import closing, nullcontext
from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import sqlite3
from tempfile import NamedTemporaryFile

from candidates.story_seed_snapshot import (
    MAX_FILE_BYTES,
    MAX_LINE_BYTES,
    MAX_ROWS,
    load_seed_snapshot_with_digest,
)
from web.tmdb_ids import QueueItem
from web.tmdb_reviewed_refresh import (
    ReviewedRefresh, _read_reviewed_refresh, _validated_reviews, read_reviewed_refresh,
)


@dataclass(frozen=True)
class ComposedGeneration:
    previous_sha256: str
    sha256: str
    rows: int
    replaced: int
    added: int
    reviews: tuple[tuple[QueueItem, ReviewedRefresh], ...]


def _existing_seed_row(row):
    # Preserve the loader's recognized seed fields, not arbitrary input extras.
    return {
        **{key: row[key] for key in ("media_type", "tmdb_id", "title", "overview", "year")},
        "language": "ru-RU" if "ru" in row["localized"] else "en-US",
        **({"poster_path": row["poster_path"]} if "poster_path" in row else {}),
    }


def compose_reviewed_generation(
    *, previous: Path, previous_sha256: str, checkpoint: Path, output: Path,
    reviewed: Mapping[QueueItem, ReviewedRefresh], use_cleared: bool = False,
) -> ComposedGeneration:
    """Atomically create an unactivated generation at a new filename.

    The caller attests clearance for the intended use of all rows. The base is
    the exact verified prior seed (including its recognized poster metadata).
    Only explicit, versioned review matches may upsert typed rows; there is no
    deletion instruction, and existing Russian coverage cannot be demoted
    to English fallback. A refresh can become stale after the DB read, so
    an operator must check freshness again before any later activation.
    """
    if use_cleared is not True:
        raise PermissionError("Explicit intended-use clearance is required")
    if type(previous_sha256) is not str or re.fullmatch(r"[a-f0-9]{64}", previous_sha256) is None:
        raise ValueError("An exact prior seed SHA-256 is required")
    output = Path(output)
    if output.exists() or output.is_symlink():
        raise FileExistsError("Choose a new seed generation destination")

    snapshot, digest = load_seed_snapshot_with_digest(previous)
    if digest != previous_sha256:
        raise ValueError("Previous seed SHA-256 does not match")
    rows = {key: _existing_seed_row(row) for key, row in snapshot.items()}
    reviews = _validated_reviews(reviewed)
    changes = read_reviewed_refresh(checkpoint=checkpoint, reviewed=dict(reviews))
    replaced = 0
    for change in changes:
        old = rows.get(change.item.key)
        if old and old["language"] == "ru-RU" and change.language != "ru-RU":
            raise ValueError("Reviewed refresh would remove Russian search coverage")
        replaced += old is not None
        rows[change.item.key] = {
            "media_type": change.item.media_type, "tmdb_id": change.item.tmdb_id,
            "title": change.title, "overview": change.overview,
            "language": change.language, "year": change.year,
            **({"poster_path": old["poster_path"]} if old and "poster_path" in old else {}),
        }
    digest_out = _write_detached_seed(output, rows)
    return ComposedGeneration(digest, digest_out, len(rows), replaced, len(changes) - replaced, reviews)


def _write_detached_seed(output, rows):
    return _write_detached_lines(output, (
        (json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
        for row in rows.values()
    ))


def _write_detached_lines(output, lines, *, publication_guard=nullcontext):
    written = 0
    line_no = 0
    new_digest = sha256()
    temporary = None
    try:
        with NamedTemporaryFile(dir=output.parent, prefix=".tmdb-generation-", delete=False) as stream:
            temporary = Path(stream.name)
            for line_no, line in enumerate(lines, 1):
                written += len(line)
                if len(line) > MAX_LINE_BYTES or written > MAX_FILE_BYTES or line_no > MAX_ROWS:
                    raise ValueError("Seed exceeds reader size limits")
                stream.write(line)
                new_digest.update(line)
            if not line_no:
                raise ValueError("Cannot seal an empty seed")
            stream.flush()
            os.fsync(stream.fileno())
        # Same-directory hard link is atomic and fails if a competitor creates
        # the destination first. Never fall back to copying or overwriting.
        with publication_guard():
            os.link(temporary, output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)

    return new_digest.hexdigest()



def apply_reviewed_generation_locally(
    *, checkpoint: Path, generation: Path, receipt: ComposedGeneration, switch_local,
    use_cleared: bool = False,
):
    """Guard one synchronous, in-memory switch of a detached local generation.

    The trusted caller supplies the composer receipt and a short local callback.
    The callback receives the expected prior digest, the candidate digest, and
    the exact verified rows (not the path). It must atomically compare the
    current local generation to the prior digest and adopt the passed rows, or
    decline without mutation. Do not reload from disk or schedule a later
    switch in that callback. This is not a durable pointer, routing change or
    distributed lock. Only competing SQLite writes on this checkpoint are
    excluded until the callback returns; the checkpoint must not be replaced.
    Prepare/validate expensive state outside the callback where applicable.
    """
    if use_cleared is not True:
        raise PermissionError("Explicit intended-use clearance is required")
    if not isinstance(receipt, ComposedGeneration):
        raise ValueError("Expected a composer receipt")
    reviews = _validated_reviews(dict(receipt.reviews))
    if (reviews != receipt.reviews or not callable(switch_local)
            or any(type(digest) is not str or re.fullmatch(r"[a-f0-9]{64}", digest) is None
                   for digest in (receipt.previous_sha256, receipt.sha256))):
        raise ValueError("Invalid generation receipt or local switch")

    # Parse the same bytes covered by the digest, and keep the global loader
    # cache insulated from callback mutation. Never give it a mutable pathname.
    snapshot, digest = load_seed_snapshot_with_digest(generation)
    if digest != receipt.sha256 or len(snapshot) != receipt.rows:
        raise ValueError("Candidate seed does not match the composer receipt")
    snapshot = deepcopy(snapshot)
    with closing(sqlite3.connect(Path(checkpoint).resolve().as_uri() + "?mode=rw",
                                 uri=True, timeout=0)) as conn:
        # Acquire before checking and hold through the switch. A read
        # transaction alone permits the problematic interleave in WAL mode.
        conn.execute("BEGIN IMMEDIATE")
        try:
            current = _read_reviewed_refresh(conn, reviews)
            for change in current:
                row = snapshot.get(change.item.key)
                if (row is None or row["title"] != change.title.strip()
                        or row["overview"] != change.overview.strip() or row["year"] != change.year
                        or set(row["localized"]) != {change.language[:2]}):
                    raise ValueError("Candidate seed does not contain the exact reviewed refresh")
            return switch_local(receipt.previous_sha256, digest, snapshot)
        finally:
            conn.rollback()

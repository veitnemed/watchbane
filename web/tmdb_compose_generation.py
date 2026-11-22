"""Compose a private reviewed seed generation without replacing an active one."""
from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from tempfile import NamedTemporaryFile

from candidates.story_seed_snapshot import (
    MAX_FILE_BYTES,
    MAX_LINE_BYTES,
    MAX_ROWS,
    load_seed_snapshot_with_digest,
)
from web.tmdb_ids import QueueItem
from web.tmdb_reviewed_refresh import ReviewedRefresh, read_reviewed_refresh


@dataclass(frozen=True)
class ComposedGeneration:
    previous_sha256: str
    sha256: str
    rows: int
    replaced: int
    added: int


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
    changes = read_reviewed_refresh(checkpoint=checkpoint, reviewed=reviewed)
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
    if len(rows) > MAX_ROWS:
        raise ValueError("Seed exceeds reader size limits")

    written = 0
    new_digest = sha256()
    temporary = None
    try:
        with NamedTemporaryFile(dir=output.parent, prefix=".tmdb-generation-", delete=False) as stream:
            temporary = Path(stream.name)
            for key in rows:
                line = (json.dumps(rows[key], ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                        + "\n").encode("utf-8")
                written += len(line)
                if len(line) > MAX_LINE_BYTES or written > MAX_FILE_BYTES:
                    raise ValueError("Seed exceeds reader size limits")
                stream.write(line)
                new_digest.update(line)
            stream.flush()
            os.fsync(stream.fileno())
        # Same-directory hard link is atomic and fails if a competitor creates
        # the destination first. Never fall back to copying or overwriting.
        os.link(temporary, output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)

    return ComposedGeneration(digest, new_digest.hexdigest(), len(rows), replaced, len(changes) - replaced)

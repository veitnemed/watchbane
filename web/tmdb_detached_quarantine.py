"""Seal one explicitly reviewed adult exclusion without any activation path."""
from contextlib import closing, contextmanager
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import re
import sqlite3

from candidates.story_seed_snapshot import MAX_LINE_BYTES, load_seed_snapshot_with_digest
from web.tmdb_change_windows import (
    MAX_COMPLETION_BYTES, _TABLES, _item_key, _reject_payload_constant, _table_names, _unique_payload_object,
)
from web.tmdb_compose_generation import _write_detached_lines
from web.tmdb_ids import QueueItem


_SHA = re.compile(r"[a-f0-9]{64}")


@dataclass(frozen=True)
class ReviewedAdultDetail:
    """Operator attestation binding an exact private Details observation.

    The path and HTTP status are trusted operator attestations tied to the
    raw body digest, not independent authentication of TMDb or permission.
    """

    item: QueueItem
    change_version: int
    checkpoint_signature: str
    details_path: str
    status: int
    response_sha256: str


@dataclass(frozen=True)
class DetachedQuarantine:
    previous_sha256: str
    sha256: str
    rows: int
    review: ReviewedAdultDetail
    activation_status: str = "not_eligible_for_activation"


def _validate_review(review, evidence):
    if not isinstance(review, ReviewedAdultDetail):
        raise ValueError("An exact explicit adult review is required")
    key = _item_key(review.item)
    if (type(review.change_version) is not int or review.change_version <= 0
            or type(review.checkpoint_signature) is not str or _SHA.fullmatch(review.checkpoint_signature) is None
            or review.details_path != f"/3/{key[0]}/{key[1]}"
            or type(review.status) is not int or review.status != 200
            or type(review.response_sha256) is not str or _SHA.fullmatch(review.response_sha256) is None
            or type(evidence) is not bytes or not 1 <= len(evidence) <= MAX_COMPLETION_BYTES
            or sha256(evidence).hexdigest() != review.response_sha256):
        raise ValueError("Adult Detail review does not match exact evidence")
    try:
        response = json.loads(evidence.decode("utf-8"), object_pairs_hook=_unique_payload_object,
                              parse_constant=_reject_payload_constant)
        if (not isinstance(response, dict) or type(response.get("id")) is not int or response["id"] != key[1]
                or response.get("media_type", key[0]) != key[0] or response.get("adult") is not True
                or ("success" in response and response["success"] is not True)):
            raise ValueError
    except (ValueError, RecursionError):
        raise ValueError("Expected explicit adult:true on the exact typed Detail") from None
    return key


def seal_reviewed_adult_quarantine(
    *, previous: Path, previous_sha256: str, checkpoint: Path, output: Path,
    review: ReviewedAdultDetail, evidence: bytes, use_cleared: bool = False,
) -> DetachedQuarantine:
    """Copy a verified seed minus one typed key under a change-version fence.

    No live lookup, acknowledgement, durable deletion, active switch, rollback,
    or profile/collection access. A successful offline receipt intentionally
    cannot be consumed by the ordinary generation-activation helper. Keep
    custody of the exact provider response outside this API; it is not copied
    into the JSONL, SQLite, or exception text. Before any separate future use,
    a new authorization and freshness check would still be needed.
    """
    if use_cleared is not True:
        raise PermissionError("Explicit reviewed evidence and intended-use clearance are required")
    key = _validate_review(review, evidence)
    if type(previous_sha256) is not str or _SHA.fullmatch(previous_sha256) is None:
        raise ValueError("An exact prior seed SHA-256 is required")
    output = Path(output)
    if output.exists() or output.is_symlink():
        raise FileExistsError("Choose a new seed generation destination")
    snapshot, digest = load_seed_snapshot_with_digest(previous)
    if digest != previous_sha256:
        raise ValueError("Previous seed SHA-256 does not match")
    if review.item.key not in snapshot or len(snapshot) <= 1:
        raise ValueError("Quarantine must omit an existing typed row and leave a nonempty seed")
    def preserved_lines():
        # The verified loader preserves insertion order and reads one title
        # per line. Pin exactly these original descriptor bytes again before
        # publishing, preserving even unrecognized fields on other lines.
        observed = sha256()
        with Path(previous).open("rb") as stream:
            for key_for_line in snapshot:
                line = stream.readline(MAX_LINE_BYTES + 1)
                if not line or len(line) > MAX_LINE_BYTES:
                    raise ValueError("Previous seed changed before quarantine")
                observed.update(line)
                if key_for_line != review.item.key:
                    yield line
            if stream.read(1) or observed.hexdigest() != digest:
                raise ValueError("Previous seed changed before quarantine")

    @contextmanager
    def exact_change_fence():
        # Writer reservation covers verification and atomic link only, never
        # serialization. Existing DB only: no path creation, migration or write.
        with closing(sqlite3.connect(Path(checkpoint).resolve().as_uri() + "?mode=rw",
                                     uri=True, timeout=0)) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                if _table_names(connection) != _TABLES:
                    raise ValueError("Expected a versioned detached change checkpoint")
                pending = connection.execute(
                    "SELECT version FROM change_pending WHERE media=? AND tmdb_id=?", key,
                ).fetchone()
                watermark = connection.execute(
                    "SELECT signature FROM change_watermark WHERE singleton=1",
                ).fetchone()
                if pending != (review.change_version,) or watermark != (review.checkpoint_signature,):
                    raise ValueError("Missing or superseded typed adult review generation")
                yield
            finally:
                connection.rollback()

    sha = _write_detached_lines(output, preserved_lines(), publication_guard=exact_change_fence)
    return DetachedQuarantine(digest, sha, len(snapshot) - 1, review)

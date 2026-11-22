"""Operator-only passage matrix snapshot; independent of desktop profile caches."""
from dataclasses import dataclass
from hashlib import sha256
from itertools import islice
import json
import os
from pathlib import Path
import re
import struct
import tempfile

import numpy as np

from candidates.story_seed_snapshot import MAX_ROWS
from candidates.story_vector_cache import DIMENSION, PREPROCESS_VERSION

_MAGIC = b"WBSVEC01"
_HEADER = struct.Struct("<8s32sII32s")
_DTYPE = np.dtype("<f4")
_TYPED_KEY = re.compile(r"tmdb:(?:movie|tv):[1-9][0-9]*")
_SHA256 = re.compile(r"[a-f0-9]{64}")
_BLOCK_ROWS = 4096


@dataclass(frozen=True)
class SnapshotIdentity:
    catalog_sha256: str
    model_identity: str
    documents_sha256: str
    count: int
    preprocessing: str = PREPROCESS_VERSION

    def __post_init__(self):
        for digest in (self.catalog_sha256, self.documents_sha256):
            if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
                raise ValueError("expected a SHA-256 hex digest")
        if (type(self.count) is not int or not 1 <= self.count <= MAX_ROWS
                or not isinstance(self.model_identity, str) or not self.model_identity
                or not isinstance(self.preprocessing, str) or not self.preprocessing):
            raise ValueError("invalid passage snapshot identity")

    @classmethod
    def from_documents(cls, catalog_sha256, model_identity, documents, *, preprocessing=PREPROCESS_VERSION):
        digest, keys = sha256(), set()
        for doc in islice(documents, MAX_ROWS + 1):
            if not _TYPED_KEY.fullmatch(doc.key) or doc.key in keys:
                raise ValueError("passage snapshots need unique typed TMDb IDs")
            keys.add(doc.key)
            # Length framing makes separators in the overview unambiguous.
            for value in (doc.key, doc.overview):
                encoded = value.encode("utf-8")
                digest.update(struct.pack("<Q", len(encoded)))
                digest.update(encoded)
        return cls(catalog_sha256, model_identity, digest.hexdigest(), len(keys), preprocessing)

    def fingerprint(self):
        canonical = json.dumps((self.catalog_sha256, self.model_identity,
                                self.documents_sha256, self.count, self.preprocessing),
                               separators=(",", ":")).encode("ascii")
        return sha256(canonical).digest()


def _blocks(matrix):
    for first in range(0, len(matrix), _BLOCK_ROWS):
        yield matrix[first:first + _BLOCK_ROWS]


class PassageVectorSnapshot:
    """Explicit detached cache. Missing/corrupt generations are cache misses.

    Write a matching matrix with no concurrent caller mutation. Generations
    are content-addressed by identity; old files are not collected here.
    """

    def __init__(self, server_cache_directory):
        self.root = Path(server_cache_directory) / "server_passage_snapshots_v1"

    def _path(self, identity):
        return self.root / (identity.fingerprint().hex() + ".wbsvec")

    def load(self, identity):
        """Do not return a partial or mismatched matrix, even after interruption."""
        return self._read(identity)

    def load_with_digest(self, identity):
        """Audit the validated snapshot and its whole-file SHA-256 together."""
        return self._read(identity, with_digest=True)

    def _read(self, identity, *, with_digest=False):
        fingerprint = identity.fingerprint()
        size = _HEADER.size + identity.count * DIMENSION * _DTYPE.itemsize
        try:
            with self._path(identity).open("rb") as stream:
                if os.fstat(stream.fileno()).st_size != size:
                    return None
                header = stream.read(_HEADER.size)
                magic, actual, count, dimension, expected_digest = _HEADER.unpack(header)
                if (magic, actual, count, dimension) != (_MAGIC, fingerprint, identity.count, DIMENSION):
                    return None
                vector_bytes = stream.read(size - _HEADER.size + 1)
        except (OSError, struct.error):
            return None
        if len(vector_bytes) != size - _HEADER.size or sha256(vector_bytes).digest() != expected_digest:
            return None
        matrix = np.frombuffer(vector_bytes, dtype=_DTYPE).reshape(identity.count, DIMENSION)
        if not all(np.isfinite(block).all() for block in _blocks(matrix)):
            return None
        if with_digest:
            digest = sha256(header)
            digest.update(vector_bytes)
            return matrix, digest.hexdigest()
        return matrix

    def save(self, identity, matrix):
        """Flush a complete, checksummed temporary file, then replace atomically."""
        self._save(identity, matrix)

    def save_new(self, identity, matrix, *, before_publish):
        """Write atomically only if the target does not yet exist."""
        if not callable(before_publish):
            raise ValueError("expected an explicit pre-publication check")
        return self._save(identity, matrix, before_publish=before_publish)

    def _save(self, identity, matrix, *, before_publish=None):
        if (not isinstance(matrix, np.ndarray) or matrix.dtype.kind != "f" or matrix.dtype.itemsize != 4
                or matrix.shape != (identity.count, DIMENSION)):
            raise ValueError("expected a matching float32 passage matrix")
        target = self._path(identity)
        staging = self.root
        if before_publish is None:
            self.root.mkdir(parents=True, exist_ok=True)
        elif not self.root.exists():
            # Stage in the existing private parent. A failed recheck for a new
            # namespace must not leave an empty directory or a staged file.
            staging = self.root.parent
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=staging, prefix=".stage-", delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(b"\0" * _HEADER.size)
                digest = sha256()
                for block in _blocks(matrix):
                    chunk = np.ascontiguousarray(block, dtype=_DTYPE)
                    if not np.isfinite(chunk).all():
                        raise ValueError("passage matrix must be finite")
                    payload = chunk.tobytes()
                    stream.write(payload)
                    digest.update(payload)
                stream.seek(0)
                stream.write(_HEADER.pack(_MAGIC, identity.fingerprint(), identity.count,
                                          DIMENSION, digest.digest()))
                stream.flush()
                os.fsync(stream.fileno())
            if before_publish is None:
                os.replace(temporary, target)
            else:
                before_publish()
                self.root.mkdir(exist_ok=True)
                if self.root.is_symlink():
                    raise ValueError("invalid passage namespace")
                os.link(temporary, target)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

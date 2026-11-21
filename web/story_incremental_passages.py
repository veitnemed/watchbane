"""Offline copy-forward between exact, validated server passage generations."""
from dataclasses import dataclass
from hashlib import sha256
from itertools import islice

import numpy as np

from candidates.story_seed_snapshot import MAX_ROWS
from candidates.story_vector_cache import DIMENSION
from web.story_vector_snapshot import PassageVectorSnapshot, SnapshotIdentity

_ROW_BYTES = DIMENSION * np.dtype(np.float32).itemsize
_MAX_MATRIX_BYTES = MAX_ROWS * _ROW_BYTES


@dataclass(frozen=True)
class IncrementalPassages:
    matrix: np.ndarray
    reused_rows: int
    encoded_rows: int
    exact_hit: bool = False


def _validated_documents(identity, documents):
    expected = tuple(islice(documents, identity.count + 1))
    computed = SnapshotIdentity.from_documents(identity.catalog_sha256, identity.model_identity, expected,
                                               preprocessing=identity.preprocessing)
    if computed != identity:
        raise ValueError("document order or passages do not match the snapshot identity")
    return expected


def _passage_key(doc):
    return doc.key, sha256(doc.overview.encode("utf-8")).digest()


def reuse_verified_passages(
    cache: PassageVectorSnapshot, *,
    current_identity: SnapshotIdentity, current_documents,
    previous_identity: SnapshotIdentity, previous_documents,
    encode, max_matrix_bytes: int = _MAX_MATRIX_BYTES,
) -> IncrementalPassages:
    """Load verified prior rows, encode misses, atomically publish the result.

    Callers supply the exact catalog digests from the validated snapshot
    loaders and model identity from their verified encoder. The byte limit
    caps each raw matrix (not total cache-directory disk usage).
    """
    if type(max_matrix_bytes) is not int or not 1 <= max_matrix_bytes <= _MAX_MATRIX_BYTES:
        raise ValueError("invalid passage matrix byte cap")
    if current_identity.count * _ROW_BYTES > max_matrix_bytes:
        raise ValueError("current passage matrix exceeds byte cap")
    current = _validated_documents(current_identity, current_documents)
    previous = _validated_documents(previous_identity, previous_documents)
    exact = cache.load(current_identity)
    if exact is not None:
        return IncrementalPassages(exact, 0, 0, exact_hit=True)

    source = None
    if (previous_identity.model_identity == current_identity.model_identity
            and previous_identity.preprocessing == current_identity.preprocessing
            and previous_identity.count * _ROW_BYTES <= max_matrix_bytes
            and previous_identity != current_identity):
        source = cache.load(previous_identity)
    matrix = np.empty((len(current), DIMENSION), dtype=np.float32)
    positions = {_passage_key(doc): i for i, doc in enumerate(previous)} if source is not None else {}
    missing = []
    for i, doc in enumerate(current):
        row = positions.get(_passage_key(doc))
        if row is None:
            missing.append(i)
        else:
            matrix[i] = source[row]
    if missing:
        vectors = encode([current[i].overview for i in missing])
        if (not isinstance(vectors, np.ndarray) or vectors.dtype.kind != "f" or vectors.dtype.itemsize != 4
                or vectors.shape != (len(missing), DIMENSION) or not np.isfinite(vectors).all()):
            raise ValueError("encoder did not return a finite matching float32 matrix")
        matrix[missing] = vectors
    cache.save(current_identity, matrix)
    return IncrementalPassages(matrix, len(current) - len(missing), len(missing))

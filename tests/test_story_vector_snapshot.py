from dataclasses import replace
from hashlib import sha256
from pathlib import Path

import pytest

np = pytest.importorskip("numpy")

from candidates.story_search import StoryDocument
from candidates.story_vector_cache import DIMENSION
from web.story_vector_snapshot import PassageVectorSnapshot, SnapshotIdentity


def _fixture():
    documents = (
        StoryDocument("tmdb:tv:7", "Seven", "Описание сериала.", "tv", "fixture"),
        StoryDocument("tmdb:movie:7", "Seven", "Описание фильма.", "movie", "fixture"),
    )
    digest = sha256(b"approved synthetic fixture").hexdigest()
    identity = SnapshotIdentity.from_documents(digest, "pinned-test-model", documents)
    return identity, documents, np.arange(2 * DIMENSION, dtype=np.float32).reshape(2, DIMENSION)


def test_restart_uses_matrix_only_for_same_ordered_input_and_version(tmp_path):
    identity, documents, matrix = _fixture()
    cache = PassageVectorSnapshot(tmp_path)
    assert cache.load(identity) is None
    cache.save(identity, matrix)
    reopened = PassageVectorSnapshot(tmp_path)
    loaded = reopened.load(identity)
    assert loaded.dtype == np.float32 and not loaded.flags.writeable
    np.testing.assert_array_equal(loaded, matrix)
    changes = [
        replace(identity, catalog_sha256=sha256(b"same docs but new file").hexdigest()),
        replace(identity, model_identity="other-pinned-model"),
        replace(identity, preprocessing="next-pooling-version"),
        SnapshotIdentity.from_documents(identity.catalog_sha256, identity.model_identity, reversed(documents)),
        SnapshotIdentity.from_documents(identity.catalog_sha256, identity.model_identity,
                                       (documents[0], replace(documents[1], overview="Новая версия текста."))),
    ]
    assert all(reopened.load(altered) is None for altered in changes)
    serialized = next(tmp_path.rglob("*.wbsvec")).read_bytes()
    assert documents[0].overview.encode() not in serialized and documents[0].key.encode() not in serialized


def test_interruption_before_swap_preserves_old_generation(tmp_path, monkeypatch):
    import web.story_vector_snapshot as snapshots

    identity, _, matrix = _fixture()
    cache = PassageVectorSnapshot(tmp_path)
    cache.save(identity, matrix)

    def interrupted(stage, target):
        assert Path(stage).is_file() and Path(target).is_file()
        np.testing.assert_array_equal(PassageVectorSnapshot(tmp_path).load(identity), matrix)
        raise KeyboardInterrupt

    monkeypatch.setattr(snapshots.os, "replace", interrupted)
    with pytest.raises(KeyboardInterrupt):
        cache.save(identity, matrix + 1)
    assert not list(cache.root.glob(".stage-*"))
    np.testing.assert_array_equal(PassageVectorSnapshot(tmp_path).load(identity), matrix)


def test_truncated_corrupt_or_moved_generation_is_never_loaded(tmp_path):
    identity, _, matrix = _fixture()
    cache = PassageVectorSnapshot(tmp_path)
    cache.save(identity, matrix)
    path = next(tmp_path.rglob("*.wbsvec"))
    original = path.read_bytes()
    for bad in (original[:-1], original + b"x", original[:-1] + bytes((original[-1] ^ 1,))):
        path.write_bytes(bad)
        assert cache.load(identity) is None
    other = replace(identity, model_identity="new-model")
    cache.save(other, matrix)
    other_path = next(p for p in cache.root.glob("*.wbsvec") if p != path)
    other_path.write_bytes(original)
    assert cache.load(other) is None


def test_invalid_matrix_cannot_poison_existing_snapshot(tmp_path):
    identity, docs, matrix = _fixture()
    cache = PassageVectorSnapshot(tmp_path)
    cache.save(identity, matrix)
    with pytest.raises(ValueError, match="unique typed"):
        SnapshotIdentity.from_documents(identity.catalog_sha256, identity.model_identity, [docs[0], docs[0]])
    invalid = matrix.copy()
    invalid[-1, -1] = np.inf
    for bad in (matrix[:1], matrix.astype(np.float64), invalid):
        with pytest.raises(ValueError):
            cache.save(identity, bad)
    np.testing.assert_array_equal(cache.load(identity), matrix)
    assert not list(cache.root.glob(".stage-*"))


def test_checksum_consistent_nan_snapshot_is_also_a_miss(tmp_path):
    import web.story_vector_snapshot as snapshots

    identity, _, matrix = _fixture()
    cache = PassageVectorSnapshot(tmp_path)
    cache.save(identity, matrix)
    path = next(cache.root.glob("*.wbsvec"))
    header = path.read_bytes()[:snapshots._HEADER.size]
    magic, fingerprint, count, dimension, _ = snapshots._HEADER.unpack(header)
    matrix[0, 0] = np.nan
    payload = matrix.astype("<f4").tobytes()
    path.write_bytes(snapshots._HEADER.pack(magic, fingerprint, count, dimension, sha256(payload).digest())
                     + payload)
    assert cache.load(identity) is None

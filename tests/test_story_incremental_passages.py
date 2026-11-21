from dataclasses import replace
from hashlib import sha256

import pytest

np = pytest.importorskip("numpy")

from candidates.story_search import StoryDocument
from candidates.story_vector_cache import DIMENSION
from web.story_incremental_passages import reuse_verified_passages
from web.story_vector_snapshot import PassageVectorSnapshot, SnapshotIdentity


def _doc(key, overview):
    return StoryDocument(key, "Title", overview, key.split(":")[1], "fixture")


def _identity(generation, docs):
    return SnapshotIdentity.from_documents(sha256(generation.encode()).hexdigest(), "verified fixture model", docs)


def _encode(texts):
    return np.stack([np.full(DIMENSION, float(sum(text.encode())), dtype=np.float32) for text in texts])


@pytest.fixture
def generations(tmp_path):
    previous = (_doc("tmdb:tv:13", "Shared"), _doc("tmdb:movie:13", "Changed"),
                _doc("tmdb:movie:90", "Removed"))
    current = (_doc("tmdb:tv:90", "Removed"), replace(previous[1], overview="Replacement"),
               replace(previous[0], title="Title-only change"))
    old_id, new_id = _identity("previous", previous), _identity("current", current)
    cache = PassageVectorSnapshot(tmp_path)
    original = _encode([doc.overview for doc in previous])
    cache.save(old_id, original)
    return cache, old_id, previous, new_id, current, original


def _reuse(generations, encode, **options):
    cache, old_id, previous, new_id, current, _ = generations
    kwargs = dict(previous_identity=old_id, previous_documents=previous, current_identity=new_id,
                  current_documents=current, encode=encode)
    return reuse_verified_passages(cache, **(kwargs | options))


def test_changed_new_and_removed_typed_ids_are_not_reused(generations):
    cache, old_id, _, new_id, current, original = generations
    seen = []
    def record(texts):
        seen.extend(texts)
        return _encode(texts)
    result = _reuse(generations, record)
    assert seen == ["Removed", "Replacement"]  # Same numeric ID and text, different media type.
    assert (result.reused_rows, result.encoded_rows, result.exact_hit) == (1, 2, False)
    np.testing.assert_array_equal(result.matrix, _encode([doc.overview for doc in current]))
    np.testing.assert_array_equal(cache.load(new_id), result.matrix)
    np.testing.assert_array_equal(cache.load(old_id), original)
    exact = _reuse(generations, lambda _: pytest.fail("unexpected re-encoding"))
    assert exact.exact_hit


@pytest.mark.parametrize("scenario", ["model", "preprocessing", "catalog", "corrupt"])
def test_mismatching_or_corrupt_previous_snapshot_encodes_all(generations, scenario):
    cache, old_id, _, new_id, current, _ = generations
    options = {}
    if scenario == "model":
        options["current_identity"] = replace(new_id, model_identity="different pinned model")
    elif scenario == "preprocessing":
        options["current_identity"] = replace(new_id, preprocessing="different prefix")
    elif scenario == "catalog":
        options["previous_identity"] = replace(old_id, catalog_sha256="1" * 64)
    else:
        cache._path(old_id).write_bytes(b"corrupt")
    calls = []
    def encode(texts):
        calls.extend(texts)
        return _encode(texts)
    result = _reuse(generations, encode, **options)
    assert calls == [doc.overview for doc in current]
    assert result.reused_rows == 0 and result.encoded_rows == len(current)


@pytest.mark.parametrize("failure", ["raise", "nonfinite", "shape", "publish"])
def test_failure_preserves_verified_previous_generation(generations, failure, monkeypatch):
    import web.story_vector_snapshot as snapshots

    cache, old_id, _, new_id, _, original = generations
    old_bytes = cache._path(old_id).read_bytes()

    def inject(*_args):
        raise OSError("disposable injected failure")

    def encode(texts):
        if failure == "raise":
            inject()
        vectors = _encode(texts)
        if failure == "nonfinite":
            vectors[0, 0] = np.nan
        if failure == "shape":
            vectors = vectors[:-1]
        return vectors

    if failure == "publish":
        monkeypatch.setattr(snapshots.os, "replace", inject)
    with pytest.raises((OSError, ValueError)):
        _reuse(generations, encode)
    assert cache.load(new_id) is None and not list(cache.root.glob(".stage-*"))
    assert cache._path(old_id).read_bytes() == old_bytes
    np.testing.assert_array_equal(cache.load(old_id), original)


def test_invalid_documents_or_small_budget_fail_before_encoder(generations):
    _, _, previous, _, current, _ = generations
    for options in ({"current_documents": current[::-1]}, {"previous_documents": previous[:-1]},
                    {"max_matrix_bytes": 3 * DIMENSION * 4 - 1}, {"max_matrix_bytes": True}):
        with pytest.raises(ValueError):
            _reuse(generations, lambda _: pytest.fail("unexpected encoder"), **options)

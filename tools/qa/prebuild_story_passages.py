"""Prebuild a detached, local Watchbane passage snapshot from an approved, pinned catalog."""
import argparse
import json
import os
from pathlib import Path
import re
import stat
import sys
import time

from candidates.story_semantic import DEFAULT_E5_BATCH_SIZE


def private_directory(directory):
    directory = Path(directory).expanduser()
    if directory.is_symlink():
        raise ValueError("expected a private cache directory, not a symlink")
    directory = directory.resolve(strict=True)
    info = directory.stat()
    # The operator tool has no ACL inspection on Windows; avoid claiming
    # owner-only cache publication where the check cannot be made.
    if (os.name != "posix" or not stat.S_ISDIR(info.st_mode)
            or info.st_uid != os.geteuid() or info.st_mode & 0o077):
        raise ValueError("expected an existing owner-private POSIX cache directory")
    return directory


def regular_target(cache, identity):
    if cache.root.is_symlink() or (cache.root.exists() and not cache.root.is_dir()):
        raise ValueError("invalid passage namespace")
    try:
        info = cache._path(identity).lstat()
    except FileNotFoundError:
        return False
    if not stat.S_ISREG(info.st_mode):
        raise ValueError("invalid passage snapshot file")
    return True


def _sha(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


class _PinnedReuse:
    """Adapt the shared planner to a read-only verified source and no-clobber destination."""

    def __init__(self, prior_identity, prior_matrix, destination, current_identity, before_publish):
        self.prior_identity, self.prior_matrix = prior_identity, prior_matrix
        self.destination, self.current_identity = destination, current_identity
        self.before_publish = before_publish

    def load(self, identity):
        if identity == self.prior_identity:
            return self.prior_matrix
        if identity != self.current_identity:
            raise ValueError("Unexpected incremental cache identity.")
        # We checked the destination before planning; any racing destination
        # fails the no-clobber link instead of being accepted or replaced.
        return None

    def save(self, identity, matrix):
        if identity != self.current_identity:
            raise ValueError("Refusing to write a prior cache identity.")
        self.destination.save_new(identity, matrix, before_publish=self.before_publish)


def prebuild(catalog, pinned_digest, model_dir, cache_dir, *, batch_size=DEFAULT_E5_BATCH_SIZE,
             previous_catalog=None, previous_catalog_sha256=None, previous_cache_dir=None,
             previous_snapshot_sha256=None):
    """No route, no model fetch, and no replacement of an existing generation."""
    from candidates.story_semantic import LocalE5, validate_e5_batch_size
    from web.story_api import _StartupPassageEncoder, _load_documents, _startup_passage_identity
    from web.story_vector_snapshot import PassageVectorSnapshot

    if not _sha(pinned_digest):
        raise ValueError("expected a lowercase catalog SHA-256")
    prior_fields = (previous_catalog, previous_catalog_sha256, previous_cache_dir, previous_snapshot_sha256)
    reuse = any(field is not None for field in prior_fields)
    if reuse and (any(field is None for field in prior_fields) or not _sha(previous_catalog_sha256)
                  or not _sha(previous_snapshot_sha256) or previous_catalog_sha256 == pinned_digest):
        raise ValueError("reuse requires separately pinned prior catalog and cache, with distinct catalog bytes")
    validate_e5_batch_size(batch_size)
    cache = PassageVectorSnapshot(private_directory(cache_dir))
    started = time.monotonic()

    def catalog_for_pin(path, pin):
        documents, digest = _load_documents(path)
        if digest != pin or not documents:
            raise ValueError("catalog pin mismatch or no eligible Russian descriptions")
        return documents

    def current_catalog():
        return catalog_for_pin(catalog, pinned_digest)

    documents = current_catalog()
    if reuse:
        prior_cache = PassageVectorSnapshot(private_directory(previous_cache_dir))
        prior_documents = catalog_for_pin(previous_catalog, previous_catalog_sha256)
    model_dir = Path(model_dir)
    if not (model_dir / "onnx/model.onnx").is_file():
        raise ValueError("existing verified local FP32 model is required")
    encoder = LocalE5(model_dir)
    if encoder.variant != "fp32":
        raise ValueError("existing verified local FP32 model is required")
    identity = _startup_passage_identity(pinned_digest, encoder, documents, batch_size)

    if reuse:
        prior_identity = _startup_passage_identity(previous_catalog_sha256, encoder, prior_documents, batch_size)

        def prior_snapshot():
            catalog_for_pin(previous_catalog, previous_catalog_sha256)
            if not regular_target(prior_cache, prior_identity):
                raise ValueError("pinned previous snapshot is missing or has incompatible identity")
            verified = prior_cache.load_with_digest(prior_identity)
            if verified is None or verified[1] != previous_snapshot_sha256:
                raise ValueError("previous snapshot invalid or SHA-256 mismatch")
            return verified[0]

        prior_matrix = prior_snapshot()

        def before_publish():
            current_catalog()
            prior_snapshot()
    else:
        before_publish = current_catalog

    current_catalog()  # Detect replacement during model verification.
    counts = {}
    if not regular_target(cache, identity):
        if reuse:
            from web.story_incremental_passages import reuse_verified_passages

            result = reuse_verified_passages(
                _PinnedReuse(prior_identity, prior_matrix, cache, identity, before_publish),
                current_identity=identity, current_documents=documents,
                previous_identity=prior_identity, previous_documents=prior_documents,
                encode=lambda texts: encoder.encode(texts, batch_size=batch_size))
            counts = {"reused_rows": result.reused_rows, "encoded_rows": result.encoded_rows, "existing_rows": 0}
        else:
            matrix = _StartupPassageEncoder(encoder, None, None, documents,
                                            startup_batch_size=batch_size).encode([doc.overview for doc in documents])
            # Read the pin after expensive encoding and after the fully
            # written temporary snapshot, just before the atomic link.
            cache.save_new(identity, matrix, before_publish=before_publish)
    elif reuse:
        counts = {"reused_rows": 0, "encoded_rows": 0, "existing_rows": identity.count}
    if not regular_target(cache, identity):
        raise ValueError("missing cache snapshot")
    verified = cache.load_with_digest(identity)
    if verified is None:
        raise ValueError("corrupt cache snapshot; not replaced")
    current_catalog()
    return {"catalog_sha256": pinned_digest, "snapshot_sha256": verified[1],
            "rows": identity.count, "seconds": round(time.monotonic() - started, 3), **counts}


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__, epilog="Requires a local POSIX filesystem with hard-link publication; never replaces a snapshot.")
    parser.add_argument("--catalog", required=True, type=Path)
    parser.add_argument("--catalog-sha256", required=True)
    parser.add_argument("--model-dir", required=True, type=Path)
    parser.add_argument("--cache-dir", required=True, type=Path,
                        help="Existing, owner-private POSIX directory; use its path for server --cache-dir")
    parser.add_argument("--startup-passage-batch-size", type=int, default=DEFAULT_E5_BATCH_SIZE,
                        help="Use the exact same startup passage batch size as the later server")
    parser.add_argument("--previous-catalog", type=Path, help="Optional approved prior snapshot for detached reuse")
    parser.add_argument("--previous-catalog-sha256")
    parser.add_argument("--previous-cache-dir", type=Path, help="Existing private cache; the prior snapshot is never modified")
    parser.add_argument("--previous-snapshot-sha256", help="SHA-256 of the prior complete prebuilt snapshot")
    args = parser.parse_args(argv)
    try:
        report = prebuild(args.catalog, args.catalog_sha256, args.model_dir, args.cache_dir,
                          batch_size=args.startup_passage_batch_size, previous_catalog=args.previous_catalog,
                          previous_catalog_sha256=args.previous_catalog_sha256,
                          previous_cache_dir=args.previous_cache_dir,
                          previous_snapshot_sha256=args.previous_snapshot_sha256)
    except (OSError, ValueError, RuntimeError):
        print("Passage prebuild refused: verify the catalog pin, model, private directory and cache integrity.",
              file=sys.stderr)
        return 1
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

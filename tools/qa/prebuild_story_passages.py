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


def prebuild(catalog, pinned_digest, model_dir, cache_dir, *, batch_size=DEFAULT_E5_BATCH_SIZE):
    """No route, no model fetch, and no replacement of an existing generation."""
    from candidates.story_semantic import LocalE5, validate_e5_batch_size
    from web.story_api import _StartupPassageEncoder, _load_documents, _startup_passage_identity
    from web.story_vector_snapshot import PassageVectorSnapshot

    if not isinstance(pinned_digest, str) or not re.fullmatch(r"[0-9a-f]{64}", pinned_digest):
        raise ValueError("expected a lowercase catalog SHA-256")
    validate_e5_batch_size(batch_size)
    cache = PassageVectorSnapshot(private_directory(cache_dir))
    started = time.monotonic()

    def current_catalog():
        documents, digest = _load_documents(catalog)
        if digest != pinned_digest or not documents:
            raise ValueError("catalog pin mismatch or no eligible Russian descriptions")
        return documents

    documents = current_catalog()
    model_dir = Path(model_dir)
    if not (model_dir / "onnx/model.onnx").is_file():
        raise ValueError("existing verified local FP32 model is required")
    encoder = LocalE5(model_dir)
    if encoder.variant != "fp32":
        raise ValueError("existing verified local FP32 model is required")
    identity = _startup_passage_identity(pinned_digest, encoder, documents, batch_size)

    current_catalog()  # Detect replacement during model verification.
    if not regular_target(cache, identity):
        matrix = _StartupPassageEncoder(encoder, None, None, documents,
                                        startup_batch_size=batch_size).encode([doc.overview for doc in documents])
        # Reads the pin after expensive encoding and after the fully written
        # temporary snapshot, just before the atomic content-addressed link.
        # A future catalog with other bytes cannot match this identity.
        cache.save_new(identity, matrix, before_publish=current_catalog)
    if not regular_target(cache, identity):
        raise ValueError("missing cache snapshot")
    verified = cache.load_with_digest(identity)
    if verified is None:
        raise ValueError("corrupt cache snapshot; not replaced")
    current_catalog()
    return {"catalog_sha256": pinned_digest, "snapshot_sha256": verified[1],
            "rows": identity.count, "seconds": round(time.monotonic() - started, 3)}


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
    args = parser.parse_args(argv)
    try:
        report = prebuild(args.catalog, args.catalog_sha256, args.model_dir, args.cache_dir,
                          batch_size=args.startup_passage_batch_size)
    except (OSError, ValueError, RuntimeError):
        print("Passage prebuild refused: verify the catalog pin, model, private directory and cache integrity.",
              file=sys.stderr)
        return 1
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

import json
import os
from hashlib import sha256
from pathlib import Path
import socket

import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("fastapi")

from tools.qa.prebuild_story_passages import main, prebuild
from web import story_api
from web.story_vector_snapshot import PassageVectorSnapshot

pytestmark = pytest.mark.skipif(os.name != "posix", reason="operator-only POSIX directory checks")


def write_catalog(path, text, identifier=1):
    path.write_text(json.dumps({"media_type": "movie", "tmdb_id": identifier, "title": "Сюжет",
                                "overview": text, "language": "ru-RU"}) + "\n")
    return sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def inputs(tmp_path, monkeypatch):
    model = tmp_path / "model"
    (model / "onnx").mkdir(parents=True)
    (model / "onnx/model.onnx").write_bytes(b"fake; production verifies a pinned manifest")
    cache = tmp_path / "cache"
    cache.mkdir(mode=0o700)
    catalog = tmp_path / "catalog.jsonl"
    digest = write_catalog(catalog, "Альпинист возвращается домой.")
    calls = []

    class Encoder:
        variant, cache_identity = "fp32", "verified fixture runtime"
        def __init__(self, path):
            assert path == model
            calls.append("verified-model")
        def encode(self, texts, prefix="passage: ", *, batch_size=16, **kwargs):
            calls.append((prefix, tuple(texts), batch_size))
            return np.ones((len(texts), 384), dtype=np.float32)

    # Local import for isolated fake model only; web.story_api's shared
    # identity/eligibility/batch implementation remains real.
    monkeypatch.setattr("candidates.story_semantic.LocalE5", Encoder)
    monkeypatch.setattr(story_api, "LocalE5", Encoder)
    return catalog, digest, model, cache, calls


def test_passage_artifact_reused_by_exact_server_identity_without_sockets(inputs, monkeypatch):
    catalog, digest, model, cache, calls = inputs
    def socket_forbidden(*_args, **_kwargs):
        raise AssertionError("detached build attempted a network action")
    with monkeypatch.context() as patch:
        for method in ("bind", "listen", "connect", "connect_ex"):
            patch.setattr(socket.socket, method, socket_forbidden)
        report = prebuild(catalog, digest, model, cache, batch_size=4)
    assert report.keys() == {"catalog_sha256", "snapshot_sha256", "rows", "seconds"}
    assert report["rows"] == 1 and report["catalog_sha256"] == digest
    artifact, = (cache / "server_passage_snapshots_v1").iterdir()
    assert report["snapshot_sha256"] == sha256(artifact.read_bytes()).hexdigest()
    assert calls == ["verified-model", ("passage: ", ("Альпинист возвращается домой.",), 4)]

    original = artifact.stat()
    story_api.build_engine(catalog, model, cache_dir=cache, startup_batch_size=4)
    assert calls[-1] == "verified-model" and len(calls) == 3
    assert prebuild(catalog, digest, model, cache, batch_size=4)["snapshot_sha256"] == report["snapshot_sha256"]
    assert calls[-1] == "verified-model" and len(calls) == 4
    assert original.st_ino == artifact.stat().st_ino and original.st_mtime_ns == artifact.stat().st_mtime_ns


def test_stale_pin_fails_before_model_and_leaves_no_cache(inputs, capsys):
    catalog, digest, model, cache, calls = inputs
    write_catalog(catalog, "Капитан ищет берег.")
    assert main(["--catalog", str(catalog), "--catalog-sha256", digest, "--model-dir", str(model),
                 "--cache-dir", str(cache)]) == 1
    output = capsys.readouterr()
    assert not output.out and str(catalog) not in output.err and "Капитан" not in output.err
    assert not calls and list(cache.iterdir()) == []


def test_late_pin_replacement_refuses_and_keeps_unrelated_generation(inputs, monkeypatch):
    catalog, digest, model, cache, _ = inputs
    first = prebuild(catalog, digest, model, cache)
    namespace = cache / "server_passage_snapshots_v1"
    original, = namespace.iterdir()
    before = original.read_bytes()
    digest = write_catalog(catalog, "Капитан ищет берег.", identifier=2)
    real_publish = PassageVectorSnapshot.save_new
    def interleave(self, identity, matrix, *, before_publish):
        def change():
            write_catalog(catalog, "Садовник ждёт поезд.", identifier=3)
            before_publish()
        return real_publish(self, identity, matrix, before_publish=change)

    monkeypatch.setattr(PassageVectorSnapshot, "save_new", interleave)
    with pytest.raises(ValueError, match="pin mismatch"):
        prebuild(catalog, digest, model, cache)
    assert list(namespace.iterdir()) == [original]
    assert original.read_bytes() == before and first["snapshot_sha256"] == sha256(before).hexdigest()


def test_existing_corruption_and_racing_target_are_never_replaced(inputs, monkeypatch):
    catalog, digest, model, cache, calls = inputs
    prebuild(catalog, digest, model, cache)
    namespace = cache / "server_passage_snapshots_v1"
    old, = namespace.iterdir()
    old.write_bytes(b"corrupt")
    calls.clear()
    with pytest.raises(ValueError, match="corrupt"):
        prebuild(catalog, digest, model, cache)
    assert calls == ["verified-model"] and old.read_bytes() == b"corrupt"
    old.unlink()

    real_link = os.link
    def raced_link(src, dst):
        Path(dst).write_bytes(b"other writer")
        real_link(src, dst)
    monkeypatch.setattr(os, "link", raced_link)
    with pytest.raises(FileExistsError):
        prebuild(catalog, digest, model, cache)
    assert list(namespace.iterdir()) == [old]
    assert old.read_bytes() == b"other writer"


def test_cache_permissions_and_symlink_refuse_before_model(inputs):
    catalog, digest, model, cache, calls = inputs
    cache.chmod(0o755)
    with pytest.raises(ValueError, match="owner-private"):
        prebuild(catalog, digest, model, cache)
    cache.chmod(0o700)
    (cache / "server_passage_snapshots_v1").symlink_to(catalog)
    with pytest.raises(ValueError, match="namespace"):
        prebuild(catalog, digest, model, cache)
    assert not list(cache.glob("*.wbsvec"))


def test_final_pin_check_leaves_new_cache_directory_empty(inputs, monkeypatch):
    catalog, digest, model, cache, _ = inputs
    real_publish = PassageVectorSnapshot.save_new
    def change_while_staged(self, identity, matrix, *, before_publish):
        def change():
            write_catalog(catalog, "Садовник ждёт поезд.")
            before_publish()
        return real_publish(self, identity, matrix, before_publish=change)
    monkeypatch.setattr(PassageVectorSnapshot, "save_new", change_while_staged)
    with pytest.raises(ValueError, match="pin mismatch"):
        prebuild(catalog, digest, model, cache)
    assert not list(cache.iterdir())

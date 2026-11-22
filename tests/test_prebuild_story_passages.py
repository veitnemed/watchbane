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


def reuse_inputs(inputs, tmp_path):
    catalog, digest, model, incremental, calls = inputs
    prior_cache = tmp_path / "prior_cache"
    prior_cache.mkdir(mode=0o700)
    previous = tmp_path / "previous.jsonl"
    previous.write_bytes(catalog.read_bytes())
    prior_report = prebuild(previous, digest, model, prior_cache, batch_size=4)
    prior_artifact, = (prior_cache / "server_passage_snapshots_v1").iterdir()
    added = {"media_type": "tv", "tmdb_id": 1, "title": "Другой тайтл",
             "overview": "Мастер находит архив.", "language": "ru-RU"}
    catalog.write_bytes(catalog.read_bytes() + (json.dumps(added) + "\n").encode())
    current_digest = sha256(catalog.read_bytes()).hexdigest()
    options = {"previous_catalog": previous, "previous_catalog_sha256": digest,
               "previous_cache_dir": prior_cache, "previous_snapshot_sha256": prior_report["snapshot_sha256"]}
    calls.clear()
    return (catalog, current_digest, model, incremental), options, prior_artifact, calls


def test_incremental_detached_reuses_typed_rows_and_never_changes_previous(inputs, tmp_path, monkeypatch):
    args, options, prior, calls = reuse_inputs(inputs, tmp_path)
    before = prior.read_bytes(), prior.stat().st_ino, prior.stat().st_mtime_ns
    def forbidden(*_args, **_kwargs):
        raise AssertionError("detached incremental build attempted a network action")
    with monkeypatch.context() as patch:
        for method in ("bind", "listen", "connect", "connect_ex"):
            patch.setattr(socket.socket, method, forbidden)
        result = prebuild(*args, **options, batch_size=4)
    assert (result["rows"], result["reused_rows"], result["encoded_rows"], result["existing_rows"]) == (2, 1, 1, 0)
    assert calls == ["verified-model", ("passage: ", ("Мастер находит архив.",), 4)]
    assert before == (prior.read_bytes(), prior.stat().st_ino, prior.stat().st_mtime_ns)
    again = prebuild(*args, **options, batch_size=4)
    assert (again["reused_rows"], again["encoded_rows"], again["existing_rows"]) == (0, 0, 2)
    assert again["snapshot_sha256"] == result["snapshot_sha256"] and len(calls) == 3


@pytest.mark.parametrize("case", ["partial", "wrong_catalog", "wrong_snapshot", "corrupt", "missing", "wrong_batch"])
def test_incremental_prior_refusals_never_fallback_or_write(inputs, tmp_path, case):
    args, options, prior, calls = reuse_inputs(inputs, tmp_path)
    batch = 4
    if case == "partial":
        del options["previous_cache_dir"]
    elif case == "wrong_catalog":
        options["previous_catalog_sha256"] = "f" * 64
    elif case == "wrong_snapshot":
        options["previous_snapshot_sha256"] = "f" * 64
    elif case == "corrupt":
        prior.write_bytes(b"corrupt")
    elif case == "missing":
        prior.unlink()
    elif case == "wrong_batch":
        batch = 8
    expected = prior.read_bytes() if prior.is_file() else None
    with pytest.raises(ValueError, match="reuse requires|catalog pin|previous snapshot"):
        prebuild(*args, **options, batch_size=batch)
    assert not list(args[3].iterdir()) and all(isinstance(call, str) for call in calls)
    assert expected == (prior.read_bytes() if prior.is_file() else None)


def test_altered_prior_at_final_atomic_link_refuses_entire_generation(inputs, tmp_path, monkeypatch):
    args, options, prior, calls = reuse_inputs(inputs, tmp_path)
    real_publish = PassageVectorSnapshot.save_new

    def new_target(self, identity, matrix, *, before_publish):
        def alter_prior():
            prior.write_bytes(b"interleaved prior corruption")
            before_publish()
        return real_publish(self, identity, matrix, before_publish=alter_prior)

    monkeypatch.setattr(PassageVectorSnapshot, "save_new", new_target)
    with pytest.raises(ValueError, match="previous snapshot invalid"):
        prebuild(*args, **options, batch_size=4)
    assert calls[-1] == ("passage: ", ("Мастер находит архив.",), 4)
    assert prior.read_bytes() == b"interleaved prior corruption"
    assert not list(args[3].iterdir())


def test_incremental_metadata_only_change_reuses_exact_passage(inputs, tmp_path):
    args, options, _, calls = reuse_inputs(inputs, tmp_path)
    catalog, _, model, destination = args
    row = json.loads(options["previous_catalog"].read_bytes())
    row["title"] = "Новый перевод заголовка"
    catalog.write_bytes((json.dumps(row) + "\n").encode())
    pin = sha256(catalog.read_bytes()).hexdigest()
    result = prebuild(catalog, pin, model, destination, **options, batch_size=4)
    assert (result["reused_rows"], result["encoded_rows"]) == (1, 0)
    assert calls == ["verified-model"]


def test_invalid_prior_is_not_ignored_on_an_existing_target(inputs, tmp_path):
    args, options, _, calls = reuse_inputs(inputs, tmp_path)
    first = prebuild(*args, batch_size=4, **options)
    artifact, = (args[3] / "server_passage_snapshots_v1").iterdir()
    options["previous_snapshot_sha256"] = "3" * 64
    with pytest.raises(ValueError, match="previous snapshot"):
        prebuild(*args, batch_size=4, **options)
    assert sha256(artifact.read_bytes()).hexdigest() == first["snapshot_sha256"]
    assert calls[-1] == "verified-model"

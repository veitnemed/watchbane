"""Local strict cache startup is fail-closed and does not write or re-encode."""
from hashlib import sha256
import json
import os

import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient

from tools.qa.prebuild_story_passages import prebuild
from web import story_api


@pytest.fixture
def prebuilt(tmp_path, monkeypatch):
    model = tmp_path / "model"
    (model / "onnx").mkdir(parents=True)
    (model / "onnx/model.onnx").write_bytes(b"fixture only")
    cache = tmp_path / "cache"
    cache.mkdir(mode=0o700)
    catalog = tmp_path / "catalog.jsonl"
    payload = {"tmdb_id": 19, "media_type": "movie", "title": "Мастер", "language": "ru-RU",
               "overview": "Мастер ищет архив."}
    catalog.write_bytes(json.dumps(payload, ensure_ascii=False).encode() + b"\n")
    pin = sha256(catalog.read_bytes()).hexdigest()
    calls = []

    class FP32Fixture:
        variant = "fp32"
        cache_identity = "pinned fp32 CI fixture"

        def __init__(self, _directory):
            calls.append("verify")

        def encode(self, texts, prefix="passage: ", **_options):
            calls.append(prefix)
            return np.ones((len(texts), 384), dtype=np.float32)

    monkeypatch.setattr(story_api, "LocalE5", FP32Fixture)
    monkeypatch.setattr("candidates.story_semantic.LocalE5", FP32Fixture)
    report = prebuild(catalog, pin, model, cache, batch_size=4)
    artifact, = list((cache / "server_passage_snapshots_v1").iterdir())
    options = {"cache_dir": cache, "prepared_index": True, "startup_batch_size": 4,
               "expected_catalog_sha256": pin, "expected_snapshot_sha256": report["snapshot_sha256"]}
    calls.clear()
    return catalog, model, options, artifact, calls


pytestmark = pytest.mark.skipif(os.name != "posix", reason="tests prepare private POSIX cache artifacts")


def test_strict_ready_uses_snapshot_only_and_preserves_bytes(prebuilt, monkeypatch):
    catalog, model, options, artifact, calls = prebuilt
    expected = artifact.read_bytes(), artifact.stat().st_ino, artifact.stat().st_mtime_ns
    from web.story_vector_snapshot import PassageVectorSnapshot
    no_write = lambda *_args, **_kwargs: pytest.fail("strict startup attempted a write")
    monkeypatch.setattr(PassageVectorSnapshot, "save", no_write)
    monkeypatch.setattr(PassageVectorSnapshot, "save_new", no_write)

    with TestClient(story_api.create_app(catalog, model, **options)) as client:
        assert calls == ["verify"]
        assert client.get("/healthz").json() == {"ready": True}
        result = client.post("/v1/search", json={"query": "мастер ищет архив", "limit": 5})
        assert result.status_code == 200
        assert result.json()["results"][0]["id"] == "tmdb:movie:19"
    assert expected == (artifact.read_bytes(), artifact.stat().st_ino, artifact.stat().st_mtime_ns)


@pytest.mark.parametrize("case", ["wrong_catalog", "wrong_snapshot", "missing", "bad_bytes", "wrong_batch",
                                  "nonregular", "symlink"])
def test_strict_refusals_neither_encode_nor_modify_cache(prebuilt, case, tmp_path):
    catalog, model, options, artifact, calls = prebuilt
    if case == "wrong_catalog":
        options["expected_catalog_sha256"] = "1" * 64
    elif case == "wrong_snapshot":
        options["expected_snapshot_sha256"] = "2" * 64
    elif case == "missing":
        artifact.unlink()
    elif case == "bad_bytes":
        data = bytearray(artifact.read_bytes()); data[-1] ^= 1
        artifact.write_bytes(data)
    elif case == "wrong_batch":
        options["startup_batch_size"] = 16
    elif case in {"nonregular", "symlink"}:
        artifact.unlink()
        if case == "nonregular":
            os.mkfifo(artifact)
        else:
            valid = tmp_path / "other-copy"
            valid.write_bytes(b"private")
            artifact.symlink_to(valid)
    before = [(path.name, path.lstat().st_mtime_ns, path.lstat().st_ino,
               path.read_bytes() if path.is_file() and not path.is_symlink() else None)
              for path in artifact.parent.iterdir()]
    with pytest.raises(ValueError, match="Catalog SHA-256 mismatch|Required passage snapshot"):
        with TestClient(story_api.create_app(catalog, model, **options)):
            pytest.fail("strict invalid assets reached readiness")
    after = [(path.name, path.lstat().st_mtime_ns, path.lstat().st_ino,
              path.read_bytes() if path.is_file() and not path.is_symlink() else None)
             for path in artifact.parent.iterdir()]
    assert before == after
    assert calls == ([] if case == "wrong_catalog" else ["verify"])


@pytest.mark.parametrize("extra", [("--expected-catalog-sha256", "a" * 64),
                                   ("--expected-snapshot-sha256", "b" * 64),
                                   ("--expected-catalog-sha256", "a" * 64, "--expected-snapshot-sha256", "b" * 64),
                                   ("--expected-catalog-sha256", "a" * 64, "--expected-snapshot-sha256", "b" * 64,
                                    "--cache-dir", "cache", "--previous-catalog", "old.jsonl"),
                                   ("--expected-catalog-sha256", "X", "--expected-snapshot-sha256", "b" * 64,
                                    "--cache-dir", "cache")])
def test_partial_or_incompatible_strict_cli_refuses_before_starting(extra, monkeypatch, capsys):
    import uvicorn
    monkeypatch.setattr(uvicorn, "run", lambda *_args, **_kwargs: pytest.fail("invalid startup opened a server"))
    with pytest.raises(SystemExit) as error:
        story_api.main(["--catalog", "private", "--model-dir", "model", *extra])
    assert error.value.code == 2
    message = capsys.readouterr().err
    assert "requires both SHA-256 pins and a cache directory" in message and "private" not in message

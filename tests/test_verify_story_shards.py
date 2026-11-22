from hashlib import sha256
import json
import os

import pytest

from tools.qa import verify_story_shards as qa


pytestmark = pytest.mark.skipif(not qa._supported(), reason="requires POSIX directory descriptors")


def line(kind, identifier):
    return json.dumps({"media_type": kind, "tmdb_id": identifier, "title": "Generated title",
                       "overview": "Synthetic text only", "language": "en-US"}).encode() + b"\n"


def case(tmp_path, shards):
    entries = []
    for i, (content, movie, tv) in enumerate(shards):
        name = f"part-{i:05d}.jsonl"
        (tmp_path / name).write_bytes(content)
        entries.append({"file": name, "sha256": sha256(content).hexdigest(),
                        "rows": movie + tv, "bytes": len(content), "movie": movie, "tv": tv})
    return {"version": 1, "shards": entries, "total": {
        k: sum(entry[k] for entry in entries) for k in ("rows", "bytes", "movie", "tv")
    }}


def save(tmp_path, manifest):
    raw = json.dumps(manifest).encode()
    (tmp_path / qa.MANIFEST_NAME).write_bytes(raw)
    return sha256(raw).hexdigest()


def test_verify_more_than_desktop_limit_without_writing_sources(tmp_path):
    manifest = case(tmp_path, [
        (b"".join(line("movie", i) for i in range(1, 10_002)), 10_001, 0),
        (b"".join(line("tv", i) for i in range(1, 10_002)), 0, 10_001),
    ])
    pin = save(tmp_path, manifest)
    old = {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in tmp_path.iterdir()}
    assert qa.verify_shards(tmp_path, pin) == {
        "status": "VERIFIED_BYTES_ONLY", "manifest_sha256": pin, "shards": 2, **manifest["total"]
    }
    assert {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in tmp_path.iterdir()} == old


@pytest.mark.parametrize("bad", ["duplicate", "counter", "digest", "size", "entry-total", "global-cap",
                                 "traversal", "symlink", "fifo", "hardlink", "json-key", "bad-row", "non-utf8"])
def test_rejects_malformed_untrusted_inputs_without_disclosing_detail(tmp_path, capsys, bad, monkeypatch):
    other_media = "movie" if bad == "duplicate" else "tv"
    second = line(other_media, 1)
    if bad == "json-key":
        second = second.replace(b'"tmdb_id": 1,', b'"tmdb_id": 90, "tmdb_id": 1,')
    if bad == "bad-row":
        second = second.replace(b'"en-US"', b'"private"')
    if bad == "non-utf8":
        second = second.replace(b'Synthetic', b'\xff')
    manifest = case(tmp_path, [(line("movie", 1), 1, 0),
                               (second, int(other_media == "movie"), int(other_media == "tv"))])
    entry = manifest["shards"][1]
    target = tmp_path / entry["file"]
    if bad == "counter":
        entry.update(movie=1, tv=0)
        manifest["total"].update(movie=2, tv=0)
    if bad == "digest":
        entry["sha256"] = "0" * 64
    if bad == "size":
        target.write_bytes(second + b" ")
    if bad == "entry-total":
        manifest["total"]["bytes"] += 1
    if bad == "global-cap":
        monkeypatch.setattr(qa, "MAX_TOTAL_ROWS", 1)
    if bad == "traversal":
        entry["file"] = "../secret"
    if bad in {"symlink", "fifo", "hardlink"}:
        target.unlink()
        original = tmp_path / manifest["shards"][0]["file"]
        if bad == "symlink":
            target.symlink_to(original)
        elif bad == "hardlink":
            target.hardlink_to(original)
            entry.update(sha256=manifest["shards"][0]["sha256"], bytes=original.stat().st_size)
            manifest["total"]["bytes"] = 2 * original.stat().st_size
        else:
            os.mkfifo(target)
    pin = save(tmp_path, manifest)
    with pytest.raises(SystemExit) as error:
        qa.main(["--directory", str(tmp_path), "--manifest-sha256", pin])
    assert error.value.code == 1
    out, stderr = capsys.readouterr()
    assert not out
    assert stderr.startswith("Verification rejected:")
    for detail in (str(tmp_path), "part-", "secret", "Generated title", "Synthetic text", "private"):
        assert detail not in stderr


def test_wrong_manifest_pin_rejects_before_opening_any_shard(tmp_path, monkeypatch):
    manifest = case(tmp_path, [(line("movie", 1), 1, 0)])
    save(tmp_path, manifest)
    original = qa._open_regular

    def checked(fd, name, limit):
        assert name == qa.MANIFEST_NAME
        return original(fd, name, limit)

    monkeypatch.setattr(qa, "_open_regular", checked)
    with pytest.raises(qa.ShardVerificationError, match="manifest pin mismatch"):
        qa.verify_shards(tmp_path, "0" * 64)


def test_matching_hash_does_not_allow_duplicate_manifest_keys_or_non_posix(tmp_path, monkeypatch):
    raw = b'{"version":1,"version":1,"shards":[],"total":{}}'
    (tmp_path / qa.MANIFEST_NAME).write_bytes(raw)
    pin = sha256(raw).hexdigest()
    with pytest.raises(qa.ShardVerificationError, match="invalid or unreadable"):
        qa.verify_shards(tmp_path, pin)
    monkeypatch.setattr(qa, "_supported", lambda: False)
    with pytest.raises(qa.ShardVerificationError, match="POSIX"):
        qa.verify_shards(tmp_path, pin)


def test_change_during_descriptor_read_fails_closed(tmp_path, monkeypatch):
    manifest = case(tmp_path, [(line("movie", 1), 1, 0)])
    pin = save(tmp_path, manifest)
    shard = tmp_path / "part-00000.jsonl"
    original = qa._row

    def change_then_parse(raw):
        shard.write_bytes(line("movie", 2))
        return original(raw)

    monkeypatch.setattr(qa, "_row", change_then_parse)
    with pytest.raises(qa.ShardVerificationError, match="changed during verification"):
        qa.verify_shards(tmp_path, pin)


def test_rejects_single_shard_hardlinked_to_another_directory(tmp_path):
    shard_dir = tmp_path / "shards"
    shard_dir.mkdir()
    manifest = case(shard_dir, [(line("movie", 1), 1, 0)])
    pin = save(shard_dir, manifest)
    original = shard_dir / "part-00000.jsonl"
    (tmp_path / "outside").hardlink_to(original)
    with pytest.raises(qa.ShardVerificationError, match="singly linked"):
        qa.verify_shards(shard_dir, pin)
    assert original.read_bytes() == line("movie", 1)

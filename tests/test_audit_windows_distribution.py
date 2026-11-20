from hashlib import sha256

import pytest
from tools.qa import audit_windows_distribution as audit


def test_hashes_only_curated_binary_and_notices(tmp_path):
    (tmp_path / "Watchbane.exe").write_bytes(b"fake exec")
    for name in ("data", "models", ".preview-profile"):
        d = tmp_path / name
        d.mkdir()
        (d / "private.dll").write_bytes(b"not read")
    for name in ("model.onnx", "secret.zip", "synopses.jsonl"):
        (tmp_path / name).write_bytes(b"not read")
    lic = tmp_path / "licenses" / "onnxruntime"
    lic.mkdir(parents=True)
    (lic / "LICENSE").write_bytes(b"fictional")
    rows, excluded = audit.bundle_inventory(tmp_path)
    assert [r["path"] for r in rows] == ["Watchbane.exe", "licenses/onnxruntime/LICENSE"]
    assert rows[0]["sha256"] == sha256(b"fake exec").hexdigest()
    assert excluded == 6
    assert audit.missing_bundle_notices(rows, ["python", "onnxruntime"]) == [
        "python", "onnxruntime:third-party-notices"]


def test_no_reparse_follow_and_file_limit(tmp_path, monkeypatch):
    (tmp_path / "real.dll").write_bytes(b"ok")
    try:
        (tmp_path / "link.dll").symlink_to(tmp_path / "real.dll")
    except OSError:
        pytest.skip("symlinks require privileges on some Windows hosts")
    rows, excluded = audit.bundle_inventory(tmp_path)
    assert len(rows) == excluded == 1
    monkeypatch.setattr(audit, "MAX_FILES", 1)
    with pytest.raises(ValueError, match="traversal file limit"):
        audit.bundle_inventory(tmp_path)


def test_dist_record_cannot_escape_metadata_root(tmp_path, monkeypatch):
    (tmp_path / "LICENSE").write_bytes(b"good")

    class Distribution:
        version = "99.1"
        files = ["LICENSE", "../LICENSE", "PATH.txt"]
        def locate_file(self, _):
            return tmp_path

    monkeypatch.setattr(audit.metadata, "distribution", lambda _: Distribution())
    row = audit.package_inventory(["Test_Package"])["test-package"]
    assert row["version"] == "99.1"
    assert [n["path"] for n in row["notices"]] == ["LICENSE"]

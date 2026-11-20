from hashlib import sha256
import json

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



def test_summary_preserves_review_status_but_omits_filenames_and_hashes(tmp_path, monkeypatch, capsys):
    (tmp_path / "Watchbane.exe").write_bytes(b"fake exec")
    monkeypatch.setattr(audit, "package_inventory", lambda names: {
        audit.canonical(name): {"installed": True, "version": "1.2", "notices": [{"path": "LICENSE"}]}
        for name in names
    })
    assert audit.main(["--profile", "lexical", "--summary", "--bundle", str(tmp_path)]) == 1
    report = json.loads(capsys.readouterr().out)
    assert report["missing_bundle_notices"] == ["python", "PyQt6", "PyQt6-Qt6", "PyQt6-sip"]
    assert report["bundle_files_hashed"] == 1
    assert report["package_versions"]["pyqt6"] == "1.2"
    assert not {"installed_packages", "bundle", "bundle_excluded_entries"} & report.keys()


def test_msvc_bundle_names_are_exact_and_do_not_imply_loaded():
    rows = [{"path": p} for p in ("_internal/VCRUNTIME140_1.DLL", "_internal/msvcp140.dll",
                                 "unrelated/msvcp140.dll.bak", "prefix-msvcp140.dll", "msvcrt.dll")]
    assert audit.bundled_msvc_filenames(rows) == ["msvcp140.dll", "vcruntime140_1.dll"]
    assert audit.bundled_msvc_filenames(None) is None


def test_msvc_registration_reports_only_observed_version(monkeypatch):
    import sys
    from contextlib import nullcontext
    from types import SimpleNamespace

    def open_key(root, path, _reserved, flags):
        assert root == "HKLM" and flags & 1
        if path.endswith("\\arm64"):
            raise FileNotFoundError
        return nullcontext(path.rsplit("\\", 1)[-1])

    def query(key, name):
        fields = {"x64": {"Installed": 1, "Version": "v14.51.36247.0"},
                  "x86": {"Installed": 1, "Version": "must not log arbitrary registry text"}}
        return fields[key][name], None

    monkeypatch.setattr(audit.platform, "system", lambda: "Windows")
    monkeypatch.setitem(sys.modules, "winreg", SimpleNamespace(HKEY_LOCAL_MACHINE="HKLM",
                        KEY_READ=1, KEY_WOW64_64KEY=2, KEY_WOW64_32KEY=4, OpenKey=open_key, QueryValueEx=query))
    assert audit.host_msvc_registration() == {"x64": "14.51.36247.0"}
    monkeypatch.setattr(audit.platform, "system", lambda: "Linux")
    assert audit.host_msvc_registration() is None

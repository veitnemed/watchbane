import builtins
import json
import os
from pathlib import Path
from runpy import run_path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from candidates import story_model_probe, story_semantic


def rows(np):
    vectors = np.zeros((2, 384), dtype=np.float32)
    vectors[0, 0], vectors[1, 1] = 1.0, 1.0
    return vectors


def setup_encoder(monkeypatch, vectors, *, variant="fp32"):
    np = pytest.importorskip("numpy")
    calls = []

    def load(directory):
        calls.append(("load", directory))

        def encode(texts, *, prefix):
            calls.append(("encode", len(texts), prefix))
            return vectors(np)

        return SimpleNamespace(np=np, variant=variant, encode=encode)

    monkeypatch.setattr(story_semantic, "LocalE5", load)
    return calls


def test_model_probe_dispatch_precedes_gui_and_reports_only_checks(monkeypatch, tmp_path):
    calls = setup_encoder(monkeypatch, rows)
    output = tmp_path / "check.json"
    supplied = str(tmp_path / "Модель с пробелами")
    monkeypatch.setattr(sys, "argv", ["Watchbane.exe", "--check-semantic-model", supplied, str(output)])
    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        assert not name.startswith(("desktop", "PyQt")), "QA probe imported GUI"
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    with pytest.raises(SystemExit) as result:
        run_path("start_app.py", run_name="__main__")
    assert result.value.code == 0
    assert calls == [("load", supplied), ("encode", 2, "query: ")]
    assert json.loads(output.read_text(encoding="utf-8")) == {
        "status": "ok", "model_tested": True, "search_tested": False, "variant": "fp32",
        "input_count": 2, "embedding_size": 384, "shape_ok": True,
        "finite": True, "unit_norm": True, "differentiated": True,
    }


@pytest.mark.parametrize(
    ("bad", "field"),
    [
        (lambda np: rows(np)[:, :-1], "shape_ok"),
        (lambda np: rows(np).astype(np.int32), "shape_ok"),
        (lambda np: rows(np) * np.nan, "finite"),
        (lambda np: rows(np) * 2, "unit_norm"),
        (lambda np: np.repeat(rows(np)[0:1], 2, axis=0), "differentiated"),
    ],
)
def test_checks_reject_bad_embeddings(monkeypatch, bad, field):
    setup_encoder(monkeypatch, bad)
    result = story_model_probe.check_model("not-opened-by-stub")
    assert result["status"] == "invalid_embeddings"
    assert result["model_tested"] and not result["search_tested"] and result[field] is False


def test_failure_writes_redacted_report_without_overwriting_existing_file(monkeypatch, tmp_path):
    def missing_model(path):
        raise ValueError(f"private model path: {path}")

    monkeypatch.setattr(story_semantic, "LocalE5", missing_model)
    output = tmp_path / "failed.json"
    assert story_model_probe.write_model_check("private-model-name", output) == 1
    original = output.read_text(encoding="utf-8")
    assert json.loads(original) == {"status": "model_load_failed", "error_type": "ValueError",
                                    "model_tested": False, "search_tested": False}
    with pytest.raises(FileExistsError):
        story_model_probe.write_model_check("another-private-name", output)
    assert output.read_text(encoding="utf-8") == original


def test_bad_argument_count_does_not_start_gui(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["Watchbane.exe", "--check-semantic-model", "missing-report"])
    with pytest.raises(SystemExit) as result:
        run_path("start_app.py", run_name="__main__")
    assert result.value.code == 2


def test_real_fp32_probe_via_source_cli(tmp_path):
    folder = os.environ.get("WATCHBANE_TEST_MODEL_DIR")
    if not folder or not (Path(folder) / "onnx/model.onnx").is_file():
        pytest.skip("Set WATCHBANE_TEST_MODEL_DIR to verified local portable FP32 E5")
    output = tmp_path / "probe.json"
    process = subprocess.run(
        [sys.executable, "start_app.py", "--check-semantic-model", folder, str(output)],
        capture_output=True, timeout=45,
    )
    assert process.returncode == 0 and process.stdout == b""
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["status"] == "ok" and result["model_tested"] and not result["search_tested"]
    assert result["variant"] == "fp32" and result["embedding_size"] == 384
    assert result["shape_ok"] and result["finite"] and result["unit_norm"] and result["differentiated"]

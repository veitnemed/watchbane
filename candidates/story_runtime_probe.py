"""Offline smoke check of optional native libraries, not of model availability."""
import json
from importlib import import_module
from pathlib import Path


def _field(number: int, payload: bytes) -> bytes:
    # Length-delimited fields in the tiny, fixed test graph below fit in one byte.
    return bytes(((number << 3) | 2, len(payload))) + payload


def _identity_graph() -> bytes:
    """A synthetic IR 8, opset 13 Identity graph for a one-element Float32 tensor."""
    shape = _field(1, b"\x08\x01")
    tensor_type = _field(1, b"\x08\x01" + _field(2, shape))

    def value(name: bytes) -> bytes:
        return _field(1, name) + _field(2, tensor_type)

    node = _field(1, b"x") + _field(2, b"y") + _field(4, b"Identity")
    graph = _field(1, node) + _field(2, b"RuntimeProbe") + _field(11, value(b"x")) + _field(12, value(b"y"))
    return b"\x08\x08" + _field(7, graph) + _field(8, b"\x10\x0d")


def check_runtime() -> dict:
    versions = {}
    libraries = {}
    for name in ("numpy", "onnxruntime", "tokenizers"):
        try:
            library = import_module(name)
        except ModuleNotFoundError as error:
            return {
                "status": "library_missing" if error.name == name else "runtime_error",
                "library": name,
                "error_type": type(error).__name__,
                "model_tested": False,
            }
        except Exception as error:
            return {"status": "runtime_error", "library": name, "error_type": type(error).__name__, "model_tested": False}
        libraries[name] = library
        versions[name] = library.__version__

    check = "numpy"
    try:
        np, ort, tokenizers = (libraries[name] for name in ("numpy", "onnxruntime", "tokenizers"))
        x = np.array([2.0], dtype=np.float32)
        if (x + 1.0).tolist() != [3.0]:
            raise RuntimeError("NumPy calculation failed")
        check = "tokenizers"
        tokenizer = tokenizers.Tokenizer(tokenizers.models.WordLevel(vocab={"[UNK]": 0, "probe": 1}, unk_token="[UNK]"))
        if tokenizer.encode("probe").ids != [1]:
            raise RuntimeError("Tokenizer check failed")
        check = "onnxruntime"
        session = ort.InferenceSession(_identity_graph(), providers=["CPUExecutionProvider"])
        if session.get_providers() != ["CPUExecutionProvider"] or session.run(["y"], {"x": x})[0].tolist() != [2.0]:
            raise RuntimeError("ORT CPU inference failed")
    except Exception as error:
        return {"status": "runtime_error", "library": check, "error_type": type(error).__name__, "model_tested": False}
    return {"status": "ok", "versions": versions, "cpu_inference": True, "model_tested": False}


def write_runtime_check(output_path: str | Path) -> int:
    result = check_runtime()
    with Path(output_path).open("x", encoding="utf-8") as file:
        json.dump(result, file)
        file.write("\n")
    return 0 if result["status"] == "ok" else 1

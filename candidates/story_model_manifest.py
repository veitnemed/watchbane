"""Pinned official publisher artifacts; the runtime never downloads files."""
MODEL_ID = "intfloat/multilingual-e5-small"
REVISION = "614241f622f53c4eeff9890bdc4f31cfecc418b3"
FILES = {
    "onnx/model_qint8_avx512_vnni.onnx": "dd476dd0c2514e9b9be83aeb3853fac0763e0bdf4a71645407587d77c48a2d88",
    "onnx/tokenizer.json": "0b44a9d7b51c3c62626640cda0e2c2f70fdacdc25bbbd68038369d14ebdf4c39",
}

PORTABLE_FILES = {
    "onnx/model.onnx": "ca456c06b3a9505ddfd9131408916dd79290368331e7d76bb621f1cba6bc8665",
    "onnx/tokenizer.json": FILES["onnx/tokenizer.json"],
}


def artifact_sha256(path):
    """Verify large artifacts without allocating a full model-sized byte buffer."""
    from hashlib import sha256
    digest = sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

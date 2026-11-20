"""Offline inference check for an operator-supplied, pinned E5 folder."""
from __future__ import annotations

import json
from pathlib import Path

# A runtime signal, not a search benchmark. Never report the phrases or vectors.
_PHRASES = ("Врач лечит пациента в больнице.", "Капитан ведёт корабль через шторм.")
_EXPECTED_SHAPE = (2, 384)


def check_model(model_dir: str | Path) -> dict:
    """Use the normal E5 loader and verify nontrivial CPU embeddings."""
    try:
        from candidates.story_semantic import LocalE5

        model = LocalE5(model_dir)
    except Exception as error:
        return {"status": "model_load_failed", "error_type": type(error).__name__,
                "model_tested": False, "search_tested": False}

    try:
        np = model.np
        vectors = model.encode(_PHRASES, prefix="query: ")
        shape_ok = vectors.shape == _EXPECTED_SHAPE and np.issubdtype(vectors.dtype, np.floating)
        finite = bool(shape_ok and np.isfinite(vectors).all())
        unit_norm = bool(finite and np.allclose(np.linalg.norm(vectors, axis=1), 1.0,
                                                rtol=0, atol=1e-4))
        differentiated = bool(finite and not np.allclose(vectors[0], vectors[1], rtol=1e-4, atol=1e-5))
    except Exception as error:
        return {"status": "inference_failed", "error_type": type(error).__name__,
                "model_tested": True, "search_tested": False}

    ok = shape_ok and finite and unit_norm and differentiated
    return {"status": "ok" if ok else "invalid_embeddings", "model_tested": True, "search_tested": False,
            "variant": model.variant, "input_count": len(_PHRASES),
            "embedding_size": vectors.shape[1] if shape_ok else None, "shape_ok": bool(shape_ok),
            "finite": finite, "unit_norm": unit_norm, "differentiated": differentiated}


def write_model_check(model_dir: str | Path, output_path: str | Path) -> int:
    # An existing report cannot be replaced, even by a successful check.
    with Path(output_path).open("x", encoding="utf-8") as file:
        result = check_model(model_dir)
        json.dump(result, file)
        file.write("\n")
    return 0 if result["status"] == "ok" else 1

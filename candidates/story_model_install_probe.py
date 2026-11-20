"""Report only whether an explicit, pinned E5 installation succeeded."""
from __future__ import annotations

import json
from pathlib import Path


def write_model_install_check(destination: str | Path, output_path: str | Path) -> int:
    destination_path = Path(destination)
    report_path = Path(output_path)
    if report_path.resolve().is_relative_to(destination_path.resolve()):
        raise ValueError("The report must be outside the model destination")
    # Reserve a new report *before* starting the expensive operation. The
    # report is intentionally unrelated to inference and search acceptance.
    with report_path.open("x", encoding="utf-8") as file:
        result = {"status": "install_failed", "installation_verified": False,
                  "model_tested": False, "search_tested": False}
        try:
            from candidates.story_model_install import install_story_model

            install_story_model(destination_path)
        except Exception:
            # Do not expose a path, exception text, signed CDN URL or proxy.
            pass
        else:
            result.update(status="ok", installation_verified=True)
        json.dump(result, file)
        file.write("\n")
    return 0 if result["installation_verified"] else 1

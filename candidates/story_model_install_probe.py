"""Report redacted diagnostics for an explicit, pinned E5 installation."""
from __future__ import annotations

import json
from pathlib import Path

_INSTALL_FAILURE_CODES = frozenset({
    "redirect_host", "http_status", "invalid_response", "integrity",
    "network_or_disk", "tls", "timeout", "existing_invalid", "cancelled",
})


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
            from candidates.story_model_install import StoryModelInstallError, install_story_model
        except Exception:
            result.update(failure_stage="import_installer", failure_code="import_error")
        else:
            try:
                install_story_model(destination_path)
            except StoryModelInstallError as error:
                # No raw exception message, signed URL, path or proxy details.
                code = getattr(error, "code", None)
                safe_code = code if type(code) is str and code in _INSTALL_FAILURE_CODES else "runtime_error"
                result.update(failure_stage="install", failure_code=safe_code)
            except Exception:
                result.update(failure_stage="install", failure_code="runtime_error")
            else:
                result.update(status="ok", installation_verified=True)
        json.dump(result, file)
        file.write("\n")
    return 0 if result["installation_verified"] else 1

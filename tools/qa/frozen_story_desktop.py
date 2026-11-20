"""Private PyInstaller QA entrypoint. Never import from the product launcher."""
import json
from pathlib import Path
import sys

from tools.qa.smoke_story_desktop import _child_report


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 3 or args[0] not in {"first", "reopen"}:
        return 2
    phase, request, report = args
    try:
        # Reserve the report before doing anything; never overwrite a file.
        with Path(report).open("x", encoding="ascii") as output:
            with Path(request).open(encoding="ascii") as source:
                options = json.load(source)
            if not isinstance(options, dict) or options.get("verify_cached_install") is not True:
                result = {"ok": False, "failure": "Cached model verification is required."}
            else:
                options["require_fp32"] = True
                result = _child_report(phase, options)
            result["frozen"] = bool(getattr(sys, "frozen", False))
            json.dump(result, output, ensure_ascii=True)
    except (OSError, ValueError):
        return 1
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

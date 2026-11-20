"""Build a private QA-only overlay from the production spec, without altering it.

Usage from the repository root: python -m tools.qa.build_frozen_story_desktop <new-output-dir>
"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        return 2
    root = Path(__file__).resolve().parents[2]
    output = Path(args[0]).expanduser().resolve()
    if output == root or output.is_relative_to(root):
        raise ValueError("Private QA output must be outside the repository.")
    output.mkdir(parents=True, exist_ok=False)
    spec = (root / "watchbane.spec").read_text(encoding="utf-8")
    for before, after in (
        ('["start_app.py"]', f'[{str(root / "tools/qa/frozen_story_desktop.py")!r}]'),
        ("pathex=[]", f"pathex=[{str(root)!r}]"),
        ('name="Watchbane"', 'name="WatchbaneStoryQA"'),
        ('a = Analysis(', 'a = _qa_analysis('),
        ('"tools/windows_version_info.txt"', repr(str(root / "tools/windows_version_info.txt"))),
        ('"desktop/images/logos/main_icon.ico"', repr(str(root / "desktop/images/logos/main_icon.ico"))),
    ):
        expected = 2 if before.startswith("name=") else 1
        if spec.count(before) != expected:
            raise ValueError("Production spec has changed; review the private QA overlay.")
        spec = spec.replace(before, after)
    # PyInstaller resolves data names relative to the temporary spec, so give
    # its analysis the product directory for source assets, not the QA folder.
    spec = (
        "from pathlib import Path\n"
        "def _qa_analysis(*args, **kwargs):\n"
        f"    root = Path({str(root)!r})\n"
        "    kwargs['datas'] = [(str(root / source), target) for source, target in kwargs['datas']]\n"
        "    return Analysis(*args, **kwargs)\n"
    ) + spec
    with tempfile.TemporaryDirectory(prefix="watchbane-qt-spec-") as temporary:
        spec_file = Path(temporary) / "story-qa.spec"
        spec_file.write_text(spec, encoding="utf-8")
        return subprocess.call([
            sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
            "--distpath", str(output), "--workpath", str(Path(temporary) / "work"), str(spec_file),
        ], cwd=root, env={**os.environ, "WATCHBANE_BUNDLE_PROFILE": "semantic",
                        "PYINSTALLER_CONFIG_DIR": str(Path(temporary) / "config")})


if __name__ == "__main__":
    raise SystemExit(main())

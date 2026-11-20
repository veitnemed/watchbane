"""Inventory locally installed runtimes and a curated frozen bundle; not license clearance."""
import argparse
from hashlib import sha256
from importlib import metadata
import json
from pathlib import Path
import platform
import re
import stat
import sys

PACKAGES = ("PyQt6", "PyQt6-Qt6", "PyQt6-sip", "numpy", "onnxruntime",
            "tokenizers", "pyinstaller")
MAX_FILES = 10000
MAX_BYTES = 2 * 1024**3
MAX_NOTICE = 4 * 1024**2
BLOCK_PARTS = {"model", "models", "data", "profiles", "profile", "cache", "catalog", "datasets"}
BINARY = {".exe", ".dll", ".pyd", ".pyz", ".ico", ".svg", ".qm"}


def notice_name(name):
    return bool(re.match(r"^(?:licen[sc]e|copying|copyright|notice|third[ _-]?party[ _-]?notices)(?:$|[._-])",
                         name, re.I))


def canonical(s):
    return re.sub(r"[-_.]+", "-", s).lower()


def digest(path, budget):
    size = path.lstat().st_size
    if size > budget:
        raise ValueError("Byte budget exceeded")
    h = sha256()
    n = 0
    with path.open("rb") as f:
        while chunk := f.read(1024**2):
            n += len(chunk)
            if n > budget:
                raise ValueError("Byte budget exceeded")
            h.update(chunk)
    if n != size:
        raise ValueError("File changed during audit")
    return {"sha256": h.hexdigest(), "bytes": n}


def linked(path):
    st = path.lstat()
    return stat.S_ISLNK(st.st_mode) or bool(
        getattr(st, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    )


def package_inventory(names=PACKAGES):
    out = {}
    for name in names:
        try:
            dist = metadata.distribution(name)
        except metadata.PackageNotFoundError:
            out[canonical(name)] = {"installed": False, "notices": []}
            continue
        files = list(dist.files or ())
        if len(files) > MAX_FILES:
            raise ValueError("Distribution metadata file limit exceeded")
        root = Path(dist.locate_file("")).resolve()
        verified = []
        for item in files:
            rel = Path(item)
            if not notice_name(rel.name) or rel.is_absolute() or ".." in rel.parts:
                continue
            path = root / rel
            candidates = [root.joinpath(*rel.parts[:i+1]) for i in range(len(rel.parts))]
            if any(not a.exists() or linked(a) for a in candidates) or not path.is_file():
                continue
            verified.append({"path": rel.as_posix(), **digest(path, MAX_NOTICE)})
        out[canonical(name)] = {"installed": True, "version": dist.version,
                               "notices": sorted(verified, key=lambda x: x["path"])}
    return out


def bundle_inventory(root):
    if not root.is_dir() or any(linked(p) for p in (root, *root.absolute().parents)):
        raise ValueError("Bundle root must be a normal directory")
    root = root.resolve()
    records, stack = [], [root]
    inspected = amount = excluded = 0
    while stack:
        for node in stack.pop().iterdir():
            inspected += 1
            if inspected > MAX_FILES:
                raise ValueError("Bundle traversal file limit exceeded")
            name = node.name.casefold()
            file_type = node.lstat().st_mode
            if linked(node) or name.startswith(".") or name in BLOCK_PARTS or name.startswith(("story-catalog", "story_vectors")):
                excluded += 1
                continue
            if stat.S_ISDIR(file_type):
                stack.append(node)
                continue
            if not stat.S_ISREG(file_type) or not (node.suffix.lower() in BINARY or name == "base_library.zip" or notice_name(name)):
                excluded += 1
                continue
            row = digest(node, min(MAX_NOTICE if notice_name(name) else MAX_BYTES, MAX_BYTES-amount))
            amount += row["bytes"]
            records.append({"path": node.relative_to(root).as_posix(), **row})
    return sorted(records, key=lambda r: r["path"]), excluded


def missing_bundle_notices(files, names):
    paths = [Path(f["path"]) for f in files]
    missing = []
    for name in names:
        records = [p for p in paths if len(p.parts) >= 3 and p.parts[0].lower() == "licenses"
                   and canonical(p.parts[1]) == canonical(name) and notice_name(p.name)]
        if not any(re.match(r"^(?:licen[sc]e|copying)(?:$|[._-])", p.name, re.I) for p in records):
            missing.append(name)
        if name == "onnxruntime" and not any(re.match(r"^third[ _-]?party[ _-]?notices", p.name, re.I) for p in records):
            missing.append("onnxruntime:third-party-notices")
    return missing


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path)
    parser.add_argument("--profile", choices=("lexical", "semantic"), default="semantic")
    args = parser.parse_args(argv)
    names = PACKAGES if args.profile == "semantic" else tuple(p for p in PACKAGES if p not in {"numpy", "onnxruntime", "tokenizers"})
    try:
        packages = package_inventory(names)
        rows, excluded = bundle_inventory(args.bundle) if args.bundle else (None, None)
    except (OSError, ValueError) as e:
        parser.error(str(e))
    # PyInstaller itself is a build input, not a mandatory constituent notice.
    required = ["python", *(p for p in names if p != "pyinstaller")]
    flags = [name for name, row in packages.items() if not row["installed"] or not row["notices"]]
    missing = missing_bundle_notices(rows, required) if rows is not None else None
    print(json.dumps({
        "audit_host": {"system": platform.system(), "machine": platform.machine(), "python": platform.python_version()},
        "profile": args.profile, "installed_packages": packages, "package_review_flags": flags,
        "bundle": rows, "bundle_excluded_entries": excluded, "missing_bundle_notices": missing,
        "scope": "Observed files only; not legal clearance or proof of target platform or source completeness."
    }, indent=2))
    return int(bool(missing or flags))


if __name__ == "__main__":
    sys.exit(main())

"""Build or validate a credential-free Watchbane source preview from a Git commit."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import zipfile

PREFIX = "Watchbane/"
MANIFEST = "SOURCE_MANIFEST.json"
TOP = frozenset("""
    LICENSE SOURCE_PREVIEW.md RELEASE_NOTES.md VERSION.md Start-Preview.cmd
    preview.py requirements.txt requirements-preview.txt requirements-story.txt
""".split())
PACKAGES = frozenset("apis app candidates common config dataset desktop diagnostics posters storage ui".split())
EXACT = frozenset("""
    candidates/search/title_aliases.json config/tags.json
    tools/__init__.py tools/migrations/legacy_paths.py tools/qa/__init__.py
    tools/qa/download_story_model.py
""".split())
EXCLUDED = frozenset({"candidates/story_demo.py"})
ASSETS = frozenset("""
    logos/main_icon.ico logos/w_symbol_png.png
    logos_for_start_select_menu/all_icons_for_label.png
    logos_for_start_select_menu/icons2.png
    logos_for_start_select_menu/logo_tmdb.png
    logos_for_start_select_menu/wathbane_logo.png
    story_ticket.svg user_rating_not_for_me.svg user_rating_ok.svg user_rating_top.svg
""".split()) | frozenset(
    "logos_for_start_select_menu/split_icons/" + name + ".png" for name in """
        anime british_european_detective dark_thriller_crime family_animation
        hollywood_mainstream k_drama manual russian_mainstream turkish_dramas
    """.split()
)
BINARY_SUFFIXES = frozenset({".png", ".ico"})
MAX_FILE = 8_000_000
MAX_TOTAL = 30_000_000
SCHEMA = 1

# These identify credential formats, not every possible secret. The path allowlist
# and human review of the selected commit are separate release controls.
CREDENTIAL = re.compile(
    r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{12,}\b"
    r"|\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})\b"
    r"|-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----"
    r"|\b(?:tmdb[_-]?(?:token|api[_-]?key|read[_-]?token)|api_key)"
    r"""\s*["']?\s*[:=]\s*["']?[0-9a-f]{32}\b""",
    re.IGNORECASE,
)
# The former fictional catalog contains this key space. Runtime source must not
# import that module or carry those sample records even after a file rename.
DEMO = re.compile(r"\bstory_demo\b|\bdemo_documents\b|\bdemo:\d{2}\b|Авторский вымышленный пример Watchbane")


def allowed(name: str) -> bool:
    path = PurePosixPath(name)
    if path.as_posix() != name or len(path.parts) == 0 or any(
        p in {".", ".."} or p.startswith(".") or p == "__pycache__" or ":" in p or "\\" in p
        for p in path.parts
    ) or "\x00" in name:
        return False
    if name in EXCLUDED:
        return False
    if name in TOP or name in EXACT:
        return True
    if name.startswith("desktop/images/"):
        return name.removeprefix("desktop/images/") in ASSETS
    return len(path.parts) > 1 and path.parts[0] in PACKAGES and path.suffix == ".py"


def validate_bytes(name: str, data: bytes) -> None:
    if len(data) > MAX_FILE:
        raise ValueError(f"Entry too large: {name}")
    suffix = PurePosixPath(name).suffix
    if suffix in BINARY_SUFFIXES:
        signature = b"\x89PNG\r\n\x1a\n" if suffix == ".png" else b"\x00\x00\x01\x00"
        if not data.startswith(signature):
            raise ValueError(f"Unexpected asset type: {name}")
        return
    text = data.decode("utf-8-sig")
    if "\x00" in text or CREDENTIAL.search(text):
        raise ValueError(f"Binary text or potential credential: {name}")
    if suffix == ".py" and DEMO.search(text):
        raise ValueError(f"Fictional/demo source reference: {name}")


def git(repo: Path, *args: str) -> bytes:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True
    ).stdout


def sources(repo: Path, ref: str) -> tuple[str, dict[str, bytes]]:
    commit = git(repo, "rev-parse", "--verify", "--end-of-options", f"{ref}^{{commit}}").decode().strip()
    entries: dict[str, bytes] = {}
    size = 0
    for item in git(repo, "ls-tree", "-rz", commit).split(b"\0"):
        if not item:
            continue
        header, raw_name = item.split(b"\t", 1)
        name = raw_name.decode()
        if not allowed(name):
            continue
        mode, kind, oid = header.decode().split()
        if mode not in {"100644", "100755"} or kind != "blob":
            raise ValueError(f"Allowlisted path is not a regular tracked file: {name}")
        data = git(repo, "cat-file", "blob", oid)
        validate_bytes(name, data)
        size += len(data)
        if size > MAX_TOTAL:
            raise ValueError("Total payload size exceeds limit")
        entries[name] = data
    require_layout(entries)
    return commit, entries


def require_layout(entries: dict) -> None:
    required = TOP | {"desktop/shell/bootstrap.py", "candidates/story_service.py"}
    if missing := required - entries.keys():
        raise ValueError(f"Missing required entries: {', '.join(sorted(missing))}")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def manifest(commit: str, entries: dict[str, bytes]) -> bytes:
    return (json.dumps({
        "schema": SCHEMA, "commit": commit,
        "sha256": {name: digest(data) for name, data in entries.items()},
    }, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def zipinfo(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(PREFIX + name, (1980, 1, 1, 0, 0, 0))
    info.create_system = 3
    info.external_attr = 0o100644 << 16
    return info


def archive_bytes(commit: str, entries: dict[str, bytes]) -> bytes:
    result = io.BytesIO()
    with zipfile.ZipFile(result, "w", compression=zipfile.ZIP_STORED) as archive:
        for name, data in sorted({**entries, MANIFEST: manifest(commit, entries)}.items()):
            archive.writestr(zipinfo(name), data)
    return result.getvalue()


def verify(path: Path, repo: Path | None = None, ref: str | None = None) -> tuple[str, int]:
    with zipfile.ZipFile(path) as archive:
        items = archive.infolist()
        names = [item.filename for item in items]
        if (names != sorted(names) or len(names) != len(set(names))
                or len(names) != len({name.casefold() for name in names})):
            raise ValueError("Unsorted or colliding archive entries")
        if sum(item.file_size for item in items) > MAX_TOTAL:
            raise ValueError("Total payload size exceeds limit")
        entries: dict[str, bytes] = {}
        for info in items:
            if not info.filename.startswith(PREFIX):
                raise ValueError("Archive entry outside Watchbane root")
            name = info.filename.removeprefix(PREFIX)
            if info.file_size > MAX_FILE or (name != MANIFEST and not allowed(name)):
                raise ValueError(f"Unexpected archive entry: {name}")
            canonical = zipinfo(name)
            if any(getattr(info, k) != getattr(canonical, k) for k in (
                "create_system", "external_attr", "date_time", "compress_type"
            )):
                raise ValueError(f"Unexpected archive metadata: {name}")
            data = archive.read(info)
            validate_bytes(name, data)
            entries[name] = data
    raw = entries.pop(MANIFEST, b"")
    stated = json.loads(raw)
    commit = stated.get("commit", "")
    if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", commit):
        raise ValueError("Invalid manifest commit")
    require_layout(entries)
    if raw != manifest(commit, entries):
        raise ValueError("Manifest does not match archive contents")
    if repo is not None and ref is not None:
        expected_commit, expected = sources(repo, ref)
        if commit != expected_commit or expected != entries:
            raise ValueError("Archive does not match the pinned Git tree")
    return commit, len(entries)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    for name in ("build", "verify"):
        sub = actions.add_parser(name)
        sub.add_argument("archive", type=Path)
        sub.add_argument("--repo", type=Path, default=Path.cwd())
        sub.add_argument("--ref", default="HEAD" if name == "build" else None)
    args = parser.parse_args()
    try:
        if args.action == "build":
            checksum_path = Path(str(args.archive) + ".sha256")
            if args.archive.exists() or checksum_path.exists():
                raise FileExistsError("Refusing to replace an archive or checksum")
            commit, files = sources(args.repo, args.ref)
            blob = archive_bytes(commit, files)
            with args.archive.open("xb") as output:
                output.write(blob)
            with checksum_path.open("x", encoding="ascii", newline="\n") as checksum:
                checksum.write(f"{digest(blob)}  {args.archive.name}\n")
        commit, count = verify(args.archive, args.repo, args.ref)
        print(f"Verified {count} files from {commit}; SHA-256 {digest(args.archive.read_bytes())}")
    except (OSError, ValueError, zipfile.BadZipFile, subprocess.CalledProcessError) as exc:
        print(f"Preview packaging failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

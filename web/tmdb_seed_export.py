"""Private, explicit clearance gate for reviewed TMDb snapshot export."""
from collections import Counter
from collections.abc import Mapping
from contextlib import closing
from hashlib import sha256
import json
import os
from pathlib import Path
import sqlite3
from tempfile import NamedTemporaryFile

from candidates.story_seed_snapshot import MAX_FILE_BYTES, MAX_LINE_BYTES, MAX_ROWS
from web.tmdb_catalog_audit import ReviewedLanguage
from web.tmdb_ids import IdPlan


_LANG = {"ru": "ru-RU", "en": "en-US"}
_STATES = ("hydrated", "ineligible", "missing_overview")


def _reviewed_payload(payload, media, identifier):
    try:
        row = json.loads(payload)
    except (ValueError, TypeError, RecursionError):
        raise ValueError("Invalid hydrated payload") from None
    if not isinstance(row, dict):
        raise ValueError("Invalid hydrated payload")
    title, synopsis, year = (row.get(k) for k in ("title", "overview", "year"))
    if (row.get("media_type") != media or type(row.get("tmdb_id")) is not int or row["tmdb_id"] != identifier
            or not isinstance(title, str) or not title.strip() or len(title) > 512
            or not isinstance(synopsis, str) or not synopsis.strip() or len(synopsis) > 8192
            or (year is not None and (type(year) is not int or not 1800 <= year <= 2200))):
        raise ValueError("Invalid hydrated payload")
    return {"media_type": media, "tmdb_id": identifier, "title": title, "overview": synopsis, "year": year}


def export_reviewed_seed(
    *, plan: IdPlan, checkpoint: Path, output: Path,
    reviewed: Mapping[str, ReviewedLanguage], use_cleared: bool = False,
) -> dict:
    """Export only language-reviewed rows from one complete read-only snapshot.

    The caller must attest clearance for the intended use. Neither clearance nor
    the provenance of the supplied language review is independently verified.
    The destination must be new, on a filesystem supporting hard-link publish.
    """
    if use_cleared is not True:
        raise PermissionError("Explicit intended-use clearance is required")
    output = Path(output)
    if output.exists() or output.is_symlink():
        raise FileExistsError("Choose a new seed destination")
    planned = {i.key for i in plan.queue}
    if len(planned) != len(plan.queue) or not planned or len(planned) > MAX_ROWS:
        raise ValueError("Invalid typed ID plan")
    if not reviewed or not reviewed.keys() <= planned:
        raise ValueError("A non-empty review for the exact typed ID plan is required")
    manifest = json.dumps(plan.manifest(), sort_keys=True, separators=(",", ":"))
    found, emitted = set(), set()
    states, languages = Counter(), Counter()
    out_bytes = 0
    staged = None
    try:
        with closing(sqlite3.connect(Path(checkpoint).resolve().as_uri() + "?mode=ro", uri=True)) as conn:
            conn.execute("BEGIN")
            if conn.execute("SELECT manifest FROM hydration_plan WHERE singleton=1").fetchone() != (manifest,):
                raise ValueError("Hydration checkpoint differs from the ID plan")
            with NamedTemporaryFile(dir=output.parent, prefix=".tmdb-seed-", delete=False) as file:
                staged = Path(file.name)
                for media, identifier, status, payload in conn.execute(
                    "SELECT media, tmdb_id, status, payload FROM hydration_items ORDER BY media, tmdb_id"
                ):
                    key = f"tmdb:{media}:{identifier}"
                    if key not in planned or key in found or status not in _STATES:
                        raise ValueError("Unexpected typed hydration state")
                    found.add(key)
                    states[status] += 1
                    if status != "hydrated":
                        if payload is not None or key in reviewed:
                            raise ValueError("Language review requires a hydrated description")
                        continue
                    row = _reviewed_payload(payload, media, identifier)
                    if key not in reviewed:
                        continue
                    review = reviewed[key]
                    try:
                        digest = sha256(row["overview"].encode("utf-8")).hexdigest()
                    except UnicodeError:
                        raise ValueError("Invalid hydrated payload") from None
                    if (not isinstance(review, ReviewedLanguage) or review.language not in _LANG
                            or review.synopsis_sha256 != digest):
                        raise ValueError("Language review does not match the hydrated description")
                    row["language"] = _LANG[review.language]
                    line = (json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
                    out_bytes += len(line)
                    if len(line) > MAX_LINE_BYTES or out_bytes > MAX_FILE_BYTES:
                        raise ValueError("Seed exceeds reader size limits")
                    file.write(line)
                    emitted.add(key)
                    languages[review.language] += 1
                if found != planned:
                    raise ValueError("Hydration checkpoint is incomplete")
                if emitted != reviewed.keys():
                    raise ValueError("Language review requires a hydrated description")
                file.flush()
                os.fsync(file.fileno())
        # Atomic no-clobber even if a competitor creates the final path after
        # validation. On unsupported filesystems this fails rather than overwrites.
        os.link(staged, output)
    finally:
        if staged is not None:
            staged.unlink(missing_ok=True)
    return {"planned": len(planned), "completed": len(found),
            **{status: states[status] for status in _STATES},
            "unreviewed_hydrated": states["hydrated"] - len(emitted),
            "exported": len(emitted), "by_reviewed_language": {lang: languages[lang] for lang in _LANG}}

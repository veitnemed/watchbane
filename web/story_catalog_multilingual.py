"""Validate an operator-pinned multilingual snapshot (no runtime wiring)."""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import stat

from candidates.story_seed_snapshot import MAX_FILE_BYTES, MAX_LINE_BYTES, MAX_ROWS


FORMAT = "watchbane-operator-multilingual-catalog-v1"
_SHA = re.compile(r"[0-9a-f]{64}", flags=re.ASCII)
_LOCALE = re.compile(r"[a-z]{2}-[A-Z]{2}", flags=re.ASCII)
_LANG = re.compile(r"[a-z]{2}", flags=re.ASCII)
_FIELDS = {"id", "media_type", "tmdb_id", "title", "overview", "year",
           "synopsis_locale", "original_language", "evidence"}
_EVIDENCE_FIELDS = {"source", "provider_locale", "synopsis_sha256"}


@dataclass(frozen=True)
class MultilingualRow:
    key: str
    media_type: str
    tmdb_id: int
    title: str
    overview: str
    year: int | None
    synopsis_locale: str
    original_language: str | None
    synopsis_sha256: str


def _unique(members):
    obj = dict(members)
    if len(members) != len(obj):
        raise ValueError
    return obj


def _row(row):
    if not isinstance(row, dict) or set(row) != _FIELDS:
        raise ValueError
    key, kind, identifier = row["id"], row["media_type"], row["tmdb_id"]
    title, synopsis, year = row["title"], row["overview"], row["year"]
    locale, original, evidence = row["synopsis_locale"], row["original_language"], row["evidence"]
    if (kind not in ("movie", "tv") or type(identifier) is not int or not 0 < identifier < 2**31
            or key != f"tmdb:{kind}:{identifier}"
            or not isinstance(title, str) or not title.strip() or "\0" in title or len(title) > 512
            or not isinstance(synopsis, str) or not synopsis.strip() or "\0" in synopsis or len(synopsis) > 8192
            or (year is not None and (type(year) is not int or not 1800 <= year <= 2200))
            or not isinstance(locale, str) or not _LOCALE.fullmatch(locale)
            or (original is not None and (not isinstance(original, str) or not _LANG.fullmatch(original)))
            or not isinstance(evidence, dict) or set(evidence) != _EVIDENCE_FIELDS
            or evidence["source"] != "provider_translation_record"
            or evidence["provider_locale"] != locale):
        raise ValueError
    title.encode("utf-8")
    sha = hashlib.sha256(synopsis.encode("utf-8")).hexdigest()
    if evidence["synopsis_sha256"] != sha:
        raise ValueError
    return MultilingualRow(key, kind, identifier, title, synopsis, year, locale, original, sha)


def load_operator_catalog(path: Path, *, expected_sha256: str) -> tuple[MultilingualRow, ...]:
    """Accept only an operator-pinned versioned JSONL with reviewed input shape.

    A whole-file pin does not establish provider origin, language truth or use
    rights. Original-language metadata is distinct from the selected text tag.
    The standard desktop/server RU loader must not be pointed at this format.
    """
    if not isinstance(expected_sha256, str) or not _SHA.fullmatch(expected_sha256):
        raise ValueError("An exact SHA-256 pin is required")
    path = Path(path)
    metadata = path.stat()
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > MAX_FILE_BYTES:
        raise ValueError("Expected a bounded regular catalog file")
    digest = hashlib.sha256()
    length = 0
    records, seen = [], set()
    with path.open("rb") as file:
        index = 0
        while raw := file.readline(MAX_LINE_BYTES + 1):
            length += len(raw)
            if len(raw) > MAX_LINE_BYTES or length > MAX_FILE_BYTES or index > MAX_ROWS:
                raise ValueError("Operator catalog exceeds reader limits")
            digest.update(raw)
            try:
                decoded = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique)
                if index == 0:
                    if decoded != {"format": FORMAT}:
                        raise ValueError
                else:
                    parsed = _row(decoded)
                    if parsed.key in seen:
                        raise ValueError
                    seen.add(parsed.key)
                    records.append(parsed)
            except (ValueError, RecursionError):
                raise ValueError(f"Invalid operator catalog entry at line {index + 1}") from None
            index += 1
    if digest.hexdigest() != expected_sha256:
        raise ValueError("Operator catalog SHA-256 does not match")
    if not records:
        raise ValueError("Operator catalog contains no descriptions")
    return tuple(records)

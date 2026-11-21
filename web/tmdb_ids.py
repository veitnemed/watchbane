"""Bounded offline queue planner for caller-supplied TMDb Daily ID Exports.

This plans Detail lookups, not a catalog. It never fetches, hydrates, or stores
records. An unverified/missing adult flag is not treated as false.
"""
from dataclasses import asdict, dataclass
from datetime import date
import gzip
from hashlib import sha256
from heapq import heappush, heapreplace
from io import BytesIO
import json
from pathlib import Path
import zlib


MAX_COMPRESSED = 32 * 1024 * 1024
MAX_EXPANDED = 512 * 1024 * 1024
MAX_LINE = 16 * 1024
MAX_ROWS = 5_000_000
MAX_PER_MEDIA = 5000
_PREFIX = {"movie": "movie_ids", "tv": "tv_series_ids"}
_FORMAT = "tmdb-id-plan-v1-sha256-sample"


@dataclass(frozen=True)
class SourceSummary:
    media_type: str
    filename: str
    compressed_sha256: str
    rows: int
    adult_rows: int
    unknown_adult_rows: int


@dataclass(frozen=True)
class QueueItem:
    media_type: str
    tmdb_id: int

    @property
    def key(self) -> str:
        return f"tmdb:{self.media_type}:{self.tmdb_id}"


@dataclass(frozen=True)
class IdPlan:
    date: str
    per_media_limit: int
    sources: tuple[SourceSummary, ...]
    queue: tuple[QueueItem, ...]

    def manifest(self) -> dict:
        return {
            "format": _FORMAT,
            "date": self.date,
            "per_media_limit": self.per_media_limit,
            "sources": [asdict(source) for source in self.sources],
            "queue_sha256": sha256("\n".join(item.key for item in self.queue).encode("ascii")).hexdigest(),
        }

    def require_same_inputs(self, previous_manifest: dict) -> None:
        """Refuse resume if the format, source bytes, cap or derived queue differs."""
        if self.manifest() != previous_manifest:
            raise ValueError("TMDb ID plan differs from the saved manifest; use a new checkpoint")


def _read_source(path: Path, media: str, expected: str, cap: int):
    if path.name != expected or not path.is_file():
        raise ValueError(f"Expected local {expected}")
    with path.open("rb") as source:
        blob = source.read(MAX_COMPRESSED + 1)
    if len(blob) > MAX_COMPRESSED:
        raise ValueError(f"{expected}: compressed size limit exceeded")

    # Keep only the best cap deterministic ranks; ids in the heap are the
    # only dedup state needed, since a discarded rank cannot improve later.
    smallest = []
    selected = set()
    rows = adult = unknown = expanded = 0
    try:
        with gzip.GzipFile(fileobj=BytesIO(blob)) as stream:
            while line := stream.readline(MAX_LINE + 1):
                rows += 1
                expanded += len(line)
                if rows > MAX_ROWS or expanded > MAX_EXPANDED or len(line) > MAX_LINE:
                    raise ValueError(f"{expected}: row, line or expanded size limit exceeded")
                try:
                    row = json.loads(line.decode("utf-8"))
                except (UnicodeError, ValueError, RecursionError):
                    raise ValueError(f"{expected}: invalid UTF-8 JSON on row {rows}") from None
                identifier = row.get("id") if isinstance(row, dict) else None
                if type(identifier) is not int or not 0 < identifier < 2**31:
                    raise ValueError(f"{expected}: invalid TMDb ID on row {rows}")
                if "media_type" in row and row["media_type"] != media:
                    raise ValueError(f"{expected}: conflicting media type on row {rows}")
                if row.get("adult") is True:
                    adult += 1
                    continue
                if row.get("adult") is not False:
                    unknown += 1
                    continue
                if identifier in selected:
                    continue
                score = int.from_bytes(sha256(f"{media}:{identifier}".encode("ascii")).digest())
                item = (-score, -identifier)
                if len(smallest) < cap:
                    heappush(smallest, item)
                elif item > smallest[0]:
                    _, evicted = heapreplace(smallest, item)
                    selected.remove(-evicted)
                else:
                    continue
                selected.add(identifier)
    except (OSError, EOFError, zlib.error):
        raise ValueError(f"{expected}: invalid or truncated gzip") from None
    if not rows:
        raise ValueError(f"{expected}: empty export")
    summary = SourceSummary(media, expected, sha256(blob).hexdigest(), rows, adult, unknown)
    return summary, tuple(QueueItem(media, -identifier) for _, identifier in sorted(smallest, reverse=True))


def plan_daily_ids(
    *, export_date: date, movie_file: Path, tv_file: Path, per_media_limit: int,
) -> IdPlan:
    """Inspect both gzip inputs fully, then return a deterministic typed queue.

    Filenames assert daily/media selection, not origin authenticity. Small or
    empty eligible subsets are honest outcomes; never fill unknown adult rows
    or rebalance unused TV/movie quota into the other kind.
    """
    if type(export_date) is not date:
        raise ValueError("An explicit export calendar date is required")
    if type(per_media_limit) is not int or not 1 <= per_media_limit <= MAX_PER_MEDIA:
        raise ValueError(f"per_media_limit must be an integer from 1 to {MAX_PER_MEDIA}")
    sources, queue = [], []
    for media, path in (("movie", movie_file), ("tv", tv_file)):
        filename = f"{_PREFIX[media]}_{export_date:%m_%d_%Y}.json.gz"
        summary, items = _read_source(Path(path), media, filename, per_media_limit)
        sources.append(summary)
        queue.extend(items)
    return IdPlan(export_date.isoformat(), per_media_limit, tuple(sources), tuple(queue))

"""Private read-only aggregates from a detached hydration checkpoint."""
from collections import Counter
from collections.abc import Mapping
from contextlib import closing
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import sqlite3

from web.tmdb_ids import IdPlan
from web.tmdb_hydration import HYDRATION_STATES


@dataclass(frozen=True)
class ReviewedLanguage:
    """Supplied by an independent review, not inferred from a Details request.

    The reviewed UTF-8 synopsis digest binds the review to the actual stored
    description. A review might use human verification or matching to a
    provider translation record; this helper does not authenticate either.
    """

    synopsis_sha256: str
    language: str  # ru / en / other


def audit_hydration(
    *, plan: IdPlan, checkpoint: Path,
    observed: Mapping[str, ReviewedLanguage] | None = None,
) -> dict:
    """Do not export titles, IDs, digests, or descriptions; report counts only."""
    planned = {i.key: i.media_type for i in plan.queue}
    if len(planned) != len(plan.queue) or any(k not in ("movie", "tv") for k in planned.values()):
        raise ValueError("Invalid typed ID plan")
    observations = observed if observed is not None else {}
    if not observations.keys() <= planned.keys():
        raise ValueError("Language review is outside the typed ID plan")

    by_media = {}
    for media in ("movie", "tv"):
        by_media[media] = {
            "planned": sum(kind == media for kind in planned.values()),
            "pending": 0, **dict.fromkeys(HYDRATION_STATES, 0),
            "requested_locale": {"ru-RU": 0, "en-US": 0},
            "observed_language": {"ru": 0, "en": 0, "other": 0, "unverified": 0},
        }
    manifest = json.dumps(plan.manifest(), sort_keys=True, separators=(",", ":"))
    seen = set()
    with closing(sqlite3.connect(Path(checkpoint).resolve().as_uri() + "?mode=ro", uri=True)) as conn:
        conn.execute("BEGIN")
        if conn.execute("SELECT manifest FROM hydration_plan WHERE singleton=1").fetchone() != (manifest,):
            raise ValueError("Hydration checkpoint differs from the ID plan")
        for media, identifier, status, payload in conn.execute(
            "SELECT media, tmdb_id, status, payload FROM hydration_items"
        ):
            key = f"tmdb:{media}:{identifier}"
            if key not in planned or key in seen or status not in HYDRATION_STATES:
                raise ValueError("Unexpected typed hydration state")
            seen.add(key)
            bucket = by_media[media]
            bucket[status] += 1
            if status != "hydrated":
                if payload is not None or key in observations:
                    raise ValueError("Language review requires a hydrated description")
                continue
            try:
                row = json.loads(payload)
            except (ValueError, TypeError, RecursionError):
                raise ValueError("Invalid hydration description") from None
            if not isinstance(row, dict):
                raise ValueError("Invalid hydration description")
            synopsis = row.get("overview")
            locale = row.get("requested_locale")
            if (type(row.get("tmdb_id")) is not int or row["tmdb_id"] != identifier
                    or row.get("media_type") != media or locale not in ("ru-RU", "en-US")
                    or not isinstance(synopsis, str) or not synopsis.strip()):
                raise ValueError("Invalid hydration description")
            bucket["requested_locale"][locale] += 1
            evidence = observations.get(key)
            language = "unverified"
            if key in observations:
                if (not isinstance(evidence, ReviewedLanguage) or evidence.language not in ("ru", "en", "other")
                        or sha256(synopsis.encode("utf-8")).hexdigest() != evidence.synopsis_sha256):
                    raise ValueError("Language review does not match the stored description")
                language = evidence.language
            bucket["observed_language"][language] += 1
    if not observations.keys() <= seen:
        raise ValueError("Language review requires a hydrated description")

    pending = Counter(planned[k] for k in planned.keys() - seen)
    for media in by_media:
        by_media[media]["pending"] = pending[media]
    return {"by_media": by_media, "distinct_typed_completed": len(seen)}

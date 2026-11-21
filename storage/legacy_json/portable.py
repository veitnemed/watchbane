"""Machine-independent preferences and explicit collection checks for portable exports."""

from math import isfinite

from candidates.models.keys import candidate_typed_state_key
from dataset.models.media_type import MOVIE_MEDIA_TYPE_ALIASES, TV_MEDIA_TYPE_ALIASES
from storage.sqlite.watched_mapper import (
    extract_watched_record,
    metadata_watched_identity,
    metadata_watched_projection,
)


OMITTED_MEMBERS = ("cache/posters/posters.json", "candidates/pool.json", "candidates/criteria.json")


def portable_settings(values: dict) -> dict:
    result = {}
    for key, value in values.items():
        if key in ("interface_language", "data_language"):
            if type(value) is str and value in ("ru", "en"):
                result[key] = value
        elif key == "ui_scale":
            if type(value) in (int, float) and 0.50 <= value <= 2.00 and isfinite(value):
                result[key] = value
        elif key in ("auto_pool_refill", "fts_search_enabled"):
            if type(value) is bool:
                result[key] = value
    return result


def _mapping(value):
    return value if isinstance(value, dict) else {}


def _explicit_media_type(value):
    return isinstance(value, str) and value.strip().casefold() in (
        MOVIE_MEDIA_TYPE_ALIASES | TV_MEDIA_TYPE_ALIASES
    )


def validate_portable_collection(*, watched: dict, meta: dict, watchlist: dict, hidden: dict) -> None:
    """Reject contradictions between explicitly typed TMDb collection records.

    Title/year, IMDb and missing media types are not enough for this check to
    resolve identity. A noncanonical legacy action key is allowed.
    """
    statuses: dict[str, str] = {}

    def remember(identity: str, status: str) -> None:
        previous = statuses.get(identity)
        if previous is not None:
            raise ValueError(
                f"Conflicting typed TMDb collection state in portable export ({previous}, {status}); "
                "resolve duplicate records before transferring"
            )
        statuses[identity] = status

    # Metadata-only rows are not Watched states.
    for key, record in watched.items():
        record = _mapping(record)
        projected = metadata_watched_projection(meta.get(key))
        # Match watched mapper precedence; do not promote its default to
        # explicit evidence when a legacy media type is missing or unknown.
        raw_type = next((value for value in (
            _mapping(record.get("main_info")).get("media_type"),
            _mapping(_mapping(projected).get("main_info")).get("media_type"),
            record.get("media_type"),
        ) if value is not None and not (isinstance(value, str) and not value.strip())), None)
        if _explicit_media_type(raw_type):
            row = extract_watched_record(key, record, meta=projected)
            # The legacy mapper accepts some number-like values more broadly
            # than a stable typed ID. Only use an independently explicit ID,
            # consistent with that projection, as conflict evidence.
            evidence = {
                metadata_watched_identity({
                    "media_type": raw_type,
                    "raw_scores": section,
                })
                for section in (
                    _mapping(record.get("raw_scores")),
                    _mapping(_mapping(projected).get("raw_scores")),
                    record,
                    _mapping(projected),
                )
            } - {None}
            if evidence == {(row.media_type, row.tmdb_id)}:
                remember(f"tmdb:{row.media_type}:{row.tmdb_id}", "Watched")

    for status, actions in (("Saved", watchlist), ("Hidden", hidden)):
        for key, entry in actions.items():
            candidate = _mapping(_mapping(entry).get("candidate"))
            if not _explicit_media_type(candidate.get("media_type")):
                continue
            identity = candidate_typed_state_key(candidate)
            if identity is None:
                continue
            if key.startswith("tmdb:") and key != identity:
                raise ValueError(f"Conflicting typed TMDb action key in portable export ({status})")
            remember(identity, status)

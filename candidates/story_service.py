"""Read local catalog; construct derived profile-local vectors without changing library data."""
from candidates.story_search import StoryDocument, StorySearch
from candidates.models.keys import candidate_typed_state_key, pool_entry_key
from candidates.models.schema import resolve_canonical_year
from candidates.repositories.pool_repository import load_candidate_pool
from candidates.scoring.ranking import rank_candidates
from candidates.search.filtering import candidate_matches, filter_candidates
from candidates.search_service import _prepare_text_search_criteria
from candidates.safety.explicit_content import is_blocked_explicit_sexual_content
from dataset.language import choose_display_overview, choose_display_title
from dataset.models.identity import normalize_title_key
from dataset.models.media_type import normalize_media_type


# One active in-memory index. Unchanged descriptions reuse both vectors and TF-IDF.
# State/data changes produce a different immutable key; explicit refresh clears it.
from collections import Counter, OrderedDict
from threading import RLock
_INDEX_CACHE = OrderedDict()
_INDEX_LOCK = RLock()


def clear_story_search_cache():
    with _INDEX_LOCK:
        _INDEX_CACHE.clear()


def create_story_search(documents, model_dir=None, *, on_progress=None, cancelled=None):
    documents = tuple(documents)
    from storage.profiles import get_active_data_dir
    profile_dir = get_active_data_dir().resolve()
    key = (str(profile_dir), str(model_dir or ""), documents)
    with _INDEX_LOCK:
        if key in _INDEX_CACHE:
            return _INDEX_CACHE[key]
        if on_progress:
            on_progress(f"Индексируем описания: {len(documents)}. Первый поиск может занять больше времени.")
        if not model_dir:
            engine = StorySearch(documents)
        else:
            from candidates.story_semantic import SemanticStorySearch
            from candidates.story_vector_cache import CachedPassageEncoder
            encoder = CachedPassageEncoder(_local_encoder(str(model_dir)), profile_dir)
            engine = SemanticStorySearch(documents, encoder, cancelled=cancelled)
        _INDEX_CACHE.clear()
        _INDEX_CACHE[key] = engine
        return engine


from functools import lru_cache


@lru_cache(maxsize=1)
def _local_encoder(directory):
    from candidates.story_semantic import LocalE5
    return LocalE5(directory)


def local_story_catalog(model_dir=None, *, on_progress=None, cancelled=None, seed_path=None):
    """Index only the chosen real catalogue; an empty profile has no results."""
    documents, records = story_catalog_snapshot(seed_path=seed_path)
    return create_story_search(documents, model_dir if documents else None,
                               on_progress=on_progress, cancelled=cancelled), records


def get_pool_view() -> list[dict]:
    # The shared pool view normalizes by title/year and can hide a persisted
    # homonym, even when two distinct TMDb IDs were stored with opaque keys.
    return list(load_candidate_pool().values())


def _runtime_story_candidates(pool: list[dict]) -> list[dict]:
    if not pool:
        return []
    from storage.sqlite.session import connection

    criteria = _prepare_text_search_criteria({})
    allowed = filter_candidates(pool, dict(criteria, only_unwatched=False))
    known_watched, legacy_watched = set(), Counter()
    conn, owned = connection(None, None)
    try:
        for row in conn.execute(
            """SELECT title_normalized, year, media_type, tmdb_id FROM watched_records
               WHERE payload_json != '{}'"""
        ):
            if key := candidate_typed_state_key(dict(row)):
                known_watched.add(key)
            else:
                legacy_watched[row["title_normalized"], row["year"], row["media_type"]] += 1
    finally:
        if owned:
            conn.close()

    def legacy_identity(candidate):
        title = candidate.get("title") or candidate.get("name") or ""
        return (normalize_title_key(title), resolve_canonical_year(candidate),
                normalize_media_type(candidate.get("media_type")))

    # An old row without an ID may refer to either of two same-title films;
    # never let this ambiguous fallback hide both known identities.
    identities_by_legacy = {}
    for candidate in pool:
        if typed := candidate_typed_state_key(candidate):
            identities_by_legacy.setdefault(legacy_identity(candidate), set()).add(typed)

    eligible = []
    for candidate in allowed:
        typed = candidate_typed_state_key(candidate)
        if typed:
            legacy_key = legacy_identity(candidate)
            unambiguous = len(identities_by_legacy.get(legacy_key, ())) == 1 and legacy_watched[legacy_key] == 1
            if typed in known_watched or unambiguous:
                continue
        elif not candidate_matches(candidate, criteria):
            continue
        eligible.append(candidate)
    return rank_candidates(eligible)


def story_catalog_snapshot(pool=None, *, seed_path=None):
    """Read available descriptions without loading a model or writing an index."""
    if seed_path is not None:
        from candidates.story_seed_snapshot import load_seed_snapshot
        candidates = filter_candidates(list(load_seed_snapshot(seed_path).values()), _prepare_text_search_criteria({}))
    else:
        if pool is None:
            pool = get_pool_view()
        candidates = _runtime_story_candidates(pool)
    records, documents = {}, []
    for candidate in candidates:
        overview = choose_display_overview(candidate, "ru") or ""
        if not overview or is_blocked_explicit_sexual_content(candidate):
            continue
        key = candidate_typed_state_key(candidate) or pool_entry_key(candidate)
        if key in records:
            continue
        records[key] = candidate
        localized = candidate.get("localized") or {}
        fallback = " · английский fallback" if not (localized.get("ru") or {}).get("overview") and (localized.get("en") or {}).get("overview") == overview else ""
        documents.append(StoryDocument(key, choose_display_title(candidate, "ru") or "Без названия",
                         overview, candidate.get("media_type", "movie"),
                         "Локальное описание · " + str(candidate.get("source") or "источник не указан") + fallback,
                         year=int(candidate["year"]) if str(candidate.get("year", "")).isdigit() else None))
    return documents, records

"""Read local catalog; construct derived profile-local vectors without changing library data."""
from candidates.story_search import StoryDocument, StorySearch
from candidates.models.keys import pool_entry_key
from candidates.pool_service import get_pool_view
from candidates.search_service import get_search_filter_view, _prepare_text_search_criteria
from candidates.safety.explicit_content import is_blocked_explicit_sexual_content
from dataset.language import choose_display_overview, choose_display_title


# One active in-memory index. Unchanged descriptions reuse both vectors and TF-IDF.
# State/data changes produce a different immutable key; explicit refresh clears it.
from collections import OrderedDict
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


def local_story_catalog(model_dir=None, *, auto_demo=False, on_progress=None, cancelled=None):
    pool = get_pool_view()
    if auto_demo and not pool:
        from candidates.story_demo import demo_documents
        return create_story_search(demo_documents(), model_dir, on_progress=on_progress, cancelled=cancelled), {}
    documents, records = story_catalog_snapshot(pool)
    return create_story_search(documents, model_dir, on_progress=on_progress, cancelled=cancelled), records


def story_catalog_snapshot(pool=None):
    """Read available descriptions without loading a model or writing an index."""
    if pool is None:
        pool = get_pool_view()
    candidates = get_search_filter_view(pool, _prepare_text_search_criteria({}))["candidates"]
    records, documents = {}, []
    for candidate in candidates:
        overview = choose_display_overview(candidate, "ru") or ""
        if not overview or is_blocked_explicit_sexual_content(candidate):
            continue
        key = pool_entry_key(candidate)
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

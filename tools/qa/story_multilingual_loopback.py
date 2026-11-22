"""Detached opt-in multilingual comparison. Not the product server or a catalog source."""

from dataclasses import dataclass
from functools import partial
from hashlib import sha256
from pathlib import Path
from threading import Lock

from candidates.safety.explicit_content import is_blocked_explicit_sexual_content
from candidates.story_search import StoryDocument
from candidates.story_seed_snapshot import MAX_ROWS, load_seed_snapshot_with_digest
from candidates.story_semantic import LocalE5, SemanticStorySearch
from candidates.story_vector_cache import PREPROCESS_VERSION
from web.story_api import _load_documents, _StartupPassageEncoder, _read_query
from web.story_catalog_multilingual import load_operator_catalog
from web.story_vector_snapshot import PassageVectorSnapshot, SnapshotIdentity


@dataclass(frozen=True)
class NonAdultReview:
    """Caller-supplied review tied to the exact source artifact and text.

    This record is an assertion from the authorized QA operator, not proof
    issued by TMDb. V1 contains no provider adult/rating evidence. A real-data
    caller would need an independently reviewed source and intended-use
    clearance before creating any such records; this tool acquires neither.
    """
    operator_sha256: str
    key: str
    synopsis_locale: str
    synopsis_sha256: str
    reviewed_non_adult: bool


def project_mixed_documents(baseline, operator_catalog, operator_sha256, reviews):
    # Baseline rows are authoritative and unchanged. A translated description
    # with the same typed ID can never replace a baseline description.
    documents, baseline_sha = _load_documents(baseline)
    if not documents:
        raise ValueError("The QA comparison requires a nonempty Russian baseline")
    baseline_keys = {doc.key for doc in documents}
    raw_baseline, raw_sha = load_seed_snapshot_with_digest(baseline)
    if raw_sha != baseline_sha:
        raise ValueError("Russian baseline changed while building comparison")
    # An EN row cannot restore a disallowed typed ID or override even a
    # blocked RU description. The baseline raw key set is not exposed.
    reserved = {key for key, row in raw_baseline.items()
                if "ru" in row["localized"] or is_blocked_explicit_sexual_content(row)}
    rows = load_operator_catalog(operator_catalog, expected_sha256=operator_sha256)
    eligible = {row.key: row for row in rows if row.synopsis_locale == "en-US" and row.key not in reserved}
    permitted = set()
    for review in reviews:
        if (not isinstance(review, NonAdultReview) or review.reviewed_non_adult is not True
                or type(review.key) is not str):
            raise ValueError("English descriptions require an independent non-adult review")
        row = eligible.get(review.key)
        if (row is None or review.key in permitted or review.operator_sha256 != operator_sha256
                or review.synopsis_locale != row.synopsis_locale
                or review.synopsis_sha256 != row.synopsis_sha256):
            raise ValueError("Review does not match the exact English description")
        if is_blocked_explicit_sexual_content({"title": row.title, "overview": row.overview}):
            raise ValueError("The reviewed description failed the existing text safety gate")
        permitted.add(row.key)
    if not permitted or len(documents) + len(permitted) > MAX_ROWS:
        raise ValueError("The QA comparison requires a bounded, nonempty additive English lane")
    locales = dict.fromkeys(baseline_keys, "ru-RU")
    for key, row in eligible.items():
        if key in permitted:
            locales[key] = row.synopsis_locale
            documents.append(StoryDocument(key, row.title, row.overview, row.media_type, "TMDb", year=row.year))
    # A mixed snapshot is a distinct cache generation even when a baseline
    # digest or any individual selected description is reused.
    digest = sha256(b"watchbane-mixed-qa-v1\0" + bytes.fromhex(baseline_sha) + bytes.fromhex(operator_sha256))
    return tuple(documents), locales, digest.hexdigest()


def create_mixed_qa_app(*, baseline, operator_catalog, operator_sha256, reviews, model_dir, cache_dir=None,
                        encoder_factory=LocalE5):
    """Explicit comparison app serving only a separate QA URL over loopback.

    No product /v1/search route, Qt wiring, downloads, profiles or auto-mode.
    A native launcher (if used by an operator) must bind to a loopback address with forwarded headers disabled.
    """
    from contextlib import asynccontextmanager
    import ipaddress
    from fastapi import FastAPI, HTTPException, Request
    from starlette.concurrency import run_in_threadpool

    def build():
        documents, locales, digest = project_mixed_documents(baseline, operator_catalog, operator_sha256, reviews)
        encoder = encoder_factory(model_dir)
        cache = None
        identity = None
        if cache_dir is not None:
            cache = PassageVectorSnapshot(Path(cache_dir) / "mixed_qa_v1")
            identity = SnapshotIdentity.from_documents(
                digest, encoder.cache_identity, documents, preprocessing=f"{PREPROCESS_VERSION}:mixed-qa-v1",
            )
        startup = _StartupPassageEncoder(encoder, cache, identity, documents, startup_batch_size=4)
        return SemanticStorySearch(documents, startup), locales

    @asynccontextmanager
    async def lifespan(app):
        app.state.engine, app.state.locales = await run_in_threadpool(build)
        try:
            yield
        finally:
            del app.state.engine
            del app.state.locales

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)

    search_slot = Lock()

    @app.middleware("http")
    async def no_store_search(request: Request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.post("/qa/v1/search")
    async def search(request: Request):
        try:
            local = request.client is not None and ipaddress.ip_address(request.client.host).is_loopback
        except ValueError:
            local = False
        if not local:
            raise HTTPException(403, "loopback_only")
        query, limit = await _read_query(request)
        if not search_slot.acquire(blocking=False):
            raise HTTPException(503, "search_busy")
        try:
            result = await run_in_threadpool(partial(app.state.engine.search, query, limit=limit))
            payload = {
                "source": "tmdb", "mode": "operator_multilingual_qa",
                "results": [{
                    "id": hit.document.key, "media_type": hit.document.media_type,
                    "language": app.state.locales[hit.document.key],
                    "title": hit.document.title, "overview": hit.document.overview,
                } for hit in result.hits],
            }
        except Exception:
            raise HTTPException(503, "search_unavailable") from None
        finally:
            search_slot.release()
        return payload

    return app

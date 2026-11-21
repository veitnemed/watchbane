"""Loopback-only first server slice; approved local catalog, no desktop profile."""
from __future__ import annotations

import argparse
from contextlib import asynccontextmanager
import json
from pathlib import Path
from threading import Lock

from fastapi import FastAPI, HTTPException, Request, Response
from starlette.concurrency import run_in_threadpool
from starlette.requests import ClientDisconnect

from candidates.safety.explicit_content import is_blocked_explicit_sexual_content
from candidates.story_search import StoryDocument
from candidates.story_seed_snapshot import load_seed_snapshot_with_digest
from candidates.story_semantic import LocalE5, SemanticStorySearch

_MAX_BODY = 8192
_MAX_QUERY = 600
_MAX_RESULTS = 10


class _StartupPassageEncoder:
    """The initial, exact document batch is the only persistable call."""

    def __init__(self, encoder, cache, identity, documents):
        self.encoder, self.cache, self.identity = encoder, cache, identity
        self.expected = tuple(doc.overview for doc in documents)
        self.variant = encoder.variant

    def encode(self, texts, prefix="passage: ", **kwargs):
        expected, self.expected = self.expected, None
        if expected is None or prefix != "passage: " or tuple(texts) != expected:
            return self.encoder.encode(texts, prefix=prefix, **kwargs)
        matrix = self.cache.load(self.identity)
        if matrix is not None:
            return matrix
        matrix = self.encoder.encode(texts, prefix=prefix, **kwargs)
        try:
            self.cache.save(self.identity, matrix)
        except OSError:
            # Cache is optional and never the source of truth.
            pass
        return matrix


def build_engine(catalog: Path, model_dir: Path, *, cache_dir: Path | None = None, prepared_index: bool = False):
    """Index the approved snapshot; persistence is an explicit operator option."""
    snapshot, catalog_sha = load_seed_snapshot_with_digest(catalog)
    documents = []
    for key, row in snapshot.items():
        russian = row["localized"].get("ru")
        if russian is None or is_blocked_explicit_sexual_content(row):
            continue
        documents.append(StoryDocument(key, russian["title"], russian["overview"],
                                       row["media_type"], "TMDb", year=row["year"]))
    if not documents:
        raise ValueError("The configured TMDb snapshot has no eligible Russian descriptions.")
    encoder = LocalE5(model_dir)  # Always verify model artifacts, even on a cache hit.
    if cache_dir is not None:
        from web.story_vector_snapshot import PassageVectorSnapshot, SnapshotIdentity

        identity = SnapshotIdentity.from_documents(catalog_sha, encoder.cache_identity, documents)
        encoder = _StartupPassageEncoder(encoder, PassageVectorSnapshot(cache_dir), identity, documents)
    if prepared_index:
        from web.story_retrieval_index import PreparedRetrievalIndex

        return SemanticStorySearch(documents, encoder, retrieval_factory=PreparedRetrievalIndex)
    return SemanticStorySearch(documents, encoder)


async def _read_query(request: Request):
    if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/json":
        raise HTTPException(415, "expected_json")
    body = bytearray()
    try:
        async for part in request.stream():
            if len(body) + len(part) > _MAX_BODY:
                raise HTTPException(413, "request_too_large")
            body.extend(part)
        value = json.loads(body)
        if not isinstance(value, dict) or set(value) - {"query", "limit"}:
            raise ValueError
        query, limit = value.get("query"), value.get("limit", 5)
        if not isinstance(query, str) or not query.strip() or len(query) > _MAX_QUERY:
            raise ValueError
        query.encode("utf-8")
        if type(limit) is not int or not 1 <= limit <= _MAX_RESULTS:
            raise ValueError
    except (ValueError, RecursionError, ClientDisconnect):
        raise HTTPException(400, "invalid_search_request") from None
    return query.strip(), limit



_OUTCOME_HEADER = "Watchbane-Search-Outcome"


def _search_outcome(result):
    if result.hits:
        return {"state": "candidates", "reason": "possible_local_results"}
    reason = getattr(result, "reason", None)
    if reason == "explicit_non_film_request":
        return {"state": "scope_refusal", "reason": reason}
    if reason in ("no_filtered_descriptions", "no_eligible_catalog_entries"):
        reason = "no_eligible_catalog_entries"
    elif reason not in ("unsupported_exclusion", "need_plot_detail"):
        reason = "no_candidates"
    return {"state": "clarification", "reason": reason}

def create_app(catalog: Path, model_dir: Path, *, engine_factory=build_engine, cache_dir: Path | None = None,
               prepared_index: bool = False):
    """One verified engine per worker; tests may inject a local engine factory."""
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        options = {} if cache_dir is None else {"cache_dir": cache_dir}
        if prepared_index:
            options["prepared_index"] = True
        engine = await run_in_threadpool(engine_factory, catalog, model_dir, **options)
        app.state.engine = engine
        try:
            yield
        finally:
            del app.state.engine

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    search_slot = Lock()

    @app.middleware("http")
    async def no_store_search(request: Request, call_next):
        response = await call_next(request)
        if request.url.path == "/v1/search":
            response.headers["Cache-Control"] = "no-store"
            response.headers.append("Vary", _OUTCOME_HEADER)
        return response

    @app.get("/healthz")
    def health():
        return {"ready": True}

    @app.post("/v1/search")
    async def search(request: Request, response: Response):
        versions = request.headers.getlist(_OUTCOME_HEADER)
        if versions and versions != ["1"]:
            raise HTTPException(400, "unsupported_search_outcome_version")
        query, limit = await _read_query(request)
        if not search_slot.acquire(blocking=False):
            raise HTTPException(503, "search_busy", headers={"Retry-After": "1"})
        try:
            engine = app.state.engine
            search_query = getattr(engine, "search_with_outcome", engine.search) if versions else engine.search
            result = await run_in_threadpool(search_query, query, limit=limit)
            payload = {
                "source": "tmdb",
                "results": [{
                    "id": hit.document.key,
                    "media_type": hit.document.media_type,
                    "title": hit.document.title,
                    "year": hit.document.year,
                    "overview": hit.document.overview,
                    "evidence": hit.evidence,
                    "language": "ru-RU",
                } for hit in result.hits],
            }
            if versions:
                payload["outcome"] = _search_outcome(result)
                response.headers[_OUTCOME_HEADER] = "1"
            return payload
        except Exception:
            # Do not put search text, provider data, or an exception containing
            # either into server logs or a response body.
            raise HTTPException(503, "search_unavailable") from None
        finally:
            search_slot.release()

    return app


def main(argv=None):
    import uvicorn

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--cache-dir", type=Path, help="Explicit detached server passage cache")
    parser.add_argument("--prepared-index", action="store_true", help="Opt in to exact prepared retrieval")
    args = parser.parse_args(argv)
    uvicorn.run(create_app(args.catalog, args.model_dir, cache_dir=args.cache_dir,
                          prepared_index=args.prepared_index), host="127.0.0.1",
                port=args.port, access_log=False, proxy_headers=False)


if __name__ == "__main__":
    main()

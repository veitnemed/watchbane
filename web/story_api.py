"""Loopback-only first server slice; approved local catalog, no desktop profile."""
from __future__ import annotations

import argparse
from contextlib import asynccontextmanager
import json
from pathlib import Path
from threading import Lock

from fastapi import FastAPI, HTTPException, Request
from starlette.concurrency import run_in_threadpool
from starlette.requests import ClientDisconnect

from candidates.safety.explicit_content import is_blocked_explicit_sexual_content
from candidates.story_search import StoryDocument
from candidates.story_seed_snapshot import load_seed_snapshot
from candidates.story_semantic import LocalE5, SemanticStorySearch

_MAX_BODY = 8192
_MAX_QUERY = 600
_MAX_RESULTS = 10


def build_engine(catalog: Path, model_dir: Path):
    """Verify and index the configured snapshot once; never write a profile/cache."""
    documents = []
    for key, row in load_seed_snapshot(catalog).items():
        russian = row["localized"].get("ru")
        if russian is None or is_blocked_explicit_sexual_content(row):
            continue
        documents.append(StoryDocument(key, russian["title"], russian["overview"],
                                       row["media_type"], "TMDb", year=row["year"]))
    if not documents:
        raise ValueError("The configured TMDb snapshot has no eligible Russian descriptions.")
    return SemanticStorySearch(documents, LocalE5(model_dir))


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


def create_app(catalog: Path, model_dir: Path, *, engine_factory=build_engine):
    """One verified engine per worker; tests may inject a local engine factory."""
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        engine = await run_in_threadpool(engine_factory, catalog, model_dir)
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
        return response

    @app.get("/healthz")
    def health():
        return {"ready": True}

    @app.post("/v1/search")
    async def search(request: Request):
        query, limit = await _read_query(request)
        if not search_slot.acquire(blocking=False):
            raise HTTPException(503, "search_busy", headers={"Retry-After": "1"})
        try:
            result = await run_in_threadpool(app.state.engine.search, query, limit=limit)
            return {
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
    args = parser.parse_args(argv)
    uvicorn.run(create_app(args.catalog, args.model_dir), host="127.0.0.1",
                port=args.port, access_log=False, proxy_headers=False)


if __name__ == "__main__":
    main()

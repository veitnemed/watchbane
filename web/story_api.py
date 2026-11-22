"""Loopback-only first server slice; approved local catalog, no desktop profile."""
from __future__ import annotations

import argparse
from contextlib import asynccontextmanager
import json
from pathlib import Path
import re
from threading import Lock

from fastapi import FastAPI, HTTPException, Request, Response
from starlette.concurrency import run_in_threadpool
from starlette.requests import ClientDisconnect

from candidates.safety.explicit_content import is_blocked_explicit_sexual_content
from candidates.story_search import StoryDocument
from candidates.story_artwork import is_provider_poster_path
from candidates.story_seed_snapshot import MAX_ROWS, StorySeedSnapshotError, load_seed_snapshot_with_digest
from candidates.story_semantic import DEFAULT_E5_BATCH_SIZE, LocalE5, SemanticStorySearch, validate_e5_batch_size
from candidates.story_vector_cache import PREPROCESS_VERSION
from web.story_local_rate import LocalRateBudget, local_rate_config

_MAX_BODY = 8192
_MAX_QUERY = 600
_MAX_RESULTS = 10


class _StartupPassageEncoder:
    """The initial, exact document batch is the only persistable call."""

    def __init__(self, encoder, cache, identity, documents, previous_catalog=None,
                 startup_batch_size=DEFAULT_E5_BATCH_SIZE, expected_snapshot_sha256=None):
        self.encoder, self.cache, self.identity = encoder, cache, identity
        self.expected = tuple(doc.overview for doc in documents)
        self.documents, self.previous_catalog = documents, previous_catalog
        self.variant = encoder.variant
        self.startup_batch_size = startup_batch_size
        self.expected_snapshot_sha256 = expected_snapshot_sha256

    def encode(self, texts, prefix="passage: ", **kwargs):
        expected, self.expected = self.expected, None
        if expected is not None and self.expected_snapshot_sha256 is not None:
            if prefix != "passage: " or tuple(texts) != expected:
                raise ValueError("Strict cached startup requires the exact initial passage batch.")
            verified = self.cache.load_with_digest(self.identity)
            if verified is None or verified[1] != self.expected_snapshot_sha256:
                raise ValueError("Required passage snapshot missing, invalid, or SHA-256 mismatch.")
            return verified[0]
        if expected is None or prefix != "passage: " or tuple(texts) != expected:
            return self.encoder.encode(texts, prefix=prefix, **kwargs)
        if self.startup_batch_size != DEFAULT_E5_BATCH_SIZE:
            kwargs["batch_size"] = self.startup_batch_size
        if self.cache is None:
            return self.encoder.encode(texts, prefix=prefix, **kwargs)
        matrix = self.cache.load(self.identity)
        if matrix is not None:
            return matrix
        if self.previous_catalog is not None:
            try:
                previous, digest = _load_documents(self.previous_catalog)
                if previous:
                    from web.story_incremental_passages import reuse_verified_passages
                    from web.story_vector_snapshot import SnapshotIdentity

                    identity = SnapshotIdentity.from_documents(digest, self.encoder.cache_identity, previous,
                                                              preprocessing=self.identity.preprocessing)
                    return reuse_verified_passages(
                        self.cache, current_identity=self.identity, current_documents=self.documents,
                        previous_identity=identity, previous_documents=previous,
                        encode=lambda descriptions: self.encoder.encode(descriptions, prefix=prefix, **kwargs),
                    ).matrix
            except (StorySeedSnapshotError, OSError):
                # A missing/invalid previous source or failed optional cache write
                # must not prevent a full current-catalog rebuild.
                pass
        matrix = self.encoder.encode(texts, prefix=prefix, **kwargs)
        try:
            self.cache.save(self.identity, matrix)
        except OSError:
            # Cache is optional and never the source of truth.
            pass
        return matrix


def _load_documents(catalog, *, artwork_paths=None):
    snapshot, catalog_sha = load_seed_snapshot_with_digest(catalog)
    documents = []
    for key, row in snapshot.items():
        russian = row["localized"].get("ru")
        if russian is None or is_blocked_explicit_sexual_content(row):
            continue
        documents.append(StoryDocument(key, russian["title"], russian["overview"],
                                       row["media_type"], "TMDb", year=row["year"]))
        if artwork_paths is not None and is_provider_poster_path(row.get("poster_path")):
            artwork_paths[key] = row["poster_path"]
    return documents, catalog_sha


def _startup_passage_identity(catalog_sha, encoder, documents, startup_batch_size):
    from web.story_vector_snapshot import SnapshotIdentity

    preprocessing = PREPROCESS_VERSION
    if startup_batch_size != DEFAULT_E5_BATCH_SIZE:
        preprocessing += f":startup-batch={startup_batch_size}"
    return SnapshotIdentity.from_documents(catalog_sha, encoder.cache_identity, documents,
                                           preprocessing=preprocessing)


def _strict_startup_requested(cache_dir, previous_catalog, catalog_pin, snapshot_pin):
    if catalog_pin is None and snapshot_pin is None:
        return False
    if (cache_dir is None or previous_catalog is not None
            or any(not isinstance(pin, str) or re.fullmatch(r"[0-9a-f]{64}", pin) is None
                   for pin in (catalog_pin, snapshot_pin))):
        raise ValueError("Strict startup requires both SHA-256 pins and a cache directory, without a previous catalog.")
    return True


def build_engine(catalog: Path, model_dir: Path, *, cache_dir: Path | None = None, prepared_index: bool = False,
                 previous_catalog: Path | None = None, startup_batch_size: int = DEFAULT_E5_BATCH_SIZE,
                 artwork_paths: dict | None = None, skip_singleton_evidence: bool = False,
                 expected_catalog_sha256: str | None = None, expected_snapshot_sha256: str | None = None):
    """Index the approved snapshot; persistence is an explicit operator option."""
    validate_e5_batch_size(startup_batch_size)
    if previous_catalog is not None and cache_dir is None:
        raise ValueError("A previous catalog requires an explicit cache directory.")
    strict = _strict_startup_requested(cache_dir, previous_catalog, expected_catalog_sha256,
                                       expected_snapshot_sha256)
    try:
        documents, catalog_sha = _load_documents(catalog, artwork_paths=artwork_paths)
    except StorySeedSnapshotError:
        if strict:
            raise ValueError("Strict startup requires a valid local catalog.") from None
        raise
    if strict and catalog_sha != expected_catalog_sha256:
        raise ValueError("Catalog SHA-256 mismatch.")
    if not documents:
        raise ValueError("The configured TMDb snapshot has no eligible Russian descriptions.")
    if strict and (Path(cache_dir).is_symlink() or not Path(cache_dir).is_dir()
                   or not (Path(model_dir) / "onnx/model.onnx").is_file()):
        raise ValueError("Strict startup requires an existing cache directory and local FP32 files.")
    try:
        encoder = LocalE5(model_dir)  # Always verify model artifacts, even on a cache hit.
    except Exception:
        if strict:
            raise ValueError("Strict startup could not verify the local FP32 model.") from None
        raise
    if strict and encoder.variant != "fp32":
        raise ValueError("Strict startup requires the verified local FP32 model.")
    if cache_dir is not None:
        from web.story_vector_snapshot import PassageVectorSnapshot

        identity = _startup_passage_identity(catalog_sha, encoder, documents, startup_batch_size)
        encoder = _StartupPassageEncoder(encoder, PassageVectorSnapshot(cache_dir), identity, documents,
                                         previous_catalog=previous_catalog, startup_batch_size=startup_batch_size,
                                         expected_snapshot_sha256=expected_snapshot_sha256)
    elif startup_batch_size != DEFAULT_E5_BATCH_SIZE:
        encoder = _StartupPassageEncoder(encoder, None, None, documents, startup_batch_size=startup_batch_size)
    extra = {"skip_singleton_evidence": True} if skip_singleton_evidence else {}
    if prepared_index:
        from web.story_retrieval_index import PreparedRetrievalIndex

        return SemanticStorySearch(documents, encoder, retrieval_factory=PreparedRetrievalIndex, **extra)
    return SemanticStorySearch(documents, encoder, **extra)


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
_ARTWORK_HEADER = "Watchbane-Search-Artwork"
_INDEX_HEADER = "Watchbane-Search-Index"
_INDEX_KEY = re.compile(r"tmdb:(movie|tv):([1-9][0-9]{0,18})", re.ASCII)


def _index_counts(engine):
    """Count the immutable engine's exact typed rows, not JSONL/API totals."""
    documents = getattr(engine, "documents", None)
    if not isinstance(documents, tuple) or not 1 <= len(documents) <= MAX_ROWS:
        return None
    counts = {"total": len(documents), "movies": 0, "tv": 0}
    seen = set()
    for document in documents:
        key = getattr(document, "key", None)
        match = _INDEX_KEY.fullmatch(key) if type(key) is str else None
        if (match is None or match[1] != getattr(document, "media_type", None)
                or int(match[2]) > (1 << 63) - 1 or key in seen):
            return None
        seen.add(key)
        counts["movies" if match[1] == "movie" else "tv"] += 1
    return counts


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
               prepared_index: bool = False, previous_catalog: Path | None = None,
               startup_batch_size: int = DEFAULT_E5_BATCH_SIZE, artwork_metadata: bool = False,
               index_metadata: bool = False, skip_singleton_evidence: bool = False,
               expected_catalog_sha256: str | None = None,
               expected_snapshot_sha256: str | None = None,
               local_rate_per_minute: int | None = None, local_rate_burst: int | None = None):
    """One verified engine per worker; tests may inject a local engine factory.

    The optional search rate budget is per process, off by default, and only
    intended for this loopback lab; it is not a public ingress control.
    """
    validate_e5_batch_size(startup_batch_size)
    if previous_catalog is not None and cache_dir is None:
        raise ValueError("A previous catalog requires an explicit cache directory.")
    strict = _strict_startup_requested(cache_dir, previous_catalog, expected_catalog_sha256,
                                       expected_snapshot_sha256)
    rate = local_rate_config(local_rate_per_minute, local_rate_burst)
    rate_budget = LocalRateBudget(*rate) if rate is not None else None

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        options = {} if cache_dir is None else {"cache_dir": cache_dir}
        if strict:
            options.update(expected_catalog_sha256=expected_catalog_sha256,
                           expected_snapshot_sha256=expected_snapshot_sha256)
        if prepared_index:
            options["prepared_index"] = True
        if skip_singleton_evidence:
            options["skip_singleton_evidence"] = True
        if previous_catalog is not None:
            options["previous_catalog"] = previous_catalog
        if startup_batch_size != DEFAULT_E5_BATCH_SIZE:
            options["startup_batch_size"] = startup_batch_size
        artwork_paths = {}
        if artwork_metadata:
            options["artwork_paths"] = artwork_paths
        engine = await run_in_threadpool(engine_factory, catalog, model_dir, **options)
        app.state.artwork_paths = artwork_paths
        app.state.index_counts = await run_in_threadpool(_index_counts, engine) if index_metadata else None
        app.state.engine = engine
        try:
            yield
        finally:
            del app.state.engine
            del app.state.artwork_paths
            del app.state.index_counts

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    search_slot = Lock()

    @app.middleware("http")
    async def no_store_search(request: Request, call_next):
        response = await call_next(request)
        if request.url.path == "/v1/search":
            response.headers["Cache-Control"] = "no-store"
            vary = f"{_OUTCOME_HEADER}, {_ARTWORK_HEADER}"
            if index_metadata:
                vary += f", {_INDEX_HEADER}"
            response.headers.append("Vary", vary)
        return response

    @app.get("/healthz")
    def health():
        return {"ready": True}

    @app.post("/v1/search")
    async def search(request: Request, response: Response):
        versions = request.headers.getlist(_OUTCOME_HEADER)
        if versions and versions != ["1"]:
            raise HTTPException(400, "unsupported_search_outcome_version")
        artwork_versions = request.headers.getlist(_ARTWORK_HEADER)
        if artwork_versions and artwork_versions != ["1"]:
            raise HTTPException(400, "unsupported_search_artwork_version")
        index_versions = request.headers.getlist(_INDEX_HEADER)
        if index_versions and index_versions != ["1"]:
            raise HTTPException(400, "unsupported_search_index_version")
        if index_versions and app.state.index_counts is None:
            raise HTTPException(503, "search_index_unavailable")
        query, limit = await _read_query(request)
        # Opt-in lab policy: charge valid attempts before the independent
        # single-flight gate. With no token, 429 takes precedence; otherwise
        # an occupied worker yields the existing 503 and the token is spent.
        if rate_budget is not None:
            retry_after = rate_budget.retry_after()
            if retry_after is not None:
                raise HTTPException(429, "search_rate_limited", headers={"Retry-After": str(retry_after)})
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
            if artwork_versions:
                mapping = app.state.artwork_paths
                payload["artwork"] = {
                    row["id"]: mapping[row["id"]] for row in payload["results"]
                    if is_provider_poster_path(mapping.get(row["id"]))
                }
                response.headers[_ARTWORK_HEADER] = "1"
            if index_versions:
                payload["index"] = app.state.index_counts
                response.headers[_INDEX_HEADER] = "1"
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
    parser.add_argument("--prepared-index", action="store_true", help="Opt in to prepared exhaustive retrieval")
    parser.add_argument("--previous-catalog", type=Path, help="Optional previous approved snapshot for passage reuse")
    parser.add_argument("--expected-catalog-sha256", help="Strict local startup: require exact approved JSONL bytes")
    parser.add_argument("--expected-snapshot-sha256", help="Strict local startup: require exact prebuilt cache bytes")
    parser.add_argument("--startup-passage-batch-size", type=int, default=DEFAULT_E5_BATCH_SIZE,
                        help="Maximum E5 batch for initial passages only (1–16)")
    parser.add_argument("--artwork-metadata", action="store_true", help="Allow negotiated relative TMDb poster metadata")
    parser.add_argument("--skip-singleton-evidence", action="store_true",
                        help="Experimental QA: skip E5 explanation when only one sentence exists")
    parser.add_argument("--index-metadata", action="store_true", help="Allow negotiated exact indexed-description counts")
    parser.add_argument("--local-rate-per-minute", type=int,
                        help="Opt-in loopback lab budget, 1–3600 valid attempts per minute; spent before busy admission")
    parser.add_argument("--local-rate-burst", type=int,
                        help="Optional 1–60 token burst (default: min(rate, 5)); requires local-rate-per-minute")
    args = parser.parse_args(argv)
    try:
        validate_e5_batch_size(args.startup_passage_batch_size)
        local_rate_config(args.local_rate_per_minute, args.local_rate_burst)
        _strict_startup_requested(args.cache_dir, args.previous_catalog, args.expected_catalog_sha256,
                                  args.expected_snapshot_sha256)
    except ValueError as error:
        parser.error(str(error))
    if args.previous_catalog is not None and args.cache_dir is None:
        parser.error("--previous-catalog requires --cache-dir")
    uvicorn.run(create_app(args.catalog, args.model_dir, cache_dir=args.cache_dir,
                          prepared_index=args.prepared_index, previous_catalog=args.previous_catalog,
                          startup_batch_size=args.startup_passage_batch_size,
                          artwork_metadata=args.artwork_metadata, index_metadata=args.index_metadata,
                          skip_singleton_evidence=args.skip_singleton_evidence,
                          expected_catalog_sha256=args.expected_catalog_sha256,
                          expected_snapshot_sha256=args.expected_snapshot_sha256,
                          local_rate_per_minute=args.local_rate_per_minute,
                          local_rate_burst=args.local_rate_burst), host="127.0.0.1",
                port=args.port, access_log=False, proxy_headers=False)


if __name__ == "__main__":
    main()

"""Disposable loopback QA child: prove application startup serves from a valid passage snapshot."""
from contextlib import asynccontextmanager
from pathlib import Path
import sys


def guard(proof, model, snapshot):
    """Keep the real loader/model; reject fallback startup and record the load witness."""
    load, encode = snapshot.load, model.encode
    hit = None
    ready = False

    def require_hit(self, identity):
        nonlocal hit
        if hit is not None:
            raise RuntimeError("expected exactly one passage snapshot load")
        matrix = load(self, identity)
        if matrix is None:
            raise RuntimeError("valid matching passage snapshot required for restart lab")
        hit = identity, matrix
        return matrix

    def guarded_encode(self, *args, **kwargs):
        if not ready:
            raise RuntimeError("E5 encoding during verified cached startup is forbidden")
        return encode(self, *args, **kwargs)

    def startup_finished(engine):
        nonlocal ready
        if hit is None or engine.vectors is not hit[1]:
            raise RuntimeError("server did not use the matching loaded passage snapshot")
        with proof.open("x", encoding="ascii") as marker:
            marker.write(hit[0].fingerprint().hex())
        ready = True

    return require_hit, guarded_encode, startup_finished


def main(argv=None):
    args = sys.argv[1:] if argv is None else list(argv)
    proof, *server_args = args
    from web import story_api
    from web.story_vector_snapshot import PassageVectorSnapshot

    load, encode, finish = guard(Path(proof), story_api.LocalE5, PassageVectorSnapshot)
    PassageVectorSnapshot.load, story_api.LocalE5.encode = load, encode
    create_app = story_api.create_app

    def witnessed_app(*app_args, **kwargs):
        app = create_app(*app_args, **kwargs)
        lifespan = app.router.lifespan_context

        @asynccontextmanager
        async def witnessed_lifespan(app):
            async with lifespan(app) as state:
                finish(app.state.engine)
                yield state

        app.router.lifespan_context = witnessed_lifespan
        return app

    story_api.create_app = witnessed_app
    return story_api.main(server_args)


if __name__ == "__main__":
    main()

"""No live requests: exercise the real guarded transport with a fake opener."""
from contextlib import closing
from datetime import date
import gzip
import io
import json
import sqlite3
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit

import pytest

from apis.tmdb.detached_transport import DetachedTmdbTransport
from web.tmdb_hydration import hydrate_id_plan
from web.tmdb_ids import plan_daily_ids


def _plan(root, cap=2):
    movie = root / "movie_ids_01_02_2026.json.gz"
    tv = root / "tv_series_ids_01_02_2026.json.gz"
    for path in (movie, tv):
        path.write_bytes(gzip.compress(b'{"id":41,"adult":false}\n'))
    return plan_daily_ids(export_date=date(2026, 1, 2), movie_file=movie, tv_file=tv, per_media_limit=cap)


def _transport(cap, transcript, *, mode=None, cancelled=lambda: False):
    def opener(request, *, timeout):
        target = urlsplit(request.full_url)
        route = target.path.removeprefix("/3")
        locale = parse_qs(target.query)["language"][0]
        transcript.append((route, locale))
        movie = route.startswith("/movie/")
        row = {"id": 41, "adult": False, "title" if movie else "name": "Fixture",
               "release_date" if movie else "first_air_date": "2025-01-02",
               "overview": "Fixture synopsis" if movie or locale == "en-US" else "",
               "irrelevant_fixture_marker": "discard me"}
        if not movie and locale == "en-US":
            if mode == "throttle":
                raise HTTPError(request.full_url, 429, "too many requests", {}, io.BytesIO())
            if mode == "wrong_type":
                row["media_type"] = "movie"
            if mode == "wrong_id":
                row["id"] = True
            if mode == "missing":
                row["overview"] = ""
        if not movie and mode == "unknown_adult":
            del row["adult"]
        return io.BytesIO(json.dumps(row).encode())
    return DetachedTmdbTransport(cap, bearer=lambda: "fictional-test-marker",
                                 opener=opener, cancelled=cancelled)


def _run(plan, db, cap=20, *, mode=None):
    transcript = []
    result = hydrate_id_plan(plan=plan, checkpoint=db, transport=_transport(cap, transcript, mode=mode))
    return result, transcript


def _rows(db):
    with closing(sqlite3.connect(db)) as conn:
        return conn.execute("SELECT * FROM hydration_items ORDER BY media").fetchall()


@pytest.mark.parametrize(("mode", "cap", "reason", "charges"), [
    (None, 2, "budget_exhausted", 2), ("throttle", 20, "throttled", 3),
])
def test_completed_typed_title_stays_unchanged_after_stop_and_resume(tmp_path, mode, cap, reason, charges):
    plan, db = _plan(tmp_path), tmp_path / "detached.sqlite"
    result, launches = _run(plan, db, cap, mode=mode)
    expected = [("/movie/41", "ru-RU"), ("/tv/41", "ru-RU"), ("/tv/41", "en-US")]
    assert launches == expected[:charges]
    assert not result.complete and result.stop_reason == reason
    assert result.attempts_this_run == charges and result.completed == result.hydrated == 1
    movie, = _rows(db)
    assert movie[:3] == ("movie", 41, "hydrated")
    assert json.loads(movie[3])["requested_locale"] == "ru-RU"
    assert "discard me" not in movie[3] and "fictional-test-marker" not in movie[3]
    resumed, launches = _run(plan, db)
    assert resumed.complete and resumed.attempts_this_run == 2 and launches == expected[1:]
    unchanged, series = _rows(db)
    assert unchanged == movie and series[:3] == ("tv", 41, "hydrated")
    assert json.loads(series[3])["requested_locale"] == "en-US"
    final, launches = _run(plan, db, 0)
    assert final.complete and final.attempts_this_run == 0 and not launches


@pytest.mark.parametrize("mode", ["wrong_type", "wrong_id"])
def test_invalid_detail_does_not_poison_checkpoint(tmp_path, mode):
    plan, db = _plan(tmp_path), tmp_path / "detached.sqlite"
    result, launches = _run(plan, db, mode=mode)
    assert result.stop_reason == "invalid_typed_detail" and result.completed == 1
    assert launches[-1] == ("/tv/41", "en-US")
    assert [r[:3] for r in _rows(db)] == [("movie", 41, "hydrated")]
    assert _run(plan, db)[0].complete


@pytest.mark.parametrize(("mode", "column", "calls"), [
    ("unknown_adult", "ineligible", 2), ("missing", "missing_overview", 3),
])
def test_expected_terminal_nonhydrated_rows_are_not_redispatched(tmp_path, mode, column, calls):
    plan, db = _plan(tmp_path), tmp_path / "detached.sqlite"
    result, launches = _run(plan, db, mode=mode)
    assert result.complete and result.hydrated == 1 and getattr(result, column) == 1
    assert len(launches) == calls
    assert _rows(db)[1] == ("tv", 41, column, None)
    assert _run(plan, db, 0)[0].complete


def test_new_manifest_or_non_hydration_db_rejected_before_any_launch(tmp_path):
    plan, db = _plan(tmp_path), tmp_path / "detached.sqlite"
    zero, calls = _run(plan, db, 0)
    assert not calls and zero.stop_reason == "budget_exhausted" and zero.completed == 0

    changed = _plan(tmp_path, cap=1)
    transcript = []
    transport = _transport(20, transcript)
    with pytest.raises(ValueError, match="separate checkpoint"):
        hydrate_id_plan(plan=changed, checkpoint=db, transport=transport)
    other = tmp_path / "other.sqlite"
    with closing(sqlite3.connect(other)) as conn, conn:
        conn.execute("CREATE TABLE watched (title TEXT)")
        conn.execute("INSERT INTO watched VALUES ('keep')")
    before = other.read_bytes()
    with pytest.raises(ValueError, match="separate checkpoint"):
        hydrate_id_plan(plan=plan, checkpoint=other, transport=transport)
    assert not transcript and other.read_bytes() == before


def test_cancellation_and_concurrent_sqlite_writer_do_not_dispatch(tmp_path):
    plan, db = _plan(tmp_path), tmp_path / "detached.sqlite"
    transcript = []
    transport = _transport(20, transcript, cancelled=lambda: True)
    assert hydrate_id_plan(plan=plan, checkpoint=db, transport=transport).stop_reason == "cancelled"
    assert not transcript and not _rows(db)
    with closing(sqlite3.connect(db)) as conn:
        conn.execute("BEGIN IMMEDIATE")
        with pytest.raises(sqlite3.OperationalError, match="locked"):
            hydrate_id_plan(plan=plan, checkpoint=db, transport=_transport(20, transcript))
    assert not transcript


def _missing_transport(transcript, *, phase="ru-RU", code=34, http=404,
                       content_type="application/json; charset=utf-8", response_url=None):
    healthy = _transport(20, [])
    def opener(request, *, timeout):
        target = urlsplit(request.full_url)
        locale = parse_qs(target.query)["language"][0]
        transcript.append((target.path, locale))
        if target.path == "/3/tv/41" and locale == phase:
            body = json.dumps({"success": False, "status_code": code, "status_message": "fixture"}).encode()
            raise HTTPError(response_url or request.full_url, http, "fixture", {"Content-Type": content_type},
                            io.BytesIO(body))
        return healthy._open(request, timeout=timeout)
    return DetachedTmdbTransport(20, bearer=lambda: "fictional-test-marker", opener=opener)


def test_verified_missing_typed_item_migrates_restarts_and_has_separate_export_count(tmp_path):
    from hashlib import sha256
    from web.tmdb_catalog_audit import ReviewedLanguage, audit_hydration
    from web.tmdb_seed_export import export_reviewed_seed

    plan, checkpoint = _plan(tmp_path), tmp_path / "legacy.sqlite"
    original_payload = json.dumps({"media_type": "movie", "tmdb_id": 41, "title": "Legacy title",
                                   "overview": "Legacy fixture.", "year": 2020, "requested_locale": "en-US"})
    with closing(sqlite3.connect(checkpoint)) as conn, conn:
        conn.execute("CREATE TABLE hydration_plan (singleton INTEGER PRIMARY KEY CHECK(singleton=1), manifest TEXT NOT NULL)")
        conn.execute("""CREATE TABLE hydration_items (
            media TEXT NOT NULL CHECK(media IN ('movie', 'tv')),
            tmdb_id INTEGER NOT NULL CHECK(tmdb_id > 0),
            status TEXT NOT NULL CHECK(status IN ('hydrated', 'ineligible', 'missing_overview')),
            payload TEXT, PRIMARY KEY(media, tmdb_id),
            CHECK ((status = 'hydrated') = (payload IS NOT NULL))
        )""")
        conn.execute("INSERT INTO hydration_plan VALUES (1,?)",
                     (json.dumps(plan.manifest(), sort_keys=True, separators=(",", ":")),))
        conn.execute("INSERT INTO hydration_items VALUES ('movie',41,'hydrated',?)", (original_payload,))

    calls = []
    run = hydrate_id_plan(plan=plan, checkpoint=checkpoint, transport=_missing_transport(calls))
    assert run.complete and run.unavailable == 1 and run.hydrated == 1
    assert run.attempts_this_run == 1 and calls == [("/3/tv/41", "ru-RU")]
    assert _rows(checkpoint) == [("movie", 41, "hydrated", original_payload), ("tv", 41, "unavailable", None)]
    resumed, transcript = _run(plan, checkpoint, 0)
    assert resumed.complete and resumed.unavailable == 1 and not transcript

    report = audit_hydration(plan=plan, checkpoint=checkpoint)
    assert report["by_media"]["tv"]["unavailable"] == 1 and report["by_media"]["tv"]["pending"] == 0
    export = tmp_path / "seed.jsonl"
    review = ReviewedLanguage(sha256(b"Legacy fixture.").hexdigest(), "en")
    report = export_reviewed_seed(plan=plan, checkpoint=checkpoint, output=export,
                                  reviewed={"tmdb:movie:41": review}, use_cleared=True)
    assert report["unavailable"] == 1 and report["exported"] == 1
    assert json.loads(export.read_text(encoding="utf-8"))["media_type"] == "movie"


@pytest.mark.parametrize("options", [
    {"phase": "en-US"}, {"code": 6}, {"code": 37}, {"code": "34"}, {"http": 401}, {"http": 429},
    {"content_type": "text/html"}, {"response_url": "https://example.invalid/provider"},
])
def test_untrusted_or_conflicting_missing_response_leaves_item_pending(tmp_path, options):
    plan, checkpoint = _plan(tmp_path), tmp_path / "detached.sqlite"
    calls = []
    run = hydrate_id_plan(plan=plan, checkpoint=checkpoint, transport=_missing_transport(calls, **options))
    assert not run.complete and run.unavailable == 0 and run.completed == 1
    assert run.stop_reason == ("throttled" if options.get("http") == 429 else "http")
    assert _run(plan, checkpoint)[0].complete

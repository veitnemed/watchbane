"""Detached refresh exercised with a guarded transport and a synthetic opener."""
from contextlib import closing
from datetime import date
import io
import json
import sqlite3
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit

import pytest

from apis.tmdb.detached_transport import DetachedTmdbTransport
from web.tmdb_change_windows import commit_change_window, pending_change
from web.tmdb_hydration import refresh_pending_change
from web.tmdb_ids import QueueItem


MOVIE = QueueItem("movie", 42)
TV = QueueItem("tv", 42)


def _commit(db, day, *items):
    window = date(2026, 1, day)
    return commit_change_window(checkpoint=db, start=window, end=window, pages_by_media={
        media: [{"page": 1, "total_pages": 1, "results": [
            {"id": item.tmdb_id} for item in items if item.media_type == media
        ]}] for media in ("movie", "tv")
    })


def _run(db, item, *, cap=2, mode="ok", before_return=lambda: None):
    calls = []

    def opener(request, *, timeout):
        url = urlsplit(request.full_url)
        locale = parse_qs(url.query)["language"][0]
        calls.append((url.path, locale))
        if locale == "ru-RU":
            before_return()
        if mode == "unavailable":
            payload = io.BytesIO(b'{"success": false, "status_code": 34}')
            raise HTTPError(request.full_url, 404, "fixture", {"Content-Type": "application/json"}, payload)
        if mode == "throttled":
            raise HTTPError(request.full_url, 429, "fixture", {}, io.BytesIO())
        overview = "" if mode == "missing_overview" or item == TV and locale == "ru-RU" else "Synopsis"
        if mode == "malformed_synopsis":
            overview = "\ud800"
        return io.BytesIO(json.dumps({
            "id": 43 if mode == "wrong_id" else item.tmdb_id,
            "adult": mode == "ineligible", "name" if item == TV else "title": "Fixture",
            "overview": overview,
            "private_fixture_marker": "discard",
        }).encode())

    transport = DetachedTmdbTransport(cap, bearer=lambda: "synthetic-test-marker", opener=opener)
    return refresh_pending_change(checkpoint=db, item=item, transport=transport), calls


def _staged(db):
    with closing(sqlite3.connect(db)) as conn:
        return [(kind, key, version, json.loads(payload)) for kind, key, version, payload in
                conn.execute("SELECT media,tmdb_id,version,payload FROM change_completed ORDER BY media")]


def test_newer_window_wins_and_movie_tv_versions_are_independent(tmp_path):
    db = tmp_path / "changes.sqlite"
    _commit(db, 1, MOVIE, TV)
    movie_a, tv_a = pending_change(db, MOVIE), pending_change(db, TV)
    stale, calls = _run(db, MOVIE, before_return=lambda: _commit(db, 2, MOVIE))
    assert (stale.status, stale.attempts_this_run, calls) == ("superseded", 1, [("/3/movie/42", "ru-RU")])
    movie_b = pending_change(db, MOVIE)
    assert movie_b.version > movie_a.version and pending_change(db, TV) == tv_a and _staged(db) == []
    assert _run(db, MOVIE)[0].status == "staged"
    movie_result, = _staged(db)
    assert movie_result[:3] == ("movie", 42, movie_b.version)
    assert "private_fixture_marker" not in movie_result[3]
    duplicate, calls = _run(db, MOVIE)
    assert (duplicate.status, duplicate.attempts_this_run, calls) == ("not_pending", 0, [])
    capped, calls = _run(db, TV, cap=1)
    assert (capped.status, capped.stop_reason, calls) == ("stopped", "budget_exhausted", [("/3/tv/42", "ru-RU")])
    assert pending_change(db, TV) == tv_a and _staged(db) == [movie_result]
    refreshed, calls = _run(db, TV)
    assert refreshed.status == "staged" and calls == [("/3/tv/42", "ru-RU"), ("/3/tv/42", "en-US")]
    assert _staged(db)[1][3]["requested_locale"] == "en-US"


@pytest.mark.parametrize(("mode", "status", "reason"), [
    ("unavailable", "unavailable", None), ("ineligible", "ineligible", None),
    ("missing_overview", "missing_overview", None), ("throttled", "stopped", "throttled"),
    ("wrong_id", "stopped", "invalid_typed_detail"),
    ("malformed_synopsis", "stopped", "invalid_typed_detail"),
])
def test_nonhydrated_or_failed_newer_work_does_not_remove_older_staging(tmp_path, mode, status, reason):
    db = tmp_path / "changes.sqlite"
    _commit(db, 1, MOVIE)
    assert _run(db, MOVIE)[0].status == "staged"
    old = _staged(db)
    _commit(db, 2, MOVIE)
    ticket = pending_change(db, MOVIE)
    result, calls = _run(db, MOVIE, mode=mode)
    assert (result.status, result.stop_reason, result.attempts_this_run) == (status, reason, len(calls))
    assert pending_change(db, MOVIE) == ticket
    assert _staged(db) == old

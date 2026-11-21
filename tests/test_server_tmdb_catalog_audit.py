from contextlib import closing
from datetime import date
import gzip
from hashlib import sha256
import io
import json
import sqlite3
from urllib.parse import parse_qs, urlsplit

import pytest

from apis.tmdb.detached_transport import DetachedTmdbTransport
from web.tmdb_catalog_audit import ReviewedLanguage, audit_hydration
from web.tmdb_hydration import hydrate_id_plan
from web.tmdb_ids import plan_daily_ids


@pytest.fixture
def checkpoint(tmp_path):
    movie = tmp_path / "movie_ids_01_02_2026.json.gz"
    tv = tmp_path / "tv_series_ids_01_02_2026.json.gz"
    movie.write_bytes(gzip.compress(b'{"id":41,"adult":false}\n{"id":42,"adult":false}\n'))
    tv.write_bytes(gzip.compress(b'{"id":41,"adult":false}\n'))
    plan = plan_daily_ids(export_date=date(2026, 1, 2), movie_file=movie, tv_file=tv, per_media_limit=2)
    db = tmp_path / "checkpoint.sqlite"

    def opener(request, *, timeout):
        url = urlsplit(request.full_url)
        locale = parse_qs(url.query)["language"][0]
        identifier = int(url.path.rsplit("/", 1)[-1])
        movie = "/movie/" in url.path
        overview = "Fixture English synopsis" if movie else "Независимое тестовое описание"
        if identifier == 42 or (not movie and locale == "ru-RU"):
            overview = ""
        return io.BytesIO(json.dumps({
            "id": identifier, "adult": False, "title" if movie else "name": "Synthetic fixture title",
            "overview": overview,
        }).encode())

    def run(cap):
        return hydrate_id_plan(plan=plan, checkpoint=db, transport=DetachedTmdbTransport(
            cap, bearer=lambda: "fictional-test-marker", opener=opener,
        ))

    return plan, db, run


def test_requested_is_not_observed_and_report_contains_only_aggregates(checkpoint):
    plan, db, run = checkpoint
    assert run(10).complete
    before = db.read_bytes()
    plain = audit_hydration(plan=plan, checkpoint=db)
    assert plain["distinct_typed_completed"] == 3
    movie, tv = (plain["by_media"][kind] for kind in ("movie", "tv"))
    assert movie["requested_locale"] == {"ru-RU": 1, "en-US": 0}
    assert movie["missing_overview"] == 1 and movie["pending"] == 0
    assert tv["requested_locale"] == {"ru-RU": 0, "en-US": 1}
    assert movie["observed_language"] == tv["observed_language"] == {"ru": 0, "en": 0, "other": 0, "unverified": 1}
    evidence = {
        "tmdb:movie:41": ReviewedLanguage(sha256(b"Fixture English synopsis").hexdigest(), "en"),
        "tmdb:tv:41": ReviewedLanguage(sha256("Независимое тестовое описание".encode()).hexdigest(), "ru"),
    }
    checked = audit_hydration(plan=plan, checkpoint=db, observed=evidence)
    assert checked["by_media"]["movie"]["observed_language"] == {"ru": 0, "en": 1, "other": 0, "unverified": 0}
    assert checked["by_media"]["tv"]["observed_language"] == {"ru": 1, "en": 0, "other": 0, "unverified": 0}
    serialized = json.dumps(checked, ensure_ascii=False)
    assert all(x not in serialized for x in ("Fixture", "описание", "tmdb:", *[e.synopsis_sha256 for e in evidence.values()]))
    assert db.read_bytes() == before


def test_pending_missing_and_review_mismatch_remain_separate(checkpoint):
    plan, db, run = checkpoint
    assert not run(0).complete
    pending = audit_hydration(plan=plan, checkpoint=db)
    assert [pending["by_media"][kind]["pending"] for kind in ("movie", "tv")] == [2, 1]
    assert all(group["missing_overview"] == 0 for group in pending["by_media"].values())
    bad = ReviewedLanguage("0" * 64, "ru")
    with pytest.raises(ValueError, match="requires a hydrated"):
        audit_hydration(plan=plan, checkpoint=db, observed={"tmdb:movie:41": bad})
    assert run(10).complete
    with pytest.raises(ValueError, match="does not match"):
        audit_hydration(plan=plan, checkpoint=db, observed={"tmdb:movie:41": bad})
    with pytest.raises(ValueError, match="requires a hydrated"):
        audit_hydration(plan=plan, checkpoint=db, observed={"tmdb:movie:42": bad})
    with pytest.raises(ValueError, match="outside"):
        audit_hydration(plan=plan, checkpoint=db, observed={"tmdb:movie:99": bad})


def test_rejects_checkpoint_with_inconsistent_typed_row(checkpoint):
    plan, db, run = checkpoint
    assert run(10).complete
    with closing(sqlite3.connect(db)) as conn, conn:
        current, = conn.execute("SELECT payload FROM hydration_items WHERE media='tv'").fetchone()
        conn.execute("UPDATE hydration_items SET payload=? WHERE media='tv'",
                     (json.dumps({**json.loads(current), "media_type": "movie"}),))
    with pytest.raises(ValueError, match="Invalid hydration description"):
        audit_hydration(plan=plan, checkpoint=db)

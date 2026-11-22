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


def test_private_tv_origin_and_observed_language_are_independent(tmp_path):
    from web.tmdb_seed_export import export_reviewed_seed

    movie = tmp_path / "movie_ids_01_02_2026.json.gz"
    tv = tmp_path / "tv_series_ids_01_02_2026.json.gz"
    for path, ids in ((movie, [1]), (tv, [1, 2, 3, 4, 5])):
        path.write_bytes(gzip.compress(b"".join(
            json.dumps({"id": i, "adult": False}).encode() + b"\n" for i in ids
        )))
    plan = plan_daily_ids(export_date=date(2026, 1, 2), movie_file=movie, tv_file=tv, per_media_limit=5)
    db = tmp_path / "origins.sqlite"
    english = "Independently reviewed English synopsis."
    russian = "Независимо проверенное русское описание."
    # Coproduction (1), non-RU translated (2), RU with EN fallback (3),
    # absent despite Russian original_language (4), conflicting locale sets (5).
    countries = {1: ["RU", "FR", "RU"], 2: ["JP"], 3: ["RU"], 5: ["RU"]}

    def opener(request, *, timeout):
        url = urlsplit(request.full_url)
        locale = parse_qs(url.query)["language"][0]
        identifier = int(url.path.rsplit("/", 1)[1])
        is_movie = "/movie/" in url.path
        data = {"id": identifier, "adult": False, "title" if is_movie else "name": "Synthetic",
                "overview": russian, "original_language": "ru"}
        if is_movie:
            data["production_countries"] = [{"iso_3166_1": "RU"}]
            data["origin_country"] = ["RU"]  # not trusted as TV evidence
        else:
            if identifier in countries:
                data["origin_country"] = countries[identifier]
            if identifier in (3, 5):
                data["overview"] = "" if locale == "ru-RU" else english
                if locale == "en-US":
                    if identifier == 5:
                        data["origin_country"] = ["DE"]
                    else:
                        del data["origin_country"]  # earlier typed snapshot remains usable evidence
        return io.BytesIO(json.dumps(data).encode())

    result = hydrate_id_plan(plan=plan, checkpoint=db, transport=DetachedTmdbTransport(
        10, bearer=lambda: "fictional-test-marker", opener=opener,
    ))
    assert result.complete and result.hydrated == 6 and result.attempts_this_run == 8
    review = {
        f"tmdb:{kind}:{identifier}": ReviewedLanguage(sha256(text.encode()).hexdigest(), lang)
        for kind, identifier, text, lang in (
            ("tv", 1, russian, "ru"), ("tv", 2, russian, "ru"), ("tv", 3, english, "en"),
            ("tv", 4, russian, "ru"), ("tv", 5, english, "en"), ("movie", 1, russian, "ru"),
        )
    }
    plain = audit_hydration(plan=plan, checkpoint=db)
    assert plain["by_media"]["tv"]["observed_language_by_recorded_origin"]["ru_only"]["unverified"] == 1
    groups = audit_hydration(plan=plan, checkpoint=db, observed=review)["by_media"]
    cross = groups["tv"]["observed_language_by_recorded_origin"]
    assert {origin: {lang: count for lang, count in langs.items() if count} for origin, langs in cross.items()} == {
        "ru_only": {"en": 1}, "ru_coproduction": {"ru": 1},
        "other_recorded": {"ru": 1}, "unknown": {"ru": 1, "en": 1},
    }
    assert groups["movie"]["observed_language_by_recorded_origin"]["unknown"]["ru"] == 1
    with closing(sqlite3.connect(db)) as conn:
        typed = {key: json.loads(payload) for key, payload in conn.execute(
            "SELECT tmdb_id, payload FROM hydration_items WHERE media='tv'"
        )}
        assert typed[1]["origin_country_codes"] == ["FR", "RU"]
        assert "origin_country_codes" not in typed[5]

    def export(name):
        path = tmp_path / name
        export_reviewed_seed(plan=plan, checkpoint=db, output=path, reviewed=review, use_cleared=True)
        return path.read_bytes()

    before = export("recorded.jsonl")
    with closing(sqlite3.connect(db)) as conn, conn:
        for key in (1, 2, 3):
            typed[key].pop("origin_country_codes")
            conn.execute("UPDATE hydration_items SET payload=? WHERE media='tv' AND tmdb_id=?",
                         (json.dumps(typed[key]), key))
    assert export("legacy.jsonl") == before
    assert b"origin_country" not in before
    legacy = audit_hydration(plan=plan, checkpoint=db, observed=review)["by_media"]["tv"]
    assert legacy["observed_language_by_recorded_origin"]["unknown"] == legacy["observed_language"]

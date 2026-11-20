from collections import Counter
import json
import sqlite3
from urllib.error import HTTPError

import pytest

from tools.qa.build_story_starter_catalog import (
    Acquisition, AcquisitionError, DEFAULT_ORDER, GENRES, INTERLEAVED_ORDER, Plan, buckets, build_catalog,
)


class CatalogFixture:
    def __init__(self):
        self.discover = []
        self.details = []
        self.interrupt_page = None

    def __call__(self, path, params, *, retries, timeout):
        assert retries == 0 and timeout == 12
        if path.startswith("/discover/"):
            media = path.split("/")[-1]
            date = params["primary_release_date.gte" if media == "movie" else "first_air_date.gte"]
            decade = int(date[:4])
            group = GENRES[media].index(params["with_genres"])
            page = params["page"]
            self.discover.append((media, decade, group, page))
            assert params["language"] == "ru-RU" and params["include_adult"] == "false"
            if self.interrupt_page == len(self.discover):
                raise KeyboardInterrupt
            id0 = (decade - 1900) * 10000 + group * 1000 + page * 20
            title_key, date_key = ("title", "release_date") if media == "movie" else ("name", "first_air_date")
            rows = [
                {"id": id0 + i, title_key: f"Title {id0+i}", date_key: f"{decade}-02-01",
                 "overview": "" if i == 0 else "Правдоподобное описание события, действующих лиц и места в синтетическом тесте.",
                 "genre_ids": [int(params["with_genres"].split("|")[0])], "poster_path": "/sample.jpg"}
                for i in range(20)
            ]
            if page > 1:
                # Same title is encountered via changing Discover pagination.
                rows[-1]["id"] -= 20
            return {"total_pages": 12, "results": rows}
        media, ident = path[1:].split("/")
        self.details.append((media, ident, params["language"]))
        return {"id": int(ident), "overview": "A sufficiently long English overview of a fictional character and an event."}


def test_mocked_5000_realistic_scale(tmp_path):
    source = CatalogFixture()
    checkpoint, output = tmp_path / "checkpoint.sqlite3", tmp_path / "out.jsonl"
    progress = []
    result = build_catalog(checkpoint, output, Plan(5000, "2025-12-31"),
                           get=source, progress=progress.append)
    assert result["complete"] and result["by_media"] == {"movie": 2500, "tv": 2500}
    rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    assert len({(r["media_type"], r["tmdb_id"]) for r in rows}) == len(rows) == 5000
    assert len({r["discover_bucket"] for r in rows}) == 98
    assert {r["year"] // 10 * 10 for r in rows} == set(range(1960, 2030, 10))
    assert set(r["language"] for r in rows) == {"ru-RU", "en-US"}
    assert 250 <= len(source.discover) <= 300
    assert 0 < len(source.details) < 300
    assert {x[-1] for x in source.details} == {"en-US"}
    assert progress[-1]["movie"] == progress[-1]["tv"] == 2500
    assert all(r["key"] == f'tmdb:{r["media_type"]}:{r["tmdb_id"]}' for r in rows)
    before = output.read_bytes()
    assert build_catalog(checkpoint, output, Plan(5000, "2025-12-31"),
                         get=source)["api_requests_this_run"] == 0
    assert output.read_bytes() == before


def test_interruption_resumes_from_last_committed_page(tmp_path):
    checkpoint, output = tmp_path / "resume.sqlite3", tmp_path / "resume.jsonl"
    plan = Plan(120, "2025-12-31")
    first = CatalogFixture()
    first.interrupt_page = 5
    with pytest.raises(KeyboardInterrupt):
        build_catalog(checkpoint, output, plan, get=first)
    assert not output.exists()
    second = CatalogFixture()
    assert build_catalog(checkpoint, output, plan, get=second)["count"] == 120
    assert second.discover[0] == first.discover[-1]
    assert not set(first.discover[:-1]) & set(second.discover)
    reference = tmp_path / "reference.jsonl"
    build_catalog(tmp_path / "reference.sqlite3", reference, plan, get=CatalogFixture())
    assert output.read_bytes() == reference.read_bytes()
    with pytest.raises(ValueError, match="другим планом"):
        build_catalog(checkpoint, output, Plan(122, "2025-12-31"), get=second)


def test_exhausted_keeps_previous_export_and_reuses_checkpoint(tmp_path):
    output = tmp_path / "out.jsonl"
    output.write_text("existing export", encoding="utf-8")
    calls = []
    def empty(path, params, **kwargs):
        calls.append(path)
        return {"total_pages": 0, "results": []}
    plan = Plan(2, "1960-02-01")
    checkpoint = tmp_path / "db.sqlite3"
    result = build_catalog(checkpoint, output, plan, get=empty)
    assert result["complete"] is False and result["count"] == 0
    assert len(calls) == 14
    assert output.read_text(encoding="utf-8") == "existing export"
    assert not build_catalog(checkpoint, output, plan, get=empty)["api_requests_this_run"]


def test_retry_after_and_redacted_auth_errors():
    calls, sleeps = Counter(), []
    def get(path, params, **kwargs):
        calls[path] += 1
        if calls[path] == 1:
            http = HTTPError("https://example.invalid/?api_key=SECRET", 429, "secret", {"Retry-After": "2"}, None)
            raise RuntimeError("API key SECRET") from http
        return {"results": []}
    assert Acquisition(get, sleep=sleeps.append).request("/discover/movie", {}) == {"results": []}
    assert sleeps == [2.0]
    def unauthorized(*args, **kwargs):
        raise RuntimeError("SECRET") from HTTPError("https://example.invalid/", 401, "SECRET", {}, None)
    with pytest.raises(AcquisitionError, match=r"HTTP 401") as failure:
        Acquisition(unauthorized, sleep=sleeps.append).request("/discover/movie", {})
    assert "SECRET" not in str(failure.value)
    assert sleeps == [2.0]


def test_long_retry_after_stops_without_shortening_cooldown():
    sleeps = []
    def get(*a, **kw):
        raise HTTPError("https://example.invalid/", 429, "busy", {"Retry-After": "180"}, None)
    with pytest.raises(AcquisitionError, match="Retry-After"):
        Acquisition(get, sleep=sleeps.append).request("/discover/movie", {})
    assert not sleeps


def test_origin_is_independent_of_locale_and_counts_survive_resume(tmp_path):
    checkpoint, output = tmp_path / "origin.sqlite3", tmp_path / "out.jsonl"
    plan = Plan(6, "1960-12-31")
    ru = "Подробное описание известных героев этого вымышленного художественного произведения."
    en = "A detailed description of the characters in this fictional television production."
    calls = []

    def get(path, params, **kwargs):
        calls.append(path)
        if path == "/discover/movie":
            rows = [{"id": i, "title": f"Movie {i}", "release_date": "1960-01-01",
                     "overview": ru} for i in (1, 2, 3)]
        elif path == "/discover/tv":
            rows = [{"id": i, "name": f"TV {i}", "first_air_date": "1960-01-01",
                     "overview": overview, "origin_country": origin}
                    for i, overview, origin in ((1, ru, ["US"]), (2, "", ["RU"]),
                                                (3, "", ["not a country"]), (4, ru, []))]
        else:
            ident = int(path.rsplit("/", 1)[-1])
            return {"id": ident, "overview": en if ident == 2 else ""}
        return {"total_pages": 1, "results": rows}

    result = build_catalog(checkpoint, output, plan, get=get)
    rows = {r["key"]: r for line in output.read_text(encoding="utf-8").splitlines()
            if (r := json.loads(line))}
    assert rows["tmdb:tv:1"]["origin_country"] == ["US"]
    assert rows["tmdb:tv:1"]["language"] == "ru-RU"
    assert rows["tmdb:tv:2"]["origin_country"] == ["RU"]
    assert rows["tmdb:tv:2"]["language"] == "en-US"
    assert "origin_country" not in rows["tmdb:tv:4"]
    expected = {"by_locale": {"ru-RU": 5, "en-US": 1},
                "tv_russia_origin": 1, "tv_unknown_origin": 1, "unusable_overview_count": 1}
    assert {key: result[key] for key in expected} == expected
    resumed = build_catalog(checkpoint, output, plan, get=get)
    assert resumed["api_requests_this_run"] == 0
    assert {key: resumed[key] for key in expected} == expected


def test_interleaved_first_pass_spreads_decades_and_genres_without_changing_coverage():
    legacy = list(buckets(Plan(through="2025-07-17")))
    expected_years = list(range(1960, 2030, 10))
    spread = list(buckets(Plan(through="2025-07-17", order=INTERLEAVED_ORDER)))
    first_pass = spread[:2 * len(expected_years)]
    assert [int(b.start[:4]) for b in first_pass[::2]] == expected_years
    assert [int(b.start[:4]) for b in first_pass[1::2]] == expected_years
    assert [b.media for b in first_pass] == ["movie", "tv"] * len(expected_years)
    assert [b.genre for b in first_pass[::2]] == list(GENRES["movie"])
    assert [b.genre for b in first_pass[1::2]] == list(GENRES["tv"])
    assert {int(b.start[:4]) for b in legacy[:len(first_pass)]} == {1960}
    assert len(spread) == len({b.key for b in spread}) == len(legacy) == 98
    assert set(spread) == set(legacy)
    assert {b.end for b in spread if b.start[:4] == "2020"} == {"2025-07-17"}
    with pytest.raises(ValueError, match="Недопустимые"):
        list(buckets(Plan(through="2025-07-17", order="unknown")))


def test_new_interleaved_checkpoint_resumes_with_same_pages_and_bytes(tmp_path):
    checkpoint, output = tmp_path / "interleaved.sqlite3", tmp_path / "interleaved.jsonl"
    plan = Plan(420, "2025-12-31", order=INTERLEAVED_ORDER)
    first = CatalogFixture()
    first.interrupt_page = 6
    with pytest.raises(KeyboardInterrupt):
        build_catalog(checkpoint, output, plan, get=first)
    # First five committed discover pages span three decades, and the sixth
    # (first TV page of the third decade) was interrupted before commit.
    assert [(media, decade) for media, decade, _, _ in first.discover] == [
        ("movie", 1960), ("tv", 1960), ("movie", 1970), ("tv", 1970), ("movie", 1980), ("tv", 1980),
    ]
    assert not output.exists()
    second = CatalogFixture()
    assert build_catalog(checkpoint, output, plan, get=second)["count"] == 420
    assert second.discover[0] == first.discover[-1]
    assert not set(first.discover[:-1]) & set(second.discover)
    reference = tmp_path / "reference.jsonl"
    baseline = CatalogFixture()
    build_catalog(tmp_path / "reference.sqlite3", reference, plan, get=baseline)
    assert first.discover[:-1] + second.discover == baseline.discover
    assert output.read_bytes() == reference.read_bytes()
    with sqlite3.connect(checkpoint) as conn:
        signature, = conn.execute("SELECT value FROM settings WHERE key='plan'").fetchone()
    assert json.loads(signature)["plan"]["order"] == INTERLEAVED_ORDER
    with pytest.raises(ValueError, match="другим планом"):
        build_catalog(checkpoint, output, Plan(420, "2025-12-31"), get=CatalogFixture())


def test_legacy_exact_checkpoint_signature_is_unchanged_and_cannot_switch_order(tmp_path):
    checkpoint, output = tmp_path / "old.sqlite3", tmp_path / "old.jsonl"
    legacy_signature = json.dumps({
        "version": 1,
        "plan": {"target": 40, "through": "2025-12-31", "max_pages": 12, "min_overview": 50, "min_votes": 10},
        "genres": GENRES,
    }, sort_keys=True)
    with sqlite3.connect(checkpoint) as conn:
        conn.execute("CREATE TABLE settings(key TEXT PRIMARY KEY,value TEXT NOT NULL)")
        conn.execute("INSERT INTO settings VALUES ('plan',?)", (legacy_signature,))
    before = checkpoint.read_bytes()
    unexpected = CatalogFixture()
    with pytest.raises(ValueError, match="другим планом"):
        build_catalog(checkpoint, output, Plan(40, "2025-12-31", order=INTERLEAVED_ORDER), get=unexpected)
    assert not unexpected.discover and not output.exists()
    assert checkpoint.read_bytes() == before

    previous = CatalogFixture()
    assert build_catalog(checkpoint, output, Plan(40, "2025-12-31", order=DEFAULT_ORDER), get=previous)["complete"]
    assert previous.discover[:2] == [("movie", 1960, 0, 1), ("tv", 1960, 0, 1)]
    with sqlite3.connect(checkpoint) as conn:
        after, = conn.execute("SELECT value FROM settings WHERE key='plan'").fetchone()
    assert after == legacy_signature
    assert build_catalog(checkpoint, output, Plan(40, "2025-12-31"), get=unexpected)["complete"]
    assert not unexpected.discover

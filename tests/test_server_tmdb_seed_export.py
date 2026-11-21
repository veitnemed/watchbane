from hashlib import sha256
import json

import pytest

from candidates.story_seed_snapshot import load_seed_snapshot
from web.tmdb_catalog_audit import ReviewedLanguage
from web.tmdb_seed_export import export_reviewed_seed
from test_server_tmdb_catalog_audit import checkpoint  # shared synthetic hydration fixture


def test_only_review_bound_rows_export_and_seed_parser_agrees(checkpoint, tmp_path):
    plan, db, run = checkpoint
    assert run(10).complete
    output = tmp_path / "seed.jsonl"
    evidence = {
        "tmdb:movie:41": ReviewedLanguage(sha256(b"Fixture English synopsis").hexdigest(), "en"),
        "tmdb:tv:41": ReviewedLanguage(sha256("Независимое тестовое описание".encode()).hexdigest(), "ru"),
    }
    before = db.read_bytes()
    result = export_reviewed_seed(plan=plan, checkpoint=db, output=output, reviewed=evidence, use_cleared=True)
    assert result == {"planned": 3, "completed": 3, "hydrated": 2, "missing_overview": 1, "ineligible": 0, "unavailable": 0,
                      "unreviewed_hydrated": 0, "exported": 2, "by_reviewed_language": {"ru": 1, "en": 1}}
    parsed = load_seed_snapshot(output)
    assert set(parsed) == set(evidence)
    assert parsed["tmdb:movie:41"]["localized"]["en"]["overview"] == "Fixture English synopsis"
    assert "ru" in parsed["tmdb:tv:41"]["localized"]
    rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    assert [row["language"] for row in rows] == ["en-US", "ru-RU"]
    assert all(set(row) == {"media_type", "tmdb_id", "title", "overview", "year", "language"} for row in rows)
    assert db.read_bytes() == before
    one = export_reviewed_seed(plan=plan, checkpoint=db, output=tmp_path / "one.jsonl",
                               reviewed={"tmdb:movie:41": evidence["tmdb:movie:41"]}, use_cleared=True)
    assert one["exported"] == one["unreviewed_hydrated"] == 1


def test_default_incomplete_and_digest_mismatch_publish_nothing(checkpoint, tmp_path):
    plan, db, run = checkpoint
    output = tmp_path / "seed.jsonl"
    evidence = {"tmdb:movie:41": ReviewedLanguage(sha256(b"Fixture English synopsis").hexdigest(), "en")}
    kwargs = dict(plan=plan, checkpoint=db, output=output)
    with pytest.raises(PermissionError):
        export_reviewed_seed(**kwargs, reviewed=evidence)
    assert not output.exists()
    assert not run(0).complete
    with pytest.raises(ValueError, match="incomplete"):
        export_reviewed_seed(**kwargs, reviewed=evidence, use_cleared=True)
    assert run(10).complete
    with pytest.raises(ValueError, match="does not match"):
        export_reviewed_seed(**kwargs, reviewed={"tmdb:movie:41": ReviewedLanguage("0" * 64, "en")}, use_cleared=True)
    with pytest.raises(ValueError, match="requires a hydrated"):
        export_reviewed_seed(**kwargs, reviewed={"tmdb:movie:42": evidence["tmdb:movie:41"]}, use_cleared=True)
    assert not output.exists() and not list(tmp_path.glob(".tmdb-seed-*"))


def test_atomic_publish_refuses_existing_or_concurrently_created_output(checkpoint, tmp_path, monkeypatch):
    from web import tmdb_seed_export

    plan, db, run = checkpoint
    assert run(10).complete
    output = tmp_path / "seed.jsonl"
    evidence = {"tmdb:movie:41": ReviewedLanguage(sha256(b"Fixture English synopsis").hexdigest(), "en")}
    kwargs = dict(plan=plan, checkpoint=db, output=output, reviewed=evidence, use_cleared=True)
    output.write_bytes(b"keep old")
    with pytest.raises(FileExistsError):
        export_reviewed_seed(**kwargs)
    assert output.read_bytes() == b"keep old"
    output.unlink()

    link = tmdb_seed_export.os.link

    def race(staged, destination):
        destination.write_bytes(b"other publisher")
        link(staged, destination)

    monkeypatch.setattr(tmdb_seed_export.os, "link", race)
    with pytest.raises(FileExistsError):
        export_reviewed_seed(**kwargs)
    assert output.read_bytes() == b"other publisher"
    assert not list(tmp_path.glob(".tmdb-seed-*"))

"""Fixture-only proof of reviewed quarantine without live activation."""
from contextlib import closing
from dataclasses import replace
from datetime import date
from hashlib import sha256
import json
import os
import sqlite3

import pytest

from candidates.story_seed_snapshot import load_seed_snapshot_with_digest
from web import tmdb_compose_generation as composer
from web.tmdb_change_windows import commit_change_window, pending_change
from web.tmdb_detached_quarantine import ReviewedAdultDetail, seal_reviewed_adult_quarantine
from web.tmdb_ids import QueueItem


MOVIE = QueueItem("movie", 42)
TV = QueueItem("tv", 42)
BODY = b'{"id":42,"adult":true,"private_ignored_marker":"never written"}'


def _advance(checkpoint, day):
    when = date(2026, 1, day)
    commit_change_window(checkpoint=checkpoint, start=when, end=when, pages_by_media={
        "movie": [{"page": 1, "total_pages": 1, "results": [{"id": MOVIE.tmdb_id}]}],
        "tv": [{"page": 1, "total_pages": 1, "results": []}],
    })


def _seed(path, *items):
    path.write_text("".join(json.dumps({
        "media_type": item.media_type, "tmdb_id": item.tmdb_id,
        "title": "Fixture", "overview": "Условное описание", "language": "ru-RU",
        "poster_path": f"/{item.media_type}.png", "year": 2019,
    }, ensure_ascii=False) + "\n" for item in items), encoding="utf-8")


@pytest.fixture
def args(tmp_path):
    old, db, new = (tmp_path / name for name in ("old.jsonl", "typed.sqlite3", "next.jsonl"))
    _seed(old, TV, MOVIE)
    _advance(db, 1)
    with closing(sqlite3.connect(db)) as connection:
        signature, = connection.execute("SELECT signature FROM change_watermark").fetchone()
    review = ReviewedAdultDetail(MOVIE, pending_change(db, MOVIE).version, signature,
                                 "/3/movie/42", 200, sha256(BODY).hexdigest())
    return dict(previous=old, previous_sha256=sha256(old.read_bytes()).hexdigest(),
                checkpoint=db, output=new, review=review, evidence=BODY, use_cleared=True)


def test_excludes_exact_reviewed_type_only_and_receipt_cannot_activate(args):
    original = args["previous"].read_bytes()
    checkpoint = args["checkpoint"].read_bytes()
    old_rows, _ = load_seed_snapshot_with_digest(args["previous"])
    receipt = seal_reviewed_adult_quarantine(**args)
    new_rows, digest = load_seed_snapshot_with_digest(args["output"])
    assert receipt.sha256 == digest and receipt.rows == 1
    assert new_rows == {TV.key: old_rows[TV.key]}
    assert args["output"].read_bytes() == original.splitlines(keepends=True)[0]
    assert b"private_ignored_marker" not in args["output"].read_bytes()
    assert args["previous"].read_bytes() == original
    assert args["checkpoint"].read_bytes() == checkpoint
    assert receipt.activation_status == "not_eligible_for_activation"
    with pytest.raises(ValueError, match="composer receipt"):
        composer.apply_reviewed_generation_locally(
            checkpoint=args["checkpoint"], generation=args["output"], receipt=receipt, use_cleared=True,
            switch_local=lambda *_: pytest.fail("activation called"),
        )


@pytest.mark.parametrize("body", [
    b'{"id":42}', b'{"id":42,"adult":false}', b'{"id":42,"adult":1}',
    b'{"id":42,"adult":"true"}', b'{"id":42,"adult":null}', b'{"id":42,"adult":false,"adult":true}',
    b'{"id":42,"adult":true,"media_type":"tv"}', b'{"id":43,"adult":true}',
    b'{"status_code":34,"success":false}', b'{"id":42,"adult":true,"success":false}',
])
def test_ambiguous_wrong_id_type_or_provider_failure_is_not_a_quarantine(args, body):
    review = replace(args["review"], response_sha256=sha256(body).hexdigest())
    with pytest.raises(ValueError, match="explicit adult"):
        seal_reviewed_adult_quarantine(**{**args, "review": review, "evidence": body})
    assert not args["output"].exists()


@pytest.mark.parametrize("changes", [
    {"status": 404}, {"status": 429}, {"details_path": "/3/tv/42"},
    {"response_sha256": "0" * 64}, {"change_version": 0},
])
def test_bad_attested_status_path_digest_or_legacy_generation_is_refused(args, changes):
    with pytest.raises(ValueError, match="match exact evidence"):
        seal_reviewed_adult_quarantine(**{**args, "review": replace(args["review"], **changes)})
    assert not args["output"].exists()


def test_uncleared_wrong_prior_and_target_not_present_or_last_are_refused(args):
    with pytest.raises(PermissionError):
        seal_reviewed_adult_quarantine(**{**args, "use_cleared": False})
    with pytest.raises(ValueError, match="Prior|Previous"):
        seal_reviewed_adult_quarantine(**{**args, "previous_sha256": "0" * 64})
    for item in (TV, MOVIE):
        _seed(args["previous"], item)
        with pytest.raises(ValueError, match="existing typed row"):
            seal_reviewed_adult_quarantine(**{**args, "previous_sha256": sha256(args["previous"].read_bytes()).hexdigest()})
        assert not args["output"].exists()


def test_exact_generation_observed_again_after_serialization_and_before_link(args, monkeypatch):
    before = args["previous"].read_bytes()
    original_sync = os.fsync

    def supersede(fd):
        original_sync(fd)
        _advance(args["checkpoint"], 2)

    monkeypatch.setattr(composer.os, "fsync", supersede)
    with pytest.raises(ValueError, match="superseded"):
        seal_reviewed_adult_quarantine(**args)
    assert args["previous"].read_bytes() == before
    assert not args["output"].exists()
    assert not list(args["output"].parent.glob(".tmdb-generation-*"))


def test_target_race_keeps_competing_bytes_without_clearing_checkpoint(args, monkeypatch):
    checkpoint = args["checkpoint"].read_bytes()
    original_link = os.link

    def compete(source, destination):
        with closing(sqlite3.connect(args["checkpoint"], timeout=0)) as connection:
            with pytest.raises(sqlite3.OperationalError, match="locked"):
                connection.execute("BEGIN IMMEDIATE")
        destination.write_bytes(b"other operator's file")
        original_link(source, destination)

    monkeypatch.setattr(composer.os, "link", compete)
    with pytest.raises(FileExistsError):
        seal_reviewed_adult_quarantine(**args)
    assert args["output"].read_bytes() == b"other operator's file"
    assert args["checkpoint"].read_bytes() == checkpoint
    assert not list(args["output"].parent.glob(".tmdb-generation-*"))


def test_missing_checkpoint_does_not_create_any_database_or_output(args):
    args["checkpoint"].unlink()
    with pytest.raises(sqlite3.OperationalError):
        seal_reviewed_adult_quarantine(**args)
    assert not args["checkpoint"].exists() and not args["output"].exists()


def test_different_checkpoint_same_pending_version_not_authorized(args, tmp_path):
    other = tmp_path / "other-change-checkpoint.sqlite3"
    when = date(2026, 1, 1)
    commit_change_window(checkpoint=other, start=when, end=when, pages_by_media={
        media: [{"page": 1, "total_pages": 1, "results": [{"id": 42}]}] for media in ("movie", "tv")
    })
    assert pending_change(other, MOVIE).version == args["review"].change_version
    with pytest.raises(ValueError, match="superseded"):
        seal_reviewed_adult_quarantine(**{**args, "checkpoint": other})
    assert not args["output"].exists()


def test_previous_bytes_changed_between_verification_and_copy_refused(args, monkeypatch):
    from web import tmdb_detached_quarantine as quarantine

    def mutate(path):
        result = load_seed_snapshot_with_digest(path)
        path.write_bytes(path.read_bytes().replace(b"Fixture", b"Changed"))
        return result

    monkeypatch.setattr(quarantine, "load_seed_snapshot_with_digest", mutate)
    with pytest.raises(ValueError, match="changed before quarantine"):
        seal_reviewed_adult_quarantine(**args)
    assert not args["output"].exists()
    assert not list(args["output"].parent.glob(".tmdb-generation-*"))

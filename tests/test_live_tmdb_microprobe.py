from hashlib import sha256
from io import BytesIO
import gzip
import json
import os
import stat
from urllib.error import HTTPError
from urllib.parse import urlsplit

import pytest

from tools.qa import live_tmdb_microprobe as probe


pytestmark = pytest.mark.skipif(os.name != "posix", reason="POSIX credential permissions required")
_SENTINEL = "fixture-operator-secret-not-real"


def inputs(tmp_path, capsys):
    movie = tmp_path / "movie_ids_01_10_2026.json.gz"
    tv = tmp_path / "tv_series_ids_01_10_2026.json.gz"
    for path in (movie, tv):
        path.write_bytes(gzip.compress(b'{"id":311,"adult":false}\n'))
    common = ["--export-date", "2026-01-10", "--movie", str(movie), "--tv", str(tv)]
    assert probe.main(["manifest", *common]) == 0
    content = capsys.readouterr().out.encode("ascii")
    assert b'"tmdb_id"' not in content
    manifest = tmp_path / "approved.json"
    manifest.write_bytes(content)
    bearer = tmp_path / "owner-token"
    bearer.write_text(_SENTINEL + "\n")
    bearer.chmod(0o600)
    directory = tmp_path / "fresh"
    args = ["run", *common, "--manifest", str(manifest), "--manifest-sha256", sha256(content).hexdigest(),
            "--queue-sha256", json.loads(content)["queue_sha256"], "--bearer-file", str(bearer),
            "--checkpoint-dir", str(directory)]
    return args, directory, bearer, manifest


def scripted(trace, *, status=None, reflected=False):
    def opener(request, *, timeout):
        target = urlsplit(request.full_url)
        assert (target.scheme, target.netloc) == ("https", "api.themoviedb.org")
        assert request.get_header("Authorization") == f"Bearer {_SENTINEL}"
        assert timeout == 12
        trace.append((target.path, target.query))
        if status is not None:
            raise HTTPError(request.full_url, status, _SENTINEL, {}, BytesIO(_SENTINEL.encode()))
        movie = target.path == "/3/movie/311"
        return BytesIO(json.dumps({"id": 311, "adult": False,
                                    "title" if movie else "name": "private fictional title",
                                    "overview": (_SENTINEL if reflected else "private fake synopsis")
                                    if target.query == "language=en-US" else ""}).encode())
    return opener


def test_explicit_operator_run_does_exactly_four_typed_lookups_and_aggregate_only(tmp_path, capsys, monkeypatch):
    args, directory, bearer, _ = inputs(tmp_path, capsys)
    monkeypatch.setenv("TMDB_API_KEY", "ambient-must-not-be-read")
    trace = []
    assert probe.main([*args, "--confirm-live-rights"], opener=scripted(trace)) == 0
    report = capsys.readouterr().out
    assert _SENTINEL not in report and "private fake synopsis" not in report and "private fictional title" not in report
    body = json.loads(report)
    assert (body["attempt_limit"], body["attempts_this_run"], body["hydrated"]) == (4, 4, 2)
    assert body["http_stop_status"] is None
    assert trace == [("/3/movie/311", "language=ru-RU"), ("/3/movie/311", "language=en-US"),
                     ("/3/tv/311", "language=ru-RU"), ("/3/tv/311", "language=en-US")]
    assert stat.S_IMODE(directory.stat().st_mode) == 0o700
    db, = directory.iterdir()
    assert stat.S_IMODE(db.stat().st_mode) == 0o600 and _SENTINEL.encode() not in db.read_bytes()
    assert bearer.read_text() == _SENTINEL + "\n"
    with pytest.raises(SystemExit, match="2"):
        probe.main([*args, "--confirm-live-rights"], opener=scripted(trace))
    assert len(trace) == 4


@pytest.mark.parametrize("status", [401, 403, 429])
def test_stops_after_first_auth_or_quota_denial_without_leak(tmp_path, capsys, status):
    args, directory, _, _ = inputs(tmp_path, capsys)
    trace = []
    assert probe.main([*args, "--confirm-live-rights"], opener=scripted(trace, status=status)) == 1
    result = capsys.readouterr()
    assert len(trace) == 1 and _SENTINEL not in result.out + result.err
    assert json.loads(result.out)["http_stop_status"] == status
    db, = directory.iterdir()
    assert _SENTINEL.encode() not in db.read_bytes()


def test_reflected_bearer_is_not_persisted(tmp_path, capsys):
    args, directory, _, _ = inputs(tmp_path, capsys)
    trace = []
    assert probe.main([*args, "--confirm-live-rights"], opener=scripted(trace, reflected=True)) == 1
    result = capsys.readouterr().out
    assert _SENTINEL not in result and json.loads(result)["stop_reason"] == "reflected_credential"
    assert len(trace) == 2
    db, = directory.iterdir()
    assert _SENTINEL.encode() not in db.read_bytes()


def test_refuses_missing_rights_unpinned_manifest_and_public_token(tmp_path, capsys):
    args, directory, bearer, manifest = inputs(tmp_path, capsys)
    trace = []
    with pytest.raises(SystemExit, match="2"):
        probe.main(args, opener=scripted(trace))
    assert not directory.exists()
    original = manifest.read_bytes()
    manifest.write_bytes(original + b"\n")
    with pytest.raises(SystemExit, match="2"):
        probe.main([*args, "--confirm-live-rights"], opener=scripted(trace))
    assert not directory.exists()
    manifest.write_bytes(original)
    bearer.chmod(0o644)
    with pytest.raises(SystemExit, match="2"):
        probe.main([*args, "--confirm-live-rights"], opener=scripted(trace))
    assert not trace and not directory.exists()
    assert _SENTINEL not in capsys.readouterr().err


def test_rejects_wrong_queue_and_changed_source_before_checkpoint_or_credentials(tmp_path, capsys, monkeypatch):
    args, directory, _, _ = inputs(tmp_path, capsys)
    monkeypatch.setattr(probe, "_read_bearer", lambda *_: pytest.fail("read credential before source pin"))
    bad = list(args)
    bad[bad.index("--queue-sha256") + 1] = "0" * 64
    for variant in (bad, args):
        if variant is args:
            movie = tmp_path / "movie_ids_01_10_2026.json.gz"
            movie.write_bytes(gzip.compress(b'{"id":311,"adult":false}\n{"id":900,"adult":true}\n'))
        with pytest.raises(SystemExit, match="2"):
            probe.main([*variant, "--confirm-live-rights"], opener=lambda *_: pytest.fail("unexpected dispatch"))
        assert not directory.exists()


def test_existing_or_broken_output_entry_refuses_before_reading_credential(tmp_path, capsys, monkeypatch):
    args, directory, _, _ = inputs(tmp_path, capsys)
    monkeypatch.setattr(probe, "_read_bearer", lambda *_: pytest.fail("read credential with existing destination"))
    directory.mkdir()
    with pytest.raises(SystemExit, match="2"):
        probe.main([*args, "--confirm-live-rights"], opener=lambda *_: pytest.fail("unexpected dispatch"))
    assert not list(directory.iterdir())
    directory.rmdir()
    directory.symlink_to(tmp_path / "missing")
    with pytest.raises(SystemExit, match="2"):
        probe.main([*args, "--confirm-live-rights"], opener=lambda *_: pytest.fail("unexpected dispatch"))
    assert directory.is_symlink() and not directory.exists()


def test_destination_race_is_still_refused_by_exclusive_mkdir(tmp_path, capsys, monkeypatch):
    args, directory, _, _ = inputs(tmp_path, capsys)

    def competing_creator(_):
        directory.mkdir()
        return _SENTINEL

    monkeypatch.setattr(probe, "_read_bearer", competing_creator)
    with pytest.raises(SystemExit, match="2"):
        probe.main([*args, "--confirm-live-rights"], opener=lambda *_: pytest.fail("unexpected dispatch"))
    assert not list(directory.iterdir())

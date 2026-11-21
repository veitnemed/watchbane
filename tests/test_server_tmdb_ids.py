"""Only synthetic gzip fixtures: no external data, credentials or dispatch."""
from datetime import date
import gzip
import hashlib
import json

import pytest

from web import tmdb_ids


DAY = date(2026, 1, 2)


def _write(path, rows):
    body = "".join(json.dumps(row) + "\n" for row in rows).encode()
    path.write_bytes(gzip.compress(body, mtime=0))
    return path


def _sources(root, movie, tv):
    root.mkdir(exist_ok=True)
    return (_write(root / "movie_ids_01_02_2026.json.gz", movie),
            _write(root / "tv_series_ids_01_02_2026.json.gz", tv))


def _plan(pair, cap=5, day=DAY):
    return tmdb_ids.plan_daily_ids(export_date=day, movie_file=pair[0], tv_file=pair[1],
                                   per_media_limit=cap)


def test_typed_pair_preserves_homonym_id_and_does_not_invent_metadata(tmp_path):
    verified = {"id": 88, "adult": False}
    pair = _sources(tmp_path, [verified, verified, {"id": 99, "adult": True}, {"id": 100},
                               {"id": 101, "adult": 0}], [verified])
    result = _plan(pair)
    assert [item.key for item in result.queue] == ["tmdb:movie:88", "tmdb:tv:88"]
    assert [item.tmdb_id for item in result.queue] == [88, 88]
    assert result.sources[0].rows == 5
    assert result.sources[0].adult_rows == 1
    assert result.sources[0].unknown_adult_rows == 2
    manifest = result.manifest()
    result.require_same_inputs(json.loads(json.dumps(manifest)))
    assert [row["compressed_sha256"] for row in manifest["sources"]] == [
        hashlib.sha256(path.read_bytes()).hexdigest() for path in pair
    ]


def test_hash_sample_is_order_independent_but_resume_pins_exact_bytes_and_caps(tmp_path):
    rows = [{"id": i, "adult": False} for i in range(1, 100)]
    tv = [{"id": 9, "adult": False}]
    first = _plan(_sources(tmp_path / "first", rows, tv), cap=4)
    changed_pair = _sources(tmp_path / "other", rows[::-1] + rows, tv)
    second = _plan(changed_pair, cap=4)
    expected = sorted(range(1, 100), key=lambda i: hashlib.sha256(f"movie:{i}".encode()).digest())[:4]
    assert [item.tmdb_id for item in first.queue] == expected + [9]
    assert first.queue == second.queue
    assert first.manifest()["queue_sha256"] == second.manifest()["queue_sha256"]
    with pytest.raises(ValueError, match="new checkpoint"):
        second.require_same_inputs(first.manifest())
    with pytest.raises(ValueError, match="new checkpoint"):
        _plan(changed_pair, cap=3).require_same_inputs(second.manifest())


@pytest.mark.parametrize("row", [
    [], {"id": True}, {"id": 0}, {"id": 2**31}, {"id": "12"},
    {"id": 3, "adult": False, "media_type": "movie"},
])
def test_rejects_invalid_or_cross_typed_rows_in_tail_even_after_cap(tmp_path, row):
    valid = {"id": 62, "adult": False}
    with pytest.raises(ValueError, match="row 2"):
        _plan(_sources(tmp_path, [valid], [valid, row]), cap=1)


@pytest.mark.parametrize("cap", [False, 0, 5001, 2.5])
def test_requires_real_bounded_positive_cap(tmp_path, cap):
    with pytest.raises(ValueError, match="per_media_limit"):
        _plan((tmp_path / "missing", tmp_path / "missing"), cap=cap)


def test_requires_expected_dated_names_and_good_complete_gzip(tmp_path):
    valid = {"id": 62, "adult": False}
    pair = _sources(tmp_path, [valid], [valid])
    with pytest.raises(ValueError, match="movie_ids"):
        _plan(pair[::-1])
    with pytest.raises(ValueError, match="01_03_2026"):
        _plan(pair, day=date(2026, 1, 3))
    pair[1].write_bytes(pair[1].read_bytes()[:-3])
    with pytest.raises(ValueError, match="truncated gzip"):
        _plan(pair)


@pytest.mark.parametrize(("limit", "value", "error"), [
    ("MAX_COMPRESSED", 5, "compressed"), ("MAX_EXPANDED", 30, "expanded"),
    ("MAX_LINE", 10, "line"), ("MAX_ROWS", 1, "row"),
])
def test_enforces_resource_bounds(tmp_path, monkeypatch, limit, value, error):
    rows = [{"id": 62, "adult": False}, {"id": 63, "adult": False}]
    pair = _sources(tmp_path, rows, rows)
    monkeypatch.setattr(tmdb_ids, limit, value)
    with pytest.raises(ValueError, match=error):
        _plan(pair)


def test_reports_zero_eligible_without_claiming_full_catalog(tmp_path):
    result = _plan(_sources(tmp_path, [{"id": 1}], [{"id": 2, "adult": True}]))
    assert result.queue == ()
    assert result.sources[0].unknown_adult_rows == 1
    assert result.sources[1].adult_rows == 1


def test_rejects_non_json_or_empty_export(tmp_path):
    pair = _sources(tmp_path, [{"id": 62, "adult": False}], [])
    with pytest.raises(ValueError, match="empty export"):
        _plan(pair)
    pair[1].write_bytes(gzip.compress(b'not json\n'))
    with pytest.raises(ValueError, match="invalid UTF-8 JSON"):
        _plan(pair)

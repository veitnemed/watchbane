from hashlib import sha256
import json

import pytest

from candidates.story_seed_snapshot import StorySeedSnapshotError, load_seed_snapshot
from web import story_catalog_multilingual as catalog


def _row(kind="tv", language="ko-KR", synopsis="  한국어 설명  "):
    return {
        "id": f"tmdb:{kind}:7", "media_type": kind, "tmdb_id": 7, "title": "Synthetic",
        "overview": synopsis, "year": 2021, "synopsis_locale": language, "original_language": "ko",
        "evidence": {"source": "provider_translation_record", "provider_locale": language,
                     "synopsis_sha256": sha256(synopsis.encode()).hexdigest()},
    }


def _file(path, *rows, format=catalog.FORMAT):
    blob = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in ({"format": format}, *rows)).encode()
    path.write_bytes(blob)
    return sha256(blob).hexdigest()


def test_exact_typed_tags_roundtrip_and_do_not_change_desktop_parser(tmp_path):
    file = tmp_path / "operator.jsonl"
    pin = _file(file, _row(), _row("movie", "ru-RU", "Русский текст"))
    tv, movie = catalog.load_operator_catalog(file, expected_sha256=pin)
    assert (tv.key, tv.synopsis_locale, tv.original_language) == ("tmdb:tv:7", "ko-KR", "ko")
    assert (movie.key, movie.synopsis_locale, movie.original_language) == ("tmdb:movie:7", "ru-RU", "ko")
    assert tv.overview == "  한국어 설명  "  # exact reviewed bytes, not normalized
    with pytest.raises(StorySeedSnapshotError):
        load_seed_snapshot(file)
    file.write_bytes(file.read_bytes().replace(b'"Synthetic"', b'"Substituted"', 1))
    with pytest.raises(ValueError, match="SHA-256"):
        catalog.load_operator_catalog(file, expected_sha256=pin)


def test_rejects_duplicate_cross_typed_untagged_mismatched_and_bad_version(tmp_path):
    file = tmp_path / "operator.jsonl"
    row = _row()
    for rows in (
        (row, row),
        ({**row, "id": "tmdb:movie:7"},),
        ({**row, "requested_locale": "ko-KR"},),
        ({**row, "tmdb_id": True},),
        ({**row, "overview": " altered"},),
        ({**row, "synopsis_locale": "en-US"},),
        ({**row, "synopsis_locale": "ko"},),
        ({**row, "evidence": {**row["evidence"], "source": "details_request"}},),
    ):
        with pytest.raises(ValueError, match="entry at line"):
            catalog.load_operator_catalog(file, expected_sha256=_file(file, *rows))
    with pytest.raises(ValueError, match="line 1"):
        catalog.load_operator_catalog(file, expected_sha256=_file(file, row, format="unrecognized"))


@pytest.mark.parametrize(("bound", "value"), [
    ("MAX_LINE_BYTES", 60), ("MAX_FILE_BYTES", 30), ("MAX_ROWS", 1),
])
def test_shared_reader_limits_fail_closed(tmp_path, monkeypatch, bound, value):
    file = tmp_path / "operator.jsonl"
    pin = _file(file, _row(), _row("movie"))
    monkeypatch.setattr(catalog, bound, value)
    with pytest.raises(ValueError, match="limits|bounded"):
        catalog.load_operator_catalog(file, expected_sha256=pin)


def test_pin_is_explicit_and_header_alone_is_not_a_catalog(tmp_path):
    file = tmp_path / "operator.jsonl"
    pin = _file(file)
    with pytest.raises(ValueError, match="exact SHA"):
        catalog.load_operator_catalog(file, expected_sha256="any")
    with pytest.raises(ValueError, match="no descriptions"):
        catalog.load_operator_catalog(file, expected_sha256=pin)

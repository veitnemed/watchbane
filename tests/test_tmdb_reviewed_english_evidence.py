"""Synthetic private QA receipts only: no provider contact, source, or rights grant."""
from dataclasses import FrozenInstanceError, replace
from hashlib import sha256
import json
from pathlib import Path
import socket

import pytest

from web.tmdb_ids import QueueItem
from web.tmdb_reviewed_english_evidence import ReviewedAppendedDetail, verify_private_english_synopsis


_MOVIE, _TV = QueueItem("movie", 42), QueueItem("tv", 42)
_EN = "A synthetic investigator revisits an old case."


def _translation(region, code, overview):
    return {"iso_639_1": code, "iso_3166_1": region, "data": {"overview": overview}}


def _body(item=_MOVIE):
    return {"id": item.tmdb_id, "title" if item.media_type == "movie" else "name": "Untyped title language",
            "adult": False, "overview": "Нет признака языка у этого текста.", "original_language": "ko",
            "translations": {"translations": [_translation("US", "en", " " + _EN + " ")]}}


def _url(item):
    return f"https://api.themoviedb.org/3/{item.media_type}/{item.tmdb_id}?language=ru-RU&append_to_response=translations"


def _pin(item, body):
    raw = json.dumps(body, ensure_ascii=False).encode() if not isinstance(body, bytes) else body
    return ReviewedAppendedDetail(item, _url(item), 200, sha256(raw).hexdigest(),
                                  "en-US", sha256(_EN.encode()).hexdigest(), "private_qa"), raw


def _verify(item, body):
    review, raw = _pin(item, body)
    return verify_private_english_synopsis(review=review, evidence=raw, use_cleared=True)


def test_exact_en_translation_and_original_distinct_without_io(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("This bridge must not read or write a file or contact a provider")

    monkeypatch.setattr(Path, "open", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    source = _body()
    review, raw = _pin(_MOVIE, source)
    proposal = verify_private_english_synopsis(review=review, evidence=raw, use_cleared=True)
    assert (proposal.item, proposal.overview, proposal.synopsis_locale, proposal.original_language) == (
        _MOVIE, _EN, "en-US", "ko",
    )
    assert proposal.evidence_sha256 == sha256(raw).hexdigest()
    assert proposal.synopsis_sha256 == sha256(_EN.encode()).hexdigest()
    assert not hasattr(proposal, "title")
    with pytest.raises(FrozenInstanceError):
        proposal.overview = "forged"
    assert source == _body()
    assert _verify(_TV, _body(_TV)).item == _TV


@pytest.mark.parametrize("adult", [None, True, 0, 1, "false", [], {}])
def test_adult_must_be_literal_false_in_same_exact_details(adult):
    with pytest.raises(ValueError, match="explicit adult:false"):
        _verify(_MOVIE, _body() | {"adult": adult})


def test_missing_adult_or_original_context_and_wrong_typed_response():
    for field in ("adult", "original_language"):
        body = _body()
        del body[field]
        with pytest.raises(ValueError, match="exact typed Details"):
            _verify(_MOVIE, body)
    for body in (_body(_TV), _body() | {"media_type": "tv"}, _body() | {"id": True},
                 _body() | {"id": 43}, _body() | {"success": False}, _body() | {"original_language": "ko-KR"}):
        with pytest.raises(ValueError, match="exact typed Details"):
            _verify(_MOVIE, body)


def test_same_number_different_typed_receipt_or_appended_context_refused():
    review, raw = _pin(_MOVIE, _body())
    with pytest.raises(ValueError, match="typed, pinned"):
        verify_private_english_synopsis(review=replace(review, item=_TV), evidence=raw, use_cleared=True)
    with pytest.raises(ValueError, match="typed ID mismatch"):
        _verify(_MOVIE, _body() | {"translations": _body()["translations"] | {"media_type": "tv"}})
    with pytest.raises(ValueError, match="typed ID mismatch"):
        _verify(_MOVIE, _body() | {"translations": _body()["translations"] | {"id": 43}})


def test_russian_or_original_translation_not_demoted_and_locale_hint_not_evidence():
    body = _body()
    for competing in (_translation("RU", "ru", "Русское описание остаётся."),
                      _translation("KR", "ko", "한국어 설명")):
        alternate = body["translations"]["translations"] + [competing]
        with pytest.raises(ValueError, match="No exact reviewed en-US fallback"):
            _verify(_MOVIE, body | {"translations": {"translations": alternate}})
    for absent in ([], [_translation("US", "en", " ")], [_translation("GB", "en", _EN)]):
        with pytest.raises(ValueError, match="No exact reviewed en-US fallback"):
            _verify(_MOVIE, body | {"translations": {"translations": absent}, "overview": _EN})
    no_translations = dict(body, overview=_EN, language="en-US")
    no_translations.pop("translations")
    with pytest.raises(ValueError, match="No exact reviewed en-US fallback"):
        _verify(_MOVIE, no_translations)


def test_late_replacement_wrong_pin_or_standalone_context_does_not_pass():
    review, raw = _pin(_MOVIE, _body())
    for wrong in (
        replace(review, response_url="https://example.invalid/3/movie/42?language=ru-RU&append_to_response=translations"),
        replace(review, response_url="https://api.themoviedb.org/3/movie/42/translations"),
        replace(review, response_url="https://api.themoviedb.org/3/movie/42?language=en-US"),
        replace(review, status=True),
        replace(review, status=304),
        replace(review, response_sha256="f" * 64),
        replace(review, synopsis_locale="en-GB"),
    ):
        with pytest.raises(ValueError, match="typed, pinned"):
            verify_private_english_synopsis(review=wrong, evidence=raw, use_cleared=True)
    with pytest.raises(ValueError, match="typed, pinned"):
        verify_private_english_synopsis(review=review, evidence=raw + b" ", use_cleared=True)
    with pytest.raises(ValueError, match="No exact reviewed en-US"):
        verify_private_english_synopsis(review=replace(review, synopsis_sha256="a" * 64),
                                        evidence=raw, use_cleared=True)
    for replacement, cleared in ((replace(review, intended_use="publication"), True), (review, 1), (review, False)):
        with pytest.raises(PermissionError, match="private QA"):
            verify_private_english_synopsis(review=replacement, evidence=raw, use_cleared=cleared)


def test_malformed_or_conflicting_raw_fields_do_not_yield_candidates():
    repeated = json.dumps(_body(), ensure_ascii=False).replace('"adult": false', '"adult": true, "adult": false')
    nonjson = json.dumps(_body() | {"budget": float("nan")}, ensure_ascii=False)
    for raw in (repeated.encode(), nonjson.encode(), b"\xff"):
        with pytest.raises(ValueError, match="exact typed Details"):
            _verify(_MOVIE, raw)
    body = _body()
    body["translations"]["translations"].append(_translation("US", "en", "Different pinned-looking synopsis"))
    with pytest.raises(ValueError, match="Conflicting overviews"):
        _verify(_MOVIE, body)


def test_literal_nonadult_flag_does_not_bypass_existing_explicit_text_gate():
    visible = "A synthetic overview with graphic sex."
    body = _body() | {"translations": {"translations": [_translation("US", "en", visible)]}}
    review, raw = _pin(_MOVIE, body)
    with pytest.raises(ValueError, match="text safety gate") as denied:
        verify_private_english_synopsis(review=replace(review, synopsis_sha256=sha256(visible.encode()).hexdigest()),
                                        evidence=raw, use_cleared=True)
    assert visible not in str(denied.value)

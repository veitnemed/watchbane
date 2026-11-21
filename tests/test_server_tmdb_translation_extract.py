import hashlib
import json

import pytest

from web.tmdb_ids import QueueItem
from web.tmdb_translation_extract import MAX_BODY_BYTES, TypedFixture, select_translation


MOVIE = QueueItem("movie", 42)
TV = QueueItem("tv", 42)


def _fixture(item, **body):
    return TypedFixture(item, json.dumps({"id": item.tmdb_id, **body}, ensure_ascii=False).encode())


def _row(lang, region, text):
    return {"iso_639_1": lang, "iso_3166_1": region, "data": {"overview": text}}


def test_russian_tag_and_region_are_preferred_independently_of_detail_request():
    rows = [_row("ru", "KZ", "Другой вариант"), _row("ru", "RU", "Точное описание"),
            _row("ko", "KR", "한국어 설명"), _row("en", "US", "English")]
    for listing in (rows, rows[::-1]):
        result = select_translation(_fixture(MOVIE, original_language="ko", overview="Different untagged text",
                                             translations={"translations": listing}))
        assert result.item == MOVIE
        assert (result.locale_tag, result.choice, result.equals_untagged_detail) == ("ru-RU", "russian", False)
        assert result.sha256 == hashlib.sha256("Точное описание".encode()).hexdigest()


@pytest.mark.parametrize(("rows", "tag", "choice"), [
    ([_row("ko", "KR", "한국어 설명"), _row("en", "US", "English")], "ko-KR", "original"),
    ([_row("ko", "KR", "한국어 설명")], "ko-KR", "original"),
    ([_row("ru", "RU", "  "), _row("en", "GB", "British"), _row("en", "US", "English")], "en-US", "english"),
    ([_row("en", "GB", "Different")], "en-GB", "english"),
])
def test_original_and_english_fallback_are_explicit(rows, tag, choice):
    result = select_translation(_fixture(TV, original_language="ko", overview="English"),
                                _fixture(TV, translations=rows))
    assert result.item == TV
    assert (result.locale_tag, result.choice) == (tag, choice)
    assert result.equals_untagged_detail == (result.overview == "English")


def test_equal_text_does_not_prove_untagged_detail_language_on_its_own():
    same = _row("ru", "RU", " Описание ")
    details = _fixture(MOVIE, original_language="ru", overview="Описание")
    assert select_translation(details) is None
    assert select_translation(details, _fixture(MOVIE, translations=[])) is None
    assert select_translation(details, _fixture(MOVIE, translations=[_row("ru", "RU", None)])) is None
    result = select_translation(details, _fixture(MOVIE, translations=[same, same]))
    assert result.equals_untagged_detail and result.overview == "Описание"


def test_rejects_mismatched_typed_context_or_embedded_id():
    details = _fixture(MOVIE, overview="Story")
    with pytest.raises(ValueError, match="typed ID"):
        select_translation(details, _fixture(TV, translations=[]))
    with pytest.raises(ValueError, match="typed ID"):
        select_translation(details, _fixture(MOVIE, id=43, translations=[]))
    with pytest.raises(ValueError, match="typed ID"):
        select_translation(_fixture(MOVIE, translations={"id": 43, "translations": []}))


def test_rejects_oversized_ambiguous_or_invalid_evidence():
    good = _fixture(MOVIE, overview="Story")
    with pytest.raises(ValueError, match="byte limit"):
        select_translation(good, TypedFixture(MOVIE, b" " * (MAX_BODY_BYTES + 1)))
    with pytest.raises(ValueError, match="oversized overview"):
        select_translation(good, _fixture(MOVIE, translations=[_row("en", "US", "x" * 8193)]))
    with pytest.raises(ValueError, match="Conflicting"):
        select_translation(good, _fixture(MOVIE, translations=[_row("ru", "RU", "One"), _row("ru", "RU", "Two")]))
    with pytest.raises(ValueError, match="Invalid JSON"):
        select_translation(TypedFixture(MOVIE, b'{"id":42,"id":42}'))

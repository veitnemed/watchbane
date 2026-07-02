from config import constant
from config import scheme
from common import format_score
from common import valid
from storage.normalize import normalize_raw_scores


def test_raw_scores_schema_contains_only_tmdb_fields() -> None:
    assert scheme.get_fields(scheme.RAW_SCORES) == [
        "tmdb_score",
        "tmdb_votes",
        "tmdb_popularity",
    ]
    assert constant.RAW_SCORES == [
        "tmdb_score",
        "tmdb_votes",
        "tmdb_popularity",
    ]


def test_raw_score_labels_and_translations_are_tmdb_only() -> None:
    assert constant.FIELD_LABELS["tmdb_score"] == "Рейтинг TMDb"
    assert constant.FIELD_LABELS["tmdb_votes"] == "Голоса TMDb"
    assert constant.FIELD_LABELS["tmdb_popularity"] == "Популярность TMDb"
    assert constant.TRANSLATION["meta features"] == {
        "year": "Year",
        "tmdb_score": "TMDb score",
        "tmdb_votes": "TMDb votes",
        "tmdb_popularity": "TMDb popularity",
    }

    raw_labels = {constant.FIELD_LABELS.get(field, "") for field in constant.RAW_SCORES}
    assert all("Kinopoisk" not in label and "IMDb" not in label for label in raw_labels)
    assert all("Кинопоиск" not in label and "IMDb" not in label for label in raw_labels)


def test_raw_to_struct_uses_only_tmdb_active_fields() -> None:
    computed = format_score.raw_to_struct(
        {
            "tmdb_score": 7.8,
            "tmdb_votes": 1200,
            "tmdb_popularity": 42.5,
            "kp_score": 9.9,
            "kp_votes": 100000,
            "imdb_score": 8.8,
            "imdb_votes": 2000,
        },
        {"year": 2020},
    )

    assert computed == {
        "tmdb_score": 7.8,
        "tmdb_votes": 1200,
        "tmdb_popularity": 42.5,
    }


def test_normalize_and_validate_raw_scores_drop_legacy_fields() -> None:
    raw = {
        "tmdb_score": "8.1",
        "tmdb_votes": "1200",
        "tmdb_popularity": "44.2",
        "kp_score": "9.9",
        "imdb_score": "8.8",
    }

    assert normalize_raw_scores(raw) == {
        "tmdb_score": 8.1,
        "tmdb_votes": 1200,
        "tmdb_popularity": 44.2,
    }
    assert valid.is_valid_raw_meta(raw) is False
    assert valid.is_valid_raw_meta({
        "tmdb_score": 8.1,
        "tmdb_votes": 1200,
        "tmdb_popularity": 44.2,
    }) is True

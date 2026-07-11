from dataset.models.user_rating import (
    UserRating,
    is_valid_user_rating,
    legacy_score_to_user_rating,
    normalize_user_rating,
)


def test_user_rating_has_exactly_three_integer_values() -> None:
    assert [int(value) for value in UserRating] == [1, 2, 3]
    assert normalize_user_rating(None) is None
    assert [normalize_user_rating(value) for value in (1, 2, 3)] == [1, 2, 3]


def test_user_rating_rejects_values_outside_contract() -> None:
    for value in (0, 4, 1.0, 2.5, "1", True, object()):
        assert is_valid_user_rating(value) is False
        assert normalize_user_rating(value) is None


def test_legacy_score_mapping_boundaries() -> None:
    assert [legacy_score_to_user_rating(value) for value in (0, 4.9, 5, 7.9, 8, 10, None)] == [
        1,
        1,
        2,
        2,
        3,
        3,
        None,
    ]

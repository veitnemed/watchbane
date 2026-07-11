"""Canonical three-level user reaction contract."""

from __future__ import annotations

from enum import IntEnum
from typing import Any


class UserRating(IntEnum):
    NOT_FOR_ME = 1
    OK = 2
    TOP = 3


def is_valid_user_rating(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value in UserRating._value2member_map_


def normalize_user_rating(value: Any) -> int | None:
    if isinstance(value, UserRating):
        return int(value)
    return int(value) if is_valid_user_rating(value) else None


def legacy_score_to_user_rating(value: Any) -> int | None:
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        score = float(value)
    except (TypeError, ValueError):
        return None
    if 0.0 <= score < 5.0:
        return int(UserRating.NOT_FOR_ME)
    if 5.0 <= score < 8.0:
        return int(UserRating.OK)
    if 8.0 <= score <= 10.0:
        return int(UserRating.TOP)
    return None

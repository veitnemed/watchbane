"""Validation helpers for user input and project data structures."""

import unicodedata

from config import constant

VALID_YEAR_MIN = 1900


def parse_float(value) -> float:
    """Convert a string with dot or comma to float."""
    return float(str(value).replace(",", "."))


def is_valid_features(features: dict) -> bool:
    """Check that feature keys match the current model schema."""
    return set(constant.FEATURES) == set(features.keys())


def has_control_characters(text: str) -> bool:
    """Return True when the string contains control characters."""
    return any(unicodedata.category(char).startswith("C") for char in text)


def is_correct_title(title):
    """Validate title-like input while allowing normal punctuation."""
    title = str(title).strip()
    if title == "":
        return False
    return has_control_characters(title) is False


def is_correct_score(score: str):
    """Check score validity."""
    try:
        score_float = parse_float(score)
        return 0 <= score_float <= 10
    except:
        return False


def is_correct_year(year: str) -> bool:
    """Check year validity."""
    try:
        year_int = int(year)
        return VALID_YEAR_MIN <= year_int <= constant.NOW_YEAR
    except:
        return False


def is_correct_country(country: str) -> bool:
    """Validate country input."""
    country = str(country or "").strip()
    if country == "":
        return True
    return has_control_characters(country) is False


def is_correct_main_menu_command(command: str):
    """Check main menu command."""
    return command in constant.COMMANDS


def is_correct_votes(votes: str) -> bool:
    """Check votes count validity."""
    try:
        votes_int = int(votes)
        return votes_int >= 0
    except:
        return False


def is_valid_raw_meta(raw: dict) -> bool:
    """Validate raw meta payload."""
    if isinstance(raw, dict) is False:
        return False
    supported_fields = set(constant.RAW_META_FIELDS)
    if set(raw.keys()).issubset(supported_fields) is False:
        return False

    for score_field in ("tmdb_score",):
        if score_field in raw and is_correct_score(raw[score_field]) is False:
            return False
    if "tmdb_popularity" in raw:
        try:
            if parse_float(raw["tmdb_popularity"]) < 0:
                return False
        except (TypeError, ValueError):
            return False

    for votes_field in ("tmdb_votes",):
        if votes_field in raw and is_correct_votes(raw[votes_field]) is False:
            return False

    return True


def is_tags_score(score: str, max_value: int = 1) -> bool:
    """Check tag score validity."""
    try:
        score_int = int(score)
        if max_value is None:
            return score_int >= 0
        return 0 <= score_int <= max_value
    except:
        return False


def is_correct_select_menu(max_value: int, n: int) -> bool:
    """Check menu item selection."""
    try:
        n_int = int(n)
        return 0 <= n_int <= max_value
    except (TypeError, ValueError):
        return False


def is_correct_noise_delta(value: str) -> bool:
    """Check noise delta for benchmark input."""
    if value.strip() == "":
        return True
    try:
        delta = parse_float(value)
        return 0 <= delta <= 10
    except ValueError:
        return False


def is_correct_noise_runs(value: str) -> bool:
    """Check benchmark runs input."""
    if value.strip() == "":
        return True
    try:
        runs = int(value)
        return runs > 0
    except ValueError:
        return False


def is_correct_top_n(value: str) -> bool:
    """Check top-N input."""
    try:
        top_n = int(value)
        return top_n > 0
    except ValueError:
        return False


VALIDATORS = {
    "score": is_correct_score,
    "year": is_correct_year,
    "votes": is_correct_votes,
    "tags_score": is_tags_score,
    "title": is_correct_title,
    "country": is_correct_country,
}

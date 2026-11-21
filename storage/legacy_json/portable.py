"""Strict, machine-independent preference subset for portable collection exports."""

from math import isfinite


OMITTED_MEMBERS = ("cache/posters/posters.json", "candidates/pool.json", "candidates/criteria.json")


def portable_settings(values: dict) -> dict:
    result = {}
    for key, value in values.items():
        if key in ("interface_language", "data_language"):
            if type(value) is str and value in ("ru", "en"):
                result[key] = value
        elif key == "ui_scale":
            if type(value) in (int, float) and 0.50 <= value <= 2.00 and isfinite(value):
                result[key] = value
        elif key in ("auto_pool_refill", "fts_search_enabled"):
            if type(value) is bool:
                result[key] = value
    return result

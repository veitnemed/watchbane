"""Facade for SQLite watched dataset, meta, and identity repositories."""

from __future__ import annotations

from storage.sqlite.watched_identity import (
    find_exact_title,
    find_watched_identity,
    is_origin_title,
)
from storage.sqlite.watched_meta import get_meta_obj, load_meta_dict, save_meta_dict
from storage.sqlite.watched_read import load_dataset_dict
from storage.sqlite.watched_write import delete_watched, save_dataset_dict


__all__ = [
    "delete_watched",
    "find_exact_title",
    "find_watched_identity",
    "get_meta_obj",
    "is_origin_title",
    "load_dataset_dict",
    "load_meta_dict",
    "save_dataset_dict",
    "save_meta_dict",
]

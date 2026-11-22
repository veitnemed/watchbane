"""Opaque TMDb relative artwork names; this helper never resolves them."""
import re


_POSTER_NAME = re.compile(r"/[A-Za-z0-9_-]+\.(?:jpg|png|webp)", re.ASCII)


def is_provider_poster_path(value):
    return type(value) is str and len(value) <= 128 and _POSTER_NAME.fullmatch(value) is not None

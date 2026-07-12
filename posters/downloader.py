"""Poster download facade."""

from __future__ import annotations


def download_preview_posters_for_urls(urls, **kwargs):
    from posters.download_images import download_preview_posters_for_urls as download

    return download(urls, **kwargs)


def download_poster_for_title(title: str, year, **kwargs):
    from posters.download_images import download_poster_for_title as download

    return download(title, year, **kwargs)


def local_preview_poster_path_if_cached(poster_url: str) -> str | None:
    from posters.download_images import local_preview_poster_path_if_cached

    return local_preview_poster_path_if_cached(poster_url)

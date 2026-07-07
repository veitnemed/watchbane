"""Add-title resolve bundle dataclass and builders."""

from __future__ import annotations

from dataclasses import dataclass

from dataset import title_resolve
from dataset.add_flow.preview import build_preview_card_from_defaults, build_preview_movie_from_defaults


@dataclass(frozen=True)
class AddTitleResolveBundle:
    """Resolved add-title data ready for preview and save."""

    title: str
    country: str
    defaults: dict
    meta_payload: dict
    poster_hints: dict
    preview_movie: dict
    preview_card: dict
    found: bool
    statuses: dict
    pool_candidate: dict | None = None


def resolve_title_for_add(
    title: str,
    country: str = "",
    *,
    on_progress=None,
    data_language: str = "ru",
) -> AddTitleResolveBundle:
    """Resolve title through SQL/KP/TMDb and build preview card data."""
    resolved = title_resolve.resolve_title_data_for_add(
        title,
        country,
        on_progress=on_progress,
        data_language=data_language,
    )
    return build_add_title_resolve_bundle(resolved, data_language=data_language)


def build_add_title_resolve_bundle(resolved: dict, data_language: str = "ru") -> AddTitleResolveBundle:
    """Build preview/save bundle from resolve_title_data_for_add result."""
    defaults = resolved.get("defaults")
    if defaults is None:
        defaults = title_resolve.build_empty_add_defaults(resolved["title"])

    meta_payload = title_resolve.build_add_meta_payload(resolved)
    poster_hints = title_resolve.build_poster_hints_from_resolve(resolved)
    preview_movie = build_preview_movie_from_defaults(defaults)
    preview_card = build_preview_card_from_defaults(
        defaults,
        resolved=resolved,
        meta_payload=meta_payload,
        poster_hints=poster_hints,
        data_language=data_language,
    )

    return AddTitleResolveBundle(
        title=str(resolved.get("title") or ""),
        country=str(resolved.get("country") or ""),
        defaults=defaults,
        meta_payload=meta_payload,
        poster_hints=poster_hints,
        preview_movie=preview_movie,
        preview_card=preview_card,
        found=bool(resolved.get("found")),
        statuses=dict(resolved.get("statuses") or {}),
    )

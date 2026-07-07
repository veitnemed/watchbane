"""Candidate pool -> watched add-title bundle."""

from dataset import title_resolve
from dataset.add_flow.bundle import AddTitleResolveBundle
from dataset.add_flow.preview import build_preview_card_from_defaults, build_preview_movie_from_defaults
from config import scheme
from dataset.language import choose_display_overview


def build_candidate_transfer_bundle(candidate: dict, data_language: str = "ru") -> AddTitleResolveBundle:
    """Build preview/save bundle for transferring a pool candidate to watched."""
    transfer = title_resolve.build_candidate_transfer_payload(candidate)
    defaults = transfer["defaults"]
    meta_payload = transfer["meta_payload"]
    poster_hints = title_resolve.build_poster_hints_from_candidate(candidate)
    preview_movie = build_preview_movie_from_defaults(defaults)
    description = (
        choose_display_overview(candidate, data_language)
        or meta_payload.get("description")
        or candidate.get("overview")
        or candidate.get("description")
    )
    preview_card = build_preview_card_from_defaults(
        defaults,
        resolved={"source_values": {"description": description}},
        meta_payload=meta_payload,
        poster_hints=poster_hints,
        data_language=data_language,
    )
    main_info = defaults.get(scheme.MAIN_INFO, {})
    return AddTitleResolveBundle(
        title=str(main_info.get("title") or candidate.get("title") or ""),
        country=str(main_info.get("country") or ""),
        defaults=defaults,
        meta_payload=meta_payload,
        poster_hints=poster_hints,
        preview_movie=preview_movie,
        preview_card=preview_card,
        found=True,
        statuses={},
        pool_candidate=dict(candidate),
    )

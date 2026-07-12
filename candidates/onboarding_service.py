"""Onboarding autofill and candidate-pool replenishment use cases."""

from __future__ import annotations

from candidates.models.keys import COMMON_POOL_CRITERIA_NAME
from candidates.onboarding.autofill import (
    CountrySelection,
    OnboardingTasteProfile,
    STARTER_POOL_TARGET,
    TmdbAutofillClient,
    build_country_plan,
    build_fetch_buckets,
    media_weights,
    origin_weights,
    release_weights,
    run_onboarding_autofill,
    should_start_onboarding_autofill,
    vibe_weights,
)
from candidates.repositories.pool_repository import load_candidate_pool
from candidates.replenish.filter_replenisher import replenish_candidates_for_filters
from candidates.sources.tmdb import importer as tmdb_import


ONBOARDING_LAST_PROFILE_SETTING_KEY = "onboarding_last_profile"
POOL_REPLENISH_THRESHOLD = 40


def should_show_onboarding_autofill() -> bool:
    """Return whether startup should collect taste and build the first pool."""
    return should_start_onboarding_autofill()


def build_onboarding_candidate_pool(profile: OnboardingTasteProfile | dict, *, progress_callback=None, cancel_checker=None) -> dict:
    """Run deterministic onboarding autofill through the public service boundary."""
    taste_profile = _normalize_onboarding_profile(profile)
    result = run_onboarding_autofill(taste_profile, progress_callback=progress_callback, cancel_checker=cancel_checker)
    if result.ok and result.cancelled is False and result.created_count > 0:
        _save_last_onboarding_profile(taste_profile)
    return _autofill_result_to_dict(result)


def _autofill_result_to_dict(result) -> dict:
    return {
        "ok": result.ok, "profile_id": result.profile_id, "created_count": result.created_count,
        "pool_size": result.pool_size, "api_requests": result.api_requests,
        "details_requests": result.details_requests, "adaptive_pages_used": result.adaptive_pages_used,
        "pagination_stop_reasons": result.pagination_stop_reasons,
        "localization_fallback_count": result.localization_fallback_count,
        "overview_fallback_original_language_count": result.overview_fallback_original_language_count,
        "overview_fallback_en_count": result.overview_fallback_en_count,
        "missing_overview_after_fallback": result.missing_overview_after_fallback,
        "cancelled": result.cancelled, "warning": result.warning, "warnings": result.warnings,
        "planned_counts": result.planned_counts, "actual_counts": result.actual_counts,
        "rejected_future_count": result.rejected_future_count,
        "duplicate_requests_skipped": result.duplicate_requests_skipped,
        "quality_gate_rejected_counts": result.quality_gate_rejected_counts or {},
        "quality_gate_rejected_reasons": result.quality_gate_rejected_reasons or {},
        "preference_conflict_count": result.preference_conflict_count,
        "preference_warning_count": result.preference_warning_count,
        "preference_conflict_codes": list(result.preference_conflict_codes),
        "preference_auto_fix_applied": result.preference_auto_fix_applied,
        "preference_diagnostics": result.preference_diagnostics or {}, "candidates": result.candidates,
    }


def _normalize_onboarding_profile(profile: OnboardingTasteProfile | dict) -> OnboardingTasteProfile:
    if isinstance(profile, OnboardingTasteProfile):
        return profile.normalized()
    return OnboardingTasteProfile(
        media_preference=profile.get("media_preference"), release_preference=profile.get("release_preference"),
        vibe_preference=profile.get("vibe_preference"), origin_preference=profile.get("origin_preference"),
        ui_language=profile.get("ui_language"), taste_preset=profile.get("taste_preset"),
        country_selection=profile.get("country_selection"), animation_mode=profile.get("animation_mode", "any"),
        animation_disliked=profile.get("animation_disliked", False), genre_groups=profile.get("genre_groups"),
        include_genres=profile.get("include_genres"), include_genre_mode=profile.get("include_genre_mode", "or"),
        exclude_genres=profile.get("exclude_genres"), min_year=profile.get("min_year"), max_year=profile.get("max_year"),
        discover_pages=profile.get("discover_pages", 3), details_limit=profile.get("details_limit", 50),
        details_enrichment=profile.get("details_enrichment"), pagination=profile.get("pagination"),
    ).normalized()


def _save_last_onboarding_profile(profile: OnboardingTasteProfile) -> None:
    from storage.sqlite.settings_repository import set_setting
    try:
        set_setting(ONBOARDING_LAST_PROFILE_SETTING_KEY, profile.as_repository_dict())
    except Exception:
        pass


def load_last_onboarding_profile() -> dict | None:
    """Return the last successful autofill taste profile, if any."""
    from storage.sqlite.settings_repository import get_setting
    payload = get_setting(ONBOARDING_LAST_PROFILE_SETTING_KEY)
    return payload if isinstance(payload, dict) else None


def get_pool_replenish_view() -> dict:
    """Return whether the candidate pool needs an automatic top-up."""
    pool_size = len(load_candidate_pool())
    profile = load_last_onboarding_profile()
    return {
        "pool_size": pool_size, "threshold": POOL_REPLENISH_THRESHOLD, "target": STARTER_POOL_TARGET,
        "missing": max(0, STARTER_POOL_TARGET - pool_size), "has_profile": profile is not None,
        "needs_replenish": profile is not None and pool_size < POOL_REPLENISH_THRESHOLD,
    }


def replenish_candidate_pool(*, progress_callback=None, cancel_checker=None) -> dict:
    """Top the pool up to the starter target using the last taste profile."""
    view = get_pool_replenish_view()
    if view["has_profile"] is False or view["missing"] <= 0:
        return {"ok": False, "skipped": True, "created_count": 0, **view}
    result = run_onboarding_autofill(
        _normalize_onboarding_profile(load_last_onboarding_profile()), progress_callback=progress_callback,
        cancel_checker=cancel_checker, target=view["missing"],
    )
    payload = _autofill_result_to_dict(result)
    payload["skipped"] = False
    payload["replenish_target"] = view["missing"]
    return payload


class _FilterReplenishTmdbClient:
    """Adapt filter replenish media types to the shared TMDb client."""
    _DISCOVER_PATHS = {"movie": "/discover/movie", "tv": "/discover/tv"}

    def __init__(self, client: TmdbAutofillClient | None = None) -> None:
        self._client = client or TmdbAutofillClient()

    def discover(self, media_type: str, params: dict) -> dict:
        path = self._DISCOVER_PATHS.get(str(media_type or "").strip())
        if path is None:
            raise ValueError(f"Unsupported TMDb media type for filter replenish: {media_type!r}")
        return self._client.discover(path, params)

    def details(self, media_type: str, tmdb_id: int, *, language: str = "ru-RU") -> dict:
        normalized_media_type = str(media_type or "").strip()
        if normalized_media_type == "movie":
            return self._client.movie_details(int(tmdb_id), language=language)
        if normalized_media_type == "tv":
            return self._client.tv_details(int(tmdb_id), language=language)
        raise ValueError(f"Unsupported TMDb media type for filter replenish: {media_type!r}")


def _build_filter_replenish_tmdb_client() -> _FilterReplenishTmdbClient:
    return _FilterReplenishTmdbClient()


def replenish_candidate_pool_for_filters(intent: dict, *, limit: int = 30, tmdb_client=None, progress_callback=None, cancel_checker=None, dry_run: bool = False) -> dict:
    """Replenish the shared candidate pool from explicit GUI filter intent."""
    before_pool = load_candidate_pool()
    before_keys, before_count = set(before_pool), len(before_pool)
    result = replenish_candidates_for_filters(
        intent, limit=limit, tmdb_client=tmdb_client or _build_filter_replenish_tmdb_client(),
        progress_callback=progress_callback, cancel_checker=cancel_checker, dry_run=True, existing_pool=before_pool,
    )
    result.update({"dry_run": bool(dry_run), "before_pool_count": before_count, "after_pool_count": before_count, "added_pool_keys": [], "save_stats": {}})
    if result.get("ok") is not True or result.get("blocked") or result.get("cancelled") or dry_run:
        return result
    candidates = list(result.get("candidates") or [])
    if not candidates:
        return result
    if cancel_checker is not None and cancel_checker():
        result.update({"ok": False, "cancelled": True, "candidates": []})
        return result
    stats = tmdb_import.import_tmdb_candidates_to_common_pool(
        candidates, criteria_name=COMMON_POOL_CRITERIA_NAME,
        result_metadata={
            "source": "filter_replenish",
            "intent": result.get("compatibility", {}).get("intent") or result.get("plan", {}).get("intent"),
            "plan": {key: result.get("plan", {}).get(key) for key in ("target_add_count", "bucket_count", "country_plan", "media_plan")},
        },
    )
    after_pool = load_candidate_pool()
    added_keys = sorted(set(after_pool) - before_keys)
    result.update({"saved_count": len(added_keys), "before_pool_count": before_count, "after_pool_count": len(after_pool), "added_pool_keys": added_keys, "save_stats": stats})
    return result


def get_onboarding_autofill_plan_view(profile: OnboardingTasteProfile | dict) -> dict:
    """Return deterministic onboarding quotas without TMDb calls."""
    taste_profile = _normalize_onboarding_profile(profile)
    buckets = build_fetch_buckets(taste_profile)
    def quota_by(field: str) -> dict[str, int]:
        totals: dict[str, int] = {}
        for bucket in buckets:
            value = getattr(bucket, field)
            if value is not None:
                totals[str(value)] = totals.get(str(value), 0) + int(bucket.quota)
        return totals
    target = sum(int(bucket.quota) for bucket in buckets)
    selection = taste_profile.country_selection
    return {
        "profile": taste_profile.as_repository_dict(), "target": target, "bucket_count": len(buckets),
        "quotas": {
            "media_type": quota_by("media_type"), "release": quota_by("era"),
            "vibe": quota_by("vibe"), "country": quota_by("target_country"),
            "origin": quota_by("origin"), "original_language": quota_by("original_language"),
        },
        "weights": {
            "media_type": media_weights(taste_profile.media_preference), "release": release_weights(taste_profile.release_preference),
            "vibe": vibe_weights(taste_profile.vibe_preference), "origin": origin_weights(taste_profile.origin_preference, ui_language=taste_profile.ui_language),
            "country": selection.country_weights if isinstance(selection, CountrySelection) else {},
        },
        "country_selection": selection.as_repository_dict() if isinstance(selection, CountrySelection) else {},
        "country_plan": build_country_plan(selection, target) if isinstance(selection, CountrySelection) else {},
    }

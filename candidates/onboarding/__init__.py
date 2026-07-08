"""Deterministic onboarding candidate-pool autofill."""

from candidates.onboarding.autofill import (
    MAX_TMDB_REQUESTS,
    STARTER_POOL_MIN_ACCEPTABLE,
    STARTER_POOL_TARGET,
    AutofillResult,
    CandidateFetchBucket,
    OnboardingTasteProfile,
    TmdbAutofillClient,
    allocate_integer_quotas,
    build_fetch_buckets,
    media_weights,
    origin_weights,
    release_weights,
    run_onboarding_autofill,
    should_start_onboarding_autofill,
    vibe_weights,
)

__all__ = [
    "MAX_TMDB_REQUESTS",
    "STARTER_POOL_MIN_ACCEPTABLE",
    "STARTER_POOL_TARGET",
    "AutofillResult",
    "CandidateFetchBucket",
    "OnboardingTasteProfile",
    "TmdbAutofillClient",
    "allocate_integer_quotas",
    "build_fetch_buckets",
    "media_weights",
    "origin_weights",
    "release_weights",
    "run_onboarding_autofill",
    "should_start_onboarding_autofill",
    "vibe_weights",
]

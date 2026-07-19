"""Deterministic safety gates for recommendation eligibility."""

from candidates.safety.explicit_content import (
    ExplicitContentDecision,
    evaluate_explicit_sexual_content,
    is_blocked_explicit_sexual_content,
)

__all__ = (
    "ExplicitContentDecision",
    "evaluate_explicit_sexual_content",
    "is_blocked_explicit_sexual_content",
)

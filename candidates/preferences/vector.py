"""Local recommendation-vector contract and algorithm parameter resolvers."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


MOODS = frozenset({"any", "light", "dynamic", "drama", "dark"})
EXPLORATION_RATIOS = (0.0, 0.1, 0.2, 0.3, 0.4)
RARITY_WEIGHTS = (
    (0.75, 0.0, 0.25),
    (0.88, 0.0, 0.12),
    (1.0, 0.0, 0.0),
    (0.75, 0.25, 0.0),
    (0.55, 0.45, 0.0),
)
DIVERSITY_WINDOWS = (1, 4, 12, 18, 24)


def normalize_vector_level(value: Any, default: int = 2) -> int:
    try:
        level = int(value)
    except (TypeError, ValueError):
        return default
    return level if 0 <= level <= 4 else default


def resolve_exploration_ratio(level: Any) -> float:
    return EXPLORATION_RATIOS[normalize_vector_level(level)]


def resolve_rarity_weights(level: Any) -> tuple[float, float, float]:
    """Return base, hidden-gem and popularity weights."""
    return RARITY_WEIGHTS[normalize_vector_level(level)]


def resolve_diversity_window(level: Any) -> int:
    return DIVERSITY_WINDOWS[normalize_vector_level(level)]


@dataclass(frozen=True)
class RecommendationVector:
    openness_level: int = 2
    rarity_level: int = 2
    diversity_level: int = 2
    mood: str = "any"

    def normalized(self) -> "RecommendationVector":
        mood = str(self.mood or "").strip().casefold()
        return RecommendationVector(
            openness_level=normalize_vector_level(self.openness_level),
            rarity_level=normalize_vector_level(self.rarity_level),
            diversity_level=normalize_vector_level(self.diversity_level),
            mood=mood if mood in MOODS else "any",
        )

    def to_dict(self) -> dict[str, int | str]:
        return asdict(self.normalized())

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "RecommendationVector":
        source = dict(payload or {})
        allowed = cls.__dataclass_fields__
        return cls(**{key: value for key, value in source.items() if key in allowed}).normalized()

"""Deterministic gate for explicit sexual content in safe recommendation eligibility.

Classifies degree of explicitness, not relationship themes (romance, same-sex, etc.).
Strong structural signals block alone; weak text signals require accumulation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# Reason codes (diagnostic; not shown in product UI).
REASON_ADULT_FLAG = "adult_flag"
REASON_EXPLICIT_CONTENT_RATING = "explicit_content_rating"
REASON_EXPLICIT_KEYWORD = "explicit_keyword"
REASON_EXPLICIT_PHRASE = "explicit_phrase"
REASON_WEAK_ACCUMULATION = "explicit_weak_accumulation"

# Structural keyword names as stored from TMDb (case-insensitive match).
_EXPLICIT_KEYWORDS = frozenset({
    "hentai",
    "softcore",
    "hardcore",
    "pornography",
    "pornographic",
    "porn",
    "xxx",
    "animated porn",
    "adult video",
    "erotica",
    "erotic",
    "sexploitation",
})

# Content ratings that mean explicit adult sexual content (narrow; not TV-MA alone).
_EXPLICIT_CONTENT_RATINGS = frozenset({
    "nc-17",
    "nc17",
    "x",
    "xxx",
    "r18+",
    "r18",
    "r-18",
    "r-18+",
    "18+",
    "rx",
    "ao",
    "adults only",
})

# Multi-token / high-precision phrases (EN + RU). Not single ambiguous words.
_STRONG_PHRASES = (
    "explicit sex",
    "graphic sex",
    "animated porn",
    "uncensored sex",
    "full sexual intercourse",
    "hardcore sex",
    "pornographic anime",
    "hentai anime",
    "явный секс",
    "графический секс",
    "порнографическ",
    "хентай",
    "эротический аниме-фильм",
)

# Weak signals: alone never enough; need WEAK_SIGNAL_THRESHOLD independent hits.
_WEAK_OVERVIEW_TERMS = frozenset({
    "hentai",
    "хентай",
    "porn",
    "порно",
    "softcore",
    "hardcore",
    "xxx",
    "erotica",
    "эротика",
})

_WEAK_KEYWORDS = frozenset({
    "ecchi",
    "nudity",
    "sexual content",
    "adult humor",
})

WEAK_SIGNAL_THRESHOLD = 2

# Never count these alone (false-positive traps from QA brief).
_AMBIGUOUS_NEVER_ALONE = frozenset({
    "ванна",
    "тело",
    "постель",
    "обнажил",
    "bath",
    "bathtub",
    "body",
    "bed",
    "romance",
    "animation",
    "anime",
})


@dataclass(frozen=True)
class ExplicitContentDecision:
    """Result of the explicit-sexual-content safety evaluation."""

    blocked: bool
    reason_code: str | None = None
    signals: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "blocked": self.blocked,
            "reason_code": self.reason_code,
            "signals": list(self.signals),
        }


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _casefold(value: Any) -> str:
    return _clean(value).casefold()


def _truthy_adult(value: Any) -> bool:
    if value is True:
        return True
    if value in (False, None, ""):
        return False
    if isinstance(value, (int, float)) and value == 1:
        return True
    text = _casefold(value)
    return text in {"true", "1", "yes", "adult"}


def _keyword_names(candidate: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for item in candidate.get("keywords") or []:
        if isinstance(item, dict):
            name = _casefold(item.get("name") or item.get("keyword"))
        else:
            name = _casefold(item)
        if name and name not in names:
            names.append(name)
    return names


def _genre_tokens(candidate: dict[str, Any]) -> list[str]:
    tokens: list[str] = []
    for field in ("genre_keys", "genres", "genres_tmdb", "genre_names"):
        for item in candidate.get(field) or []:
            if isinstance(item, (list, tuple)) and item:
                text = _casefold(item[0])
            else:
                text = _casefold(item)
            if text and text not in tokens:
                tokens.append(text)
    return tokens


def _content_rating_token(candidate: dict[str, Any]) -> str:
    raw = _casefold(candidate.get("content_rating"))
    if not raw:
        return ""
    # TMDb sometimes returns "US: NC-17" / "JP: R18+".
    if ":" in raw:
        raw = raw.split(":", 1)[-1].strip()
    return raw.replace(" ", "")


def _text_corpus(candidate: dict[str, Any]) -> str:
    parts: list[str] = []
    for field in (
        "overview",
        "description",
        "title",
        "original_title",
        "alternative_title",
        "name",
        "original_name",
    ):
        text = _clean(candidate.get(field))
        if text:
            parts.append(text)
    localized = candidate.get("localized")
    if isinstance(localized, dict):
        for block in localized.values():
            if not isinstance(block, dict):
                continue
            for field in ("overview", "description", "title", "name"):
                text = _clean(block.get(field))
                if text:
                    parts.append(text)
    return "\n".join(parts)


def _find_strong_phrase(corpus: str) -> str | None:
    lowered = corpus.casefold()
    for phrase in _STRONG_PHRASES:
        if phrase.casefold() in lowered:
            return phrase
    return None


def evaluate_explicit_sexual_content(candidate: dict[str, Any] | None) -> ExplicitContentDecision:
    """Return whether a candidate must be excluded from safe recommendation eligibility."""
    if not isinstance(candidate, dict):
        return ExplicitContentDecision(blocked=False)

    signals: list[str] = []

    if _truthy_adult(candidate.get("adult")) or _truthy_adult(candidate.get("imdb_is_adult")):
        signals.append("adult=true")
        return ExplicitContentDecision(
            blocked=True,
            reason_code=REASON_ADULT_FLAG,
            signals=tuple(signals),
        )

    rating = _content_rating_token(candidate)
    if rating and (
        rating in _EXPLICIT_CONTENT_RATINGS
        or any(rating.startswith(prefix) for prefix in ("nc-17", "r18", "rx", "xxx"))
    ):
        signals.append(f"content_rating={rating}")
        return ExplicitContentDecision(
            blocked=True,
            reason_code=REASON_EXPLICIT_CONTENT_RATING,
            signals=tuple(signals),
        )

    keywords = _keyword_names(candidate)
    for name in keywords:
        if name in _EXPLICIT_KEYWORDS:
            signals.append(f"keyword:{name}")
            return ExplicitContentDecision(
                blocked=True,
                reason_code=REASON_EXPLICIT_KEYWORD,
                signals=tuple(signals),
            )

    # Genre labels that are themselves explicit adult categories (rare; structural).
    for genre in _genre_tokens(candidate):
        if genre in _EXPLICIT_KEYWORDS or genre in {"hentai"}:
            signals.append(f"genre:{genre}")
            return ExplicitContentDecision(
                blocked=True,
                reason_code=REASON_EXPLICIT_KEYWORD,
                signals=tuple(signals),
            )

    corpus = _text_corpus(candidate)
    strong = _find_strong_phrase(corpus)
    if strong is not None:
        signals.append(f"phrase:{strong}")
        return ExplicitContentDecision(
            blocked=True,
            reason_code=REASON_EXPLICIT_PHRASE,
            signals=tuple(signals),
        )

    weak_hits: list[str] = []
    corpus_cf = corpus.casefold()
    for term in _WEAK_OVERVIEW_TERMS:
        # Whole-word-ish: avoid matching inside unrelated tokens when possible.
        if term in corpus_cf:
            # Skip if the only hit is an ambiguous never-alone token (defensive).
            if term in _AMBIGUOUS_NEVER_ALONE:
                continue
            weak_hits.append(f"text:{term}")
    for name in keywords:
        if name in _WEAK_KEYWORDS:
            weak_hits.append(f"weak_keyword:{name}")

    # Deduplicate while preserving order.
    seen: set[str] = set()
    unique_weak: list[str] = []
    for item in weak_hits:
        if item in seen:
            continue
        seen.add(item)
        unique_weak.append(item)

    if len(unique_weak) >= WEAK_SIGNAL_THRESHOLD:
        signals.extend(unique_weak)
        return ExplicitContentDecision(
            blocked=True,
            reason_code=REASON_WEAK_ACCUMULATION,
            signals=tuple(signals),
        )

    return ExplicitContentDecision(blocked=False, signals=tuple(unique_weak))


def is_blocked_explicit_sexual_content(candidate: dict[str, Any] | None) -> bool:
    """Convenience boolean for eligibility / replenish hard-drops."""
    return evaluate_explicit_sexual_content(candidate).blocked

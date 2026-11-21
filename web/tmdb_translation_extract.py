"""Offline selection of a provider-tagged overview; no dispatch or export."""
from dataclasses import dataclass
from hashlib import sha256
import json
import re

from web.tmdb_ids import QueueItem


MAX_BODY_BYTES = 2 * 1024 * 1024
MAX_TRANSLATIONS = 1000
MAX_OVERVIEW_CHARS = 8192
_LANGUAGE = re.compile(r"[a-z]{2}", flags=re.ASCII)
_REGION = re.compile(r"[A-Z]{2}", flags=re.ASCII)


@dataclass(frozen=True)
class TypedFixture:
    """Caller-provided typed endpoint context, not proof of provider origin."""

    item: QueueItem
    body: bytes


@dataclass(frozen=True)
class TaggedOverview:
    item: QueueItem
    locale_tag: str
    choice: str
    overview: str
    sha256: str
    equals_untagged_detail: bool


def _decode(fixture: TypedFixture) -> dict:
    if not isinstance(fixture.body, bytes) or not 0 < len(fixture.body) <= MAX_BODY_BYTES:
        raise ValueError("Fixture exceeds the byte limit or is empty")

    def unique_object(members):
        obj = dict(members)
        if len(obj) != len(members):
            raise ValueError
        return obj

    try:
        body = json.loads(fixture.body.decode("utf-8"), object_pairs_hook=unique_object)
    except (ValueError, RecursionError):
        raise ValueError("Invalid JSON fixture") from None
    if not isinstance(body, dict):
        raise ValueError("Invalid JSON fixture")
    return body


def _identity(body, item, *, optional_id=False):
    identifier = body.get("id")
    if (not (optional_id and "id" not in body)
            and (type(identifier) is not int or identifier != item.tmdb_id)):
        raise ValueError("Fixture typed ID mismatch")
    if body.get("media_type", item.media_type) != item.media_type:
        raise ValueError("Fixture typed ID mismatch")


def _text(value):
    if value is None:
        return ""
    if not isinstance(value, str) or len(value) > MAX_OVERVIEW_CHARS or "\0" in value:
        raise ValueError("Invalid or oversized overview")
    try:
        value.encode("utf-8")
    except UnicodeError:
        raise ValueError("Invalid overview encoding") from None
    return value.strip()


def select_translation(
    details: TypedFixture, translations: TypedFixture | None = None,
) -> TaggedOverview | None:
    """Compare a typed Details body with appended or standalone translations.

    Russian (RU region first), then a tag matching original_language, then
    English (US region first). Within a nonpreferred region order lexically.
    Never infer language from the untagged Details overview or the request.
    """
    item = details.item
    if (not isinstance(item, QueueItem) or item.media_type not in ("movie", "tv")
            or type(item.tmdb_id) is not int or not 0 < item.tmdb_id < 2**31
            or (translations is not None and translations.item != item)):
        raise ValueError("Fixture typed ID mismatch")
    root = _decode(details)
    _identity(root, item)
    detail_text = _text(root.get("overview"))
    original = root.get("original_language")
    if not isinstance(original, str) or not _LANGUAGE.fullmatch(original):
        original = None
    if translations is None:
        section = root.get("translations")
        if section is None:
            return None
    else:
        if "translations" in root:
            raise ValueError("Use appended or standalone translations, not both")
        section = _decode(translations)
    if not isinstance(section, dict):
        raise ValueError("Invalid translations section")
    _identity(section, item, optional_id=translations is None)
    rows = section.get("translations")
    if not isinstance(rows, list) or len(rows) > MAX_TRANSLATIONS:
        raise ValueError("Invalid or oversized translations list")

    tagged = {}
    preferred = ["ru"]
    if original not in (None, "ru", "en"):
        preferred.append(original)
    preferred.append("en")
    for record in rows:
        if not isinstance(record, dict) or not isinstance(record.get("data"), dict):
            raise ValueError("Invalid translation record")
        lang, region = record.get("iso_639_1"), record.get("iso_3166_1")
        if (not isinstance(lang, str) or not _LANGUAGE.fullmatch(lang)
                or not isinstance(region, str) or not _REGION.fullmatch(region)):
            raise ValueError("Invalid translation locale tag")
        overview = _text(record["data"].get("overview"))
        if not overview or lang not in preferred:
            continue
        key = (lang, region)
        if key in tagged and tagged[key] != overview:
            raise ValueError("Conflicting overviews for one translation locale")
        tagged[key] = overview

    for lang in preferred:
        variants = [region for candidate, region in tagged if candidate == lang]
        if variants:
            default_region = {"ru": "RU", "en": "US"}.get(lang)
            region = default_region if default_region in variants else min(variants)
            text = tagged[(lang, region)]
            choice = "russian" if lang == "ru" else "original" if lang == original else "english"
            return TaggedOverview(item, f"{lang}-{region}", choice, text,
                                  sha256(text.encode("utf-8")).hexdigest(), text == detail_text)
    return None

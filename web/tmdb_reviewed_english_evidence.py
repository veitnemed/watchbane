"""Private-QA-only proof of an English synopsis in one reviewed Details response."""
from dataclasses import dataclass
from hashlib import sha256
import json
import re

from candidates.safety.explicit_content import is_blocked_explicit_sexual_content
from web.tmdb_change_windows import _reject_payload_constant, _unique_payload_object
from web.tmdb_ids import QueueItem
from web.tmdb_translation_extract import MAX_BODY_BYTES, TypedFixture, select_translation


_SHA256 = re.compile(r"[a-f0-9]{64}", re.ASCII)
_LANGUAGE = re.compile(r"[a-z]{2}", re.ASCII)
_ORIGIN = "https://api.themoviedb.org"


@dataclass(frozen=True)
class ReviewedAppendedDetail:
    """Trusted operator's typed HTTP receipt bound to separately held raw bytes.

    This is not an attestation signed by TMDb. The current detached transport
    does not emit raw response receipts. That (or independently reviewed
    custody) would be needed before making a provenance claim about live data.
    Standalone Translation responses are deliberately unsupported: their
    numeric ID alone cannot bind them to the movie or series route.
    """

    item: QueueItem
    response_url: str
    status: int
    response_sha256: str
    synopsis_locale: str
    synopsis_sha256: str
    intended_use: str


@dataclass(frozen=True)
class PrivateEnglishSynopsis:
    item: QueueItem
    overview: str
    synopsis_locale: str
    synopsis_sha256: str
    original_language: str
    evidence_sha256: str


def verify_private_english_synopsis(
    *, review: ReviewedAppendedDetail, evidence: bytes, use_cleared: bool = False,
) -> PrivateEnglishSynopsis:
    """Verify pinned, typed Details + appended Translations without I/O.

    We admit only the exact selected en-US translation. A Russian record or
    higher-priority original translation wins selection and cannot be demoted
    just because an English record also exists. The request locale and the
    untagged Details overview do not assign a language. Never export a title
    whose language is not independently evidenced. This pure result grants
    no new use, packaging, publication or activation permission.
    """
    if use_cleared is not True or not isinstance(review, ReviewedAppendedDetail) or review.intended_use != "private_qa":
        raise PermissionError("Exact reviewed private QA clearance is required")
    item = review.item
    if (not isinstance(item, QueueItem) or item.media_type not in ("movie", "tv")
            or type(item.tmdb_id) is not int or not 0 < item.tmdb_id < 2**31):
        raise ValueError("Expected an exact typed Details receipt")
    expected_url = (f"{_ORIGIN}/3/{item.media_type}/{item.tmdb_id}"
                    "?language=ru-RU&append_to_response=translations")
    if (review.response_url != expected_url or type(review.status) is not int or review.status != 200
            or review.synopsis_locale != "en-US"
            or type(review.response_sha256) is not str or _SHA256.fullmatch(review.response_sha256) is None
            or type(review.synopsis_sha256) is not str or _SHA256.fullmatch(review.synopsis_sha256) is None
            or type(evidence) is not bytes or not 0 < len(evidence) <= MAX_BODY_BYTES
            or sha256(evidence).hexdigest() != review.response_sha256):
        raise ValueError("Receipt does not match the exact typed, pinned Details evidence")
    try:
        body = json.loads(evidence.decode("utf-8"), object_pairs_hook=_unique_payload_object,
                          parse_constant=_reject_payload_constant)
        detail_title, other_title = ("title", "name") if item.media_type == "movie" else ("name", "title")
        if (type(body) is not dict or type(body.get("id")) is not int or body["id"] != item.tmdb_id
                or body.get("media_type", item.media_type) != item.media_type
                or body.get("adult") is not False or ("success" in body and body["success"] is not True)
                or type(body.get(detail_title)) is not str or not body[detail_title].strip()
                or len(body[detail_title]) > 512 or "\0" in body[detail_title] or other_title in body):
            raise ValueError
        body[detail_title].encode("utf-8")
        original = body.get("original_language")
        if type(original) is not str or _LANGUAGE.fullmatch(original) is None:
            raise ValueError
    except (ValueError, RecursionError):
        raise ValueError("Evidence lacks exact typed Details with explicit adult:false and original language") from None
    selected = select_translation(TypedFixture(item, evidence))
    if selected is None or selected.locale_tag != review.synopsis_locale or selected.sha256 != review.synopsis_sha256:
        raise ValueError("No exact reviewed en-US fallback was selected from the appended translations")
    if is_blocked_explicit_sexual_content({"overview": selected.overview}):
        raise ValueError("Reviewed synopsis did not pass the existing text safety gate")
    return PrivateEnglishSynopsis(item, selected.overview, selected.locale_tag, selected.sha256,
                                  original, review.response_sha256)

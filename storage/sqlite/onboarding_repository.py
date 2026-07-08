"""SQLite repository for onboarding candidate-autofill profiles and audit rows."""

from __future__ import annotations

from pathlib import Path
import sqlite3
from typing import Any

from storage.sqlite.json_codec import dumps_json, loads_json
from storage.sqlite.session import connection, transaction, utc_now


def create_onboarding_profile(
    profile: dict[str, Any],
    *,
    conn: sqlite3.Connection | None = None,
    path: str | Path | None = None,
) -> int:
    """Persist the profile before candidate autofill starts."""
    active, owned = connection(conn, path)
    try:
        with transaction(active, owned):
            row = active.execute(
                """
                INSERT INTO onboarding_profiles(
                  ui_language, media_preference, release_preference,
                  vibe_preference, origin_preference, created_at, completed_at
                )
                VALUES (?, ?, ?, ?, ?, ?, NULL)
                """,
                (
                    str(profile.get("ui_language") or "").strip() or "ru",
                    str(profile.get("media_preference") or "").strip() or "both",
                    str(profile.get("release_preference") or "").strip() or "mixed",
                    str(profile.get("vibe_preference") or "").strip() or "mixed",
                    profile.get("origin_preference"),
                    utc_now(),
                ),
            )
            return int(row.lastrowid)
    finally:
        if owned:
            active.close()


def complete_onboarding_profile(
    profile_id: int,
    *,
    conn: sqlite3.Connection | None = None,
    path: str | Path | None = None,
) -> None:
    active, owned = connection(conn, path)
    try:
        with transaction(active, owned):
            active.execute(
                "UPDATE onboarding_profiles SET completed_at = ? WHERE id = ?",
                (utc_now(), int(profile_id)),
            )
    finally:
        if owned:
            active.close()


def has_completed_onboarding_profile(
    *,
    conn: sqlite3.Connection | None = None,
    path: str | Path | None = None,
) -> bool:
    active, owned = connection(conn, path)
    try:
        row = active.execute(
            "SELECT 1 FROM onboarding_profiles WHERE completed_at IS NOT NULL LIMIT 1"
        ).fetchone()
        return row is not None
    finally:
        if owned:
            active.close()


def save_autofill_request_audit(
    audit: dict[str, Any],
    *,
    conn: sqlite3.Connection | None = None,
    path: str | Path | None = None,
) -> int:
    active, owned = connection(conn, path)
    try:
        with transaction(active, owned):
            row = active.execute(
                """
                INSERT INTO candidate_autofill_requests(
                  onboarding_profile_id, bucket_id, endpoint, params_json,
                  page, status, accepted_count, rejected_count, error_text, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(audit["onboarding_profile_id"]),
                    str(audit.get("bucket_id") or ""),
                    str(audit.get("endpoint") or ""),
                    dumps_json(audit.get("params") or {}),
                    int(audit.get("page") or 1),
                    str(audit.get("status") or "ok"),
                    int(audit.get("accepted_count") or 0),
                    int(audit.get("rejected_count") or 0),
                    audit.get("error_text"),
                    audit.get("created_at") or utc_now(),
                ),
            )
            return int(row.lastrowid)
    finally:
        if owned:
            active.close()


def load_autofill_request_audits(
    profile_id: int,
    *,
    conn: sqlite3.Connection | None = None,
    path: str | Path | None = None,
) -> list[dict[str, Any]]:
    active, owned = connection(conn, path)
    try:
        rows = active.execute(
            """
            SELECT *
            FROM candidate_autofill_requests
            WHERE onboarding_profile_id = ?
            ORDER BY id
            """,
            (int(profile_id),),
        ).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            result.append(
                {
                    "id": row["id"],
                    "onboarding_profile_id": row["onboarding_profile_id"],
                    "bucket_id": row["bucket_id"],
                    "endpoint": row["endpoint"],
                    "params": loads_json(row["params_json"], {}),
                    "page": row["page"],
                    "status": row["status"],
                    "accepted_count": row["accepted_count"],
                    "rejected_count": row["rejected_count"],
                    "error_text": row["error_text"],
                    "created_at": row["created_at"],
                }
            )
        return result
    finally:
        if owned:
            active.close()

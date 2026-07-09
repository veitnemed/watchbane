"""SQLite FTS5 index for candidate pool text search."""

from __future__ import annotations

import re
import sqlite3
from time import perf_counter

from candidates.models.keys import pool_entry_key
from candidates.search.document import build_search_document
from storage.sqlite.json_codec import loads_json

_FTS_TOKEN_RE = re.compile(r"[^\w\u0400-\u04ff]+", re.UNICODE)


def _candidate_pool_key(candidate: dict, explicit_key: str | None = None) -> str:
    if explicit_key:
        return explicit_key
    stored = candidate.get("pool_entry_key")
    if stored not in (None, ""):
        return str(stored)
    return pool_entry_key(candidate)


def rebuild_fts_index(conn: sqlite3.Connection, *, data_language: str = "ru") -> int:
    """Full rebuild of candidate_fts from candidate_records."""
    conn.execute("DELETE FROM candidate_fts")
    rows = conn.execute("SELECT pool_key, payload_json FROM candidate_records ORDER BY rowid").fetchall()
    payload_rows: list[tuple[str, str]] = []
    for row in rows:
        candidate = loads_json(row["payload_json"], {})
        if not isinstance(candidate, dict):
            continue
        document = build_search_document(candidate, data_language=data_language)
        payload_rows.append((str(row["pool_key"]), document))
    if payload_rows:
        conn.executemany(
            "INSERT INTO candidate_fts(pool_key, document) VALUES (?, ?)",
            payload_rows,
        )
    return len(payload_rows)


def upsert_fts_rows(
    conn: sqlite3.Connection,
    rows: list[tuple[str, dict]],
    *,
    data_language: str = "ru",
) -> int:
    """Point update for explicit (pool_key, candidate) rows."""
    if not rows:
        return 0
    keys = [pool_key for pool_key, _ in rows]
    placeholders = ",".join("?" for _ in keys)
    conn.execute(f"DELETE FROM candidate_fts WHERE pool_key IN ({placeholders})", keys)
    payload_rows = [
        (
            pool_key,
            build_search_document(candidate, data_language=data_language),
        )
        for pool_key, candidate in rows
        if isinstance(candidate, dict)
    ]
    if payload_rows:
        conn.executemany(
            "INSERT INTO candidate_fts(pool_key, document) VALUES (?, ?)",
            payload_rows,
        )
    return len(payload_rows)


def _normalize_fts_tokens(query: str) -> list[str]:
    normalized = str(query or "").strip().casefold()
    if normalized == "":
        return []
    tokens = [token for token in _FTS_TOKEN_RE.split(normalized) if token]
    seen: set[str] = set()
    unique: list[str] = []
    for token in tokens:
        if token in seen:
            continue
        seen.add(token)
        unique.append(token)
    return unique


def _escape_fts_token(token: str) -> str:
    escaped = token.replace('"', '""')
    if len(token) >= 2:
        return f'"{escaped}"*'
    return f'"{escaped}"'


def build_fts_match_query(query: str, *, typo_fallback: bool = False) -> str:
    """Build FTS5 MATCH expression (AND across tokens, OR within single-token alias group)."""
    from candidates.search.query_expand import expand_query_token_groups, expand_query_typo_groups

    groups = expand_query_typo_groups(query) if typo_fallback else expand_query_token_groups(query)
    if not groups:
        return ""
    if len(groups) == 1:
        escaped = [_escape_fts_token(token) for token in groups[0]]
        if len(escaped) == 1:
            return escaped[0]
        return " OR ".join(escaped)
    # Multi-token: AND primary token per group. Parenthesized OR + AND breaks on SQLite FTS5.
    return " ".join(_escape_fts_token(group[0]) for group in groups if group)


def _search_fts_match(conn: sqlite3.Connection, match_query: str, *, limit: int) -> list[tuple[str, float]]:
    safe_limit = max(1, int(limit))
    rows = conn.execute(
        """
        SELECT pool_key, bm25(candidate_fts) AS score
        FROM candidate_fts
        WHERE candidate_fts MATCH ?
        ORDER BY score ASC
        LIMIT ?
        """,
        (match_query, safe_limit),
    ).fetchall()
    return [(str(row["pool_key"]), float(row["score"])) for row in rows]


def search_fts(
    conn: sqlite3.Connection,
    query: str,
    *,
    limit: int = 200,
) -> list[tuple[str, float]]:
    """Return (pool_key, bm25_score) pairs; lower bm25 is better in SQLite FTS5."""
    for typo_fallback in (False, True):
        match_query = build_fts_match_query(query, typo_fallback=typo_fallback)
        if match_query == "":
            return []
        try:
            hits = _search_fts_match(conn, match_query, limit=limit)
        except sqlite3.OperationalError:
            continue
        if hits:
            return hits
    return []


def rebuild_fts_index_timed(conn: sqlite3.Connection, *, data_language: str = "ru") -> dict:
    """Rebuild helper for diagnostics scripts."""
    started = perf_counter()
    count = rebuild_fts_index(conn, data_language=data_language)
    elapsed_ms = round((perf_counter() - started) * 1000, 2)
    return {"count": count, "elapsed_ms": elapsed_ms}

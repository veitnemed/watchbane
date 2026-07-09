"""Tests for the local search query JSONL log."""

from __future__ import annotations

import json

import candidates.search.query_log as query_log


def _read_jsonl(path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _candidates() -> list[dict]:
    return [
        {"tmdb_id": 101, "title": "Первый", "final_score": 0.91},
        {"tmdb_id": 102, "title": "Второй", "final_score": 0.72},
        {"tmdb_id": 103, "title": "Третий", "final_score": 0.5},
    ]


def _build_entry(**overrides):
    base = dict(
        search_id="abc123",
        query="крими",
        filters={"country": ["RU"], "media_type": "tv"},
        sort_mode="final_score",
        result_count=3,
        top_candidates=_candidates(),
        latency_ms=12.3,
    )
    base.update(overrides)
    return query_log.build_search_query_entry(**base)


def test_search_query_log_disabled_by_default(tmp_path, monkeypatch) -> None:
    log_path = tmp_path / "reports" / "search_query_log.jsonl"
    monkeypatch.setattr(query_log, "DEFAULT_LOG_PATH", log_path)
    monkeypatch.delenv(query_log.SEARCH_QUERY_LOG_ENV, raising=False)

    warning = query_log.append_search_query_log(_build_entry())

    assert warning is None
    assert log_path.exists() is False


def test_search_query_log_enabled_writes_one_row(tmp_path, monkeypatch) -> None:
    log_path = tmp_path / "reports" / "search_query_log.jsonl"
    monkeypatch.setattr(query_log, "DEFAULT_LOG_PATH", log_path)
    monkeypatch.setenv(query_log.SEARCH_QUERY_LOG_ENV, "1")

    warning = query_log.append_search_query_log(_build_entry())

    assert warning is None
    lines = _read_jsonl(log_path)
    assert len(lines) == 1
    entry = lines[0]
    assert entry["event"] == "search"
    assert entry["query"] == "крими"
    assert entry["normalized_query"] == "крими"
    assert entry["result_count"] == 3
    assert entry["zero_result"] is False
    assert entry["latency_ms"] == 12.3
    assert entry["sort_mode"] == "final_score"


def test_top_results_contain_rank_title_id_score(tmp_path, monkeypatch) -> None:
    log_path = tmp_path / "reports" / "search_query_log.jsonl"
    monkeypatch.setattr(query_log, "DEFAULT_LOG_PATH", log_path)
    monkeypatch.setenv(query_log.SEARCH_QUERY_LOG_ENV, "1")

    query_log.append_search_query_log(_build_entry())

    top = _read_jsonl(log_path)[0]["top_results"]
    assert len(top) == 3
    assert top[0] == {"rank": 1, "tmdb_id": 101, "title": "Первый", "final_score": 0.91}
    assert [row["rank"] for row in top] == [1, 2, 3]


def test_top_results_capped_at_twenty(tmp_path, monkeypatch) -> None:
    log_path = tmp_path / "reports" / "search_query_log.jsonl"
    monkeypatch.setattr(query_log, "DEFAULT_LOG_PATH", log_path)
    monkeypatch.setenv(query_log.SEARCH_QUERY_LOG_ENV, "1")

    many = [{"tmdb_id": i, "title": f"T{i}", "final_score": 1.0} for i in range(50)]
    query_log.append_search_query_log(_build_entry(top_candidates=many, result_count=50))

    top = _read_jsonl(log_path)[0]["top_results"]
    assert len(top) == 20


def test_tokens_and_absolute_paths_are_redacted(tmp_path, monkeypatch) -> None:
    log_path = tmp_path / "reports" / "search_query_log.jsonl"
    monkeypatch.setattr(query_log, "DEFAULT_LOG_PATH", log_path)
    monkeypatch.setenv(query_log.SEARCH_QUERY_LOG_ENV, "1")

    entry = _build_entry(
        query="token=secret-token D:\\runtime\\watchbane.sqlite3",
        filters={"api_key": "secret-token", "note": "path D:\\runtime\\watchbane.sqlite3"},
    )
    query_log.append_search_query_log(entry)

    raw = log_path.read_text(encoding="utf-8")
    assert "secret-token" not in raw
    assert "api_key" not in raw
    assert "D:\\runtime" not in raw


def test_zero_result_query_is_flagged(tmp_path, monkeypatch) -> None:
    log_path = tmp_path / "reports" / "search_query_log.jsonl"
    monkeypatch.setattr(query_log, "DEFAULT_LOG_PATH", log_path)
    monkeypatch.setenv(query_log.SEARCH_QUERY_LOG_ENV, "1")

    query_log.append_search_query_log(_build_entry(top_candidates=[], result_count=0))

    entry = _read_jsonl(log_path)[0]
    assert entry["result_count"] == 0
    assert entry["zero_result"] is True
    assert entry["top_results"] == []


def test_write_failure_returns_warning_without_raising(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv(query_log.SEARCH_QUERY_LOG_ENV, "1")

    def _boom(*_args, **_kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(query_log.Path, "mkdir", _boom)

    warning = query_log.append_search_query_log(_build_entry(), path=tmp_path / "x.jsonl")

    assert warning is not None
    assert "Search query log write failed" in warning


def test_action_entry_carries_search_id_rank_and_action(tmp_path, monkeypatch) -> None:
    log_path = tmp_path / "reports" / "search_query_log.jsonl"
    monkeypatch.setattr(query_log, "DEFAULT_LOG_PATH", log_path)
    monkeypatch.setenv(query_log.SEARCH_QUERY_LOG_ENV, "1")

    entry = query_log.build_search_action_entry(
        search_id="abc123",
        action="open",
        tmdb_id=101,
        rank=1,
        query="крими",
    )
    query_log.append_search_query_log(entry)

    stored = _read_jsonl(log_path)[0]
    assert stored["event"] == "action"
    assert stored["action"] == "open"
    assert stored["search_id"] == "abc123"
    assert stored["rank"] == 1
    assert stored["tmdb_id"] == 101


def test_signature_dedup_key_matches_finalized_result() -> None:
    entry = _build_entry()
    same = _build_entry()
    different = _build_entry(result_count=2)
    assert query_log.build_search_signature(entry) == query_log.build_search_signature(same)
    assert query_log.build_search_signature(entry) != query_log.build_search_signature(different)

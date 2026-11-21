"""Opt-in server retrieval reuses semantic rules without a second lexical index."""
import json

import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient

from candidates import story_semantic
from web import story_api


class ControlledEncoder:
    variant = "fixture"

    def __init__(self, _path):
        pass

    def encode(self, texts, prefix="passage: ", **_kwargs):
        result = np.zeros((len(texts), 384), dtype=np.float32)
        for i, text in enumerate(texts):
            t = text.casefold()
            result[i, 0] = 2 if "побег" in t else 1
            result[i, 1] = 2 if "врач" in t else 0
        return result


def test_prepared_http_matches_default_and_skips_old_lexical_build(tmp_path, monkeypatch):
    catalog = tmp_path / "catalog.jsonl"
    rows = [
        ("tv", 18, 2000, "Врач планирует побег. Он ждёт помощника."),
        ("movie", 18, 2000, "Врач планирует побег. Он ждёт помощника."),
        ("movie", 19, 2001, "Следователь скрывает преступление."),
        ("tv", 22, 2001, "Побег из тюрьмы. Герой ищет проводника."),
    ]
    catalog.write_text("".join(json.dumps({
        "media_type": kind, "tmdb_id": tmdb_id, "year": year, "title": f"Fixture {kind} {tmdb_id}",
        "overview": overview, "language": "ru-RU",
    }) + "\n" for kind, tmdb_id, year, overview in rows), encoding="utf-8")
    monkeypatch.setattr(story_api, "LocalE5", ControlledEncoder)
    baseline_app = story_api.create_app(catalog, tmp_path)
    new_app = story_api.create_app(catalog, tmp_path, prepared_index=True)
    dev_queries = ("врач планирует побег", "сериал 2000 про побег", "фильм 1901 про врача",
                   "следователь скрывает преступление", "без убийств", "как мне обновить драйвер на ноутбуке")

    def fail_legacy_index(*_args):
        pytest.fail("prepared mode must not also build the old lexical index")
    with TestClient(baseline_app) as baseline:
        assert baseline_app.state.engine.lexical is not None
        expect = [baseline.post("/v1/search", json={"query": query}).json() for query in dev_queries]
        monkeypatch.setattr(story_semantic, "LexicalIndex", fail_legacy_index)
        with TestClient(new_app) as prepared:
            assert new_app.state.engine.lexical is None
            actual = [prepared.post("/v1/search", json={"query": query}).json() for query in dev_queries]
            for options in ({"hybrid": False}, {"rerank": True}, {"role_adjustment": True},
                            {"excluded": {"tmdb:movie:18"}}):
                assert new_app.state.engine.search(dev_queries[0], **options) == baseline_app.state.engine.search(
                    dev_queries[0], **options)
    assert actual == expect
    assert [row["id"] for row in actual[0]["results"]][:2] == ["tmdb:movie:18", "tmdb:tv:18"]
    assert [row["id"] for row in actual[1]["results"]] == ["tmdb:tv:18"]
    assert actual[2]["results"] == []

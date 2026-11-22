from contextlib import contextmanager
import json
from types import SimpleNamespace

import pytest

from tools.qa import smoke_story_arm_http as qa


def test_native_arm_gate_rejects_wrong_architecture_before_model(monkeypatch):
    monkeypatch.setattr(qa.platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(qa, "check_model", lambda _: pytest.fail("model opened before architecture check"))
    with pytest.raises(RuntimeError, match="native Linux ARM64"):
        qa.smoke("unused", require_native_arm=True)


def test_failed_fp32_probe_cannot_report_http_pass(monkeypatch):
    monkeypatch.setattr(qa, "check_model", lambda _: {"status": "inference_failed"})
    monkeypatch.setattr(qa, "launch", lambda *_: pytest.fail("server launched before verified inference"))
    with pytest.raises(RuntimeError, match="inference_failed"):
        qa.smoke("unused")


def test_http_checks_real_wire_contract_not_just_health(monkeypatch):
    monkeypatch.setattr(qa, "check_model", lambda _: {"status": "ok", "variant": "fp32", "embedding_size": 384})
    @contextmanager
    def launch(catalog, *_):
        data = json.loads(catalog.read_text(encoding="utf-8"))
        assert "Синтетический" in data["title"] and catalog.name == "synthetic-qa-only.jsonl"
        yield 9000, SimpleNamespace(poll=lambda: None)
    monkeypatch.setattr(qa, "launch", launch)
    monkeypatch.setattr(qa, "wait_health", lambda *_: 0.1)
    def wrong_result(port, route, body):
        assert port == 9000 and route == "/v1/search" and json.loads(body)["query"]
        return {"source": "tmdb", "results": []}
    monkeypatch.setattr(qa, "request", wrong_result)
    with pytest.raises(RuntimeError, match="differs from expected"):
        qa.smoke("unused")


@pytest.mark.parametrize("rewrite", [False, True])
def test_application_cache_restart_requires_same_snapshot_and_exact_response(monkeypatch, rewrite):
    monkeypatch.setattr(qa, "check_model", lambda _: {"status": "ok", "variant": "fp32", "embedding_size": 384})
    calls = []
    exits = []

    @contextmanager
    def launch(catalog, model, batch_size, *, cache_dir):
        assert len(exits) == len(calls)
        calls.append((catalog, model, batch_size, cache_dir))
        root = cache_dir / "server_passage_snapshots_v1"
        root.mkdir(exist_ok=True, parents=True)
        snapshot = root / "fixture.wbsvec"
        if len(calls) == 1:
            snapshot.write_bytes(b"placeholder")
        elif rewrite:
            replaced = root / "replacement"
            replaced.write_bytes(snapshot.read_bytes())
            replaced.replace(snapshot)
        yield 9000, SimpleNamespace(poll=lambda: None)
        exits.append(True)

    monkeypatch.setattr(qa, "launch", launch)
    monkeypatch.setattr(qa, "wait_health", lambda *_: len(calls) / 10)
    monkeypatch.setattr(qa, "request", lambda *args: {"source": "tmdb", "results": [dict(
        id=f"tmdb:movie:{qa._FIXTURE_ID}", media_type="movie", title=qa._FIXTURE_TITLE,
        overview=qa._OVERVIEW, evidence=qa._OVERVIEW, language="ru-RU", year=2020,
    )]})
    if rewrite:
        with pytest.raises(RuntimeError, match="rewrote"):
            qa.smoke("fixture", cache_restart=True)
    else:
        result = qa.smoke("fixture", cache_restart=True)
        assert result["readiness_seconds"] == 0.1 and result["warm_readiness_seconds"] == 0.2
        assert result["identical_restart_response"] and result["persisted_passage_snapshot_unchanged"]
    assert calls[0] == calls[1] and len(exits) == 2

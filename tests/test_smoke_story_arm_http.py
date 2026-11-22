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

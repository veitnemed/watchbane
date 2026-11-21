from contextlib import contextmanager
from hashlib import sha256
import json
from types import SimpleNamespace

import pytest

from tools.qa import exercise_story_handover as qa


@pytest.fixture
def inputs(tmp_path):
    def catalog(name, identifier):
        path = tmp_path / name
        path.write_text(json.dumps({"media_type": "movie", "tmdb_id": identifier,
                                    "title": "Fixture", "overview": "Описание.", "language": "ru-RU"})
                        + "\n", encoding="utf-8")
        return path, sha256(path.read_bytes()).hexdigest()
    old, old_pin = catalog("old.jsonl", 1)
    new, new_pin = catalog("new.jsonl", 2)
    query = tmp_path / "query.txt"
    query.write_text("описание", encoding="utf-8")
    return SimpleNamespace(old_catalog=old, old_sha256=old_pin, new_catalog=new, new_sha256=new_pin,
                           marker_id="tmdb:movie:2", query_file=query, model_dir=tmp_path, batch_size=4,
                           startup_seconds=1, samples=2)


def _fake_processes(monkeypatch, *, wrong_marker=False, bad_ready=False, new_not_ready=0):
    active, posts = set(), []
    new_health = 0
    @contextmanager
    def launch(catalog, *_args):
        name = catalog.stem
        active.add(name)
        try:
            yield name, SimpleNamespace(poll=lambda: 3 if name == "malformed" and not bad_ready else None)
        finally:
            active.remove(name)
    def request(server, path, body=None):
        nonlocal new_health
        assert server in active
        if path == "/healthz":
            if server == "new":
                new_health += 1
                return {"ready": new_health > new_not_ready}
            return {"ready": True}
        assert json.loads(body)["limit"] == 10
        posts.append((server, set(active)))
        return {"source": "tmdb", "results": [{
            "id": "tmdb:movie:2" if server == "new" and not wrong_marker else "tmdb:movie:1"
        }]}
    monkeypatch.setattr(qa, "launch", launch)
    monkeypatch.setattr(qa, "request", request)
    return active, posts


def test_checks_bad_and_marker_before_routing_new(inputs, monkeypatch):
    active, posts = _fake_processes(monkeypatch, new_not_ready=3)
    result = qa.exercise(inputs)
    assert result["bad_rejected"] and result["switched"] and result["rolled_back_and_restored"]
    assert [item[0] for item in posts] == ["old", "old", "old", "old", "new", "old", "old", "new", "new", "old", "new", "new"]
    assert posts[1][1] == {"old", "malformed"}
    assert all(running == {"old", "new"} for _, running in posts[2:])
    assert result["route"]["new_after_switch"]["ok"] == 2 and not active
    assert result["route"]["old_during_preparation"]["ok"] == 2
    assert result["route"]["old_after_rollback"]["ok"] == 1
    assert "p95_ms" in result["route"]["new_after_restore"]


@pytest.mark.parametrize(("mode", "error"), [("marker", "wrong generation marker"),
                                             ("bad", "malformed candidate reported ready")])
def test_does_not_route_new_after_failed_verification(inputs, monkeypatch, mode, error):
    active, posts = _fake_processes(monkeypatch, wrong_marker=mode == "marker", bad_ready=mode == "bad")
    with pytest.raises(qa.ExerciseError, match=error):
        qa.exercise(inputs)
    assert [server for server, _ in posts] == (["old", "old", "new"] if mode == "marker" else ["old"])
    assert not active


def test_rejects_bad_pin_before_launch(inputs, monkeypatch):
    inputs.new_sha256 = "a" * 64
    monkeypatch.setattr(qa, "launch", lambda *_: pytest.fail("launch before pin validation"))
    with pytest.raises(qa.ExerciseError, match="does not match"):
        qa.exercise(inputs)

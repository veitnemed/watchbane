from hashlib import sha256
import json

import pytest

from tools.qa import benchmark_story_server as bench


def dump(rows):
    return b"".join((json.dumps(row) + "\n").encode() for row in rows)


def digest(raw):
    return sha256(raw).hexdigest()


def test_fixture_seal_and_typed_pair_are_both_required():
    t = dict(media_type="movie", tmdb_id=1, identity_label_ru="Назв", source_url="test")
    rows = [dict(id=str(i), query=f"текст {i}", expected="known_target", group="movie:1", target=t)
            for i in range(2)]
    raw = dump(rows)
    assert bench.parse_cases(raw, digest(raw), {"known_target": 2})[-1][-1] == "tmdb:movie:1"
    with pytest.raises(ValueError, match="digest"):
        bench.parse_cases(raw + b" ", digest(raw), {"known_target": 2})
    rows[1]["group"] = "tv:1"
    raw = dump(rows)
    with pytest.raises(ValueError, match="row 2"):
        bench.parse_cases(raw, digest(raw), {"known_target": 2})


def test_catalog_schema_and_language_match_index_eligibility(tmp_path):
    p = tmp_path / "set.jsonl"
    p.write_bytes(dump([dict(media_type="tv", tmdb_id=i, title="T", overview="O",
                             language=lang, year=None)
                        for i, lang in [(1, "en-US"), (2, "ru-RU")]]))
    assert bench.indexed_ids(p, digest(p.read_bytes())) == {"tmdb:tv:2"}
    p.write_bytes(b"{}")
    with pytest.raises(ValueError):
        bench.indexed_ids(p, digest(b"{}"))


def test_scoring_keeps_missing_covered_controls_and_protocol_errors_separate():
    cases = [("known_target", "indexed hit", "tmdb:movie:1"),
             ("known_target", "indexed miss", "tmdb:tv:1"),
             ("known_target", "not indexed", "tmdb:movie:3"),
             ("out_of_scope", "false cards", None),
             ("out_of_scope", "foreign card", None),
             ("out_of_scope", "empty", None),
             ("insufficient_detail", "insufficient", None)]
    answers = [["tmdb:tv:1", "tmdb:movie:1"], [], [], ["tmdb:movie:1"],
               ["tmdb:tv:999"], [], ["tmdb:tv:1"]]

    def search(_query):
        return {"source": "tmdb", "results": [{"id": k} for k in answers.pop(0)]}

    report = bench.score(cases, {"tmdb:movie:1", "tmdb:tv:1"}, search)
    assert report["known"]["hit_at_1_all"] == {"n": 0, "d": 3, "rate": 0}
    assert report["known"]["hit_at_5_all"]["d"] == 3
    assert report["known"]["hit_at_5_covered"] == {"n": 1, "d": 2, "rate": .5}
    assert report["known"]["missing_target_queries"] == 1
    assert report["out_of_scope"]["false_positive_cards"] == {"n": 1, "d": 2, "rate": .5}
    assert report["insufficient_detail"]["returned_cards"]["rate"] == 1
    assert report["request_errors"]["out_of_scope"] == 1
    assert report["latency_successful_http_ms"]["count"] == 6


def test_cli_rejects_bad_seal_before_any_server_contact(tmp_path, monkeypatch):
    path = tmp_path / "bad.jsonl"
    path.write_bytes(b"bad")
    monkeypatch.setattr(bench, "loopback_search", lambda *_: pytest.fail("Contacted endpoint"))
    args = [arg for name in ["cases", "catalog"]
            for arg in (f"--{name}", str(path), f"--{name}-sha256", "0" * 64)]
    with pytest.raises(SystemExit) as e:
        bench.main(args)
    assert e.value.code == 2


def test_loopback_transport_keeps_clue_out_of_url_and_checks_no_store(monkeypatch):
    requests = []

    class Response:
        def __init__(self, payload, headers):
            self.payload, self.headers = payload, headers

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self, _):
            return json.dumps(self.payload).encode()

    class Opener:
        def open(self, request, timeout):
            requests.append(request)
            assert timeout == 3
            if len(requests) == 1:
                return Response({"ready": True}, {})
            return Response({"source": "tmdb", "results": []}, {"Cache-Control": "no-store"})

    def build(proxy, redirect):
        assert proxy.proxies == {}
        assert redirect.redirect_request(None, None, 302, None, {}, "https://example.com") is None
        return Opener()

    monkeypatch.setattr(bench, "build_opener", build)
    post = bench.loopback_search(9876, 3)
    assert post("секретный запрос")["results"] == []
    assert [r.full_url for r in requests] == ["http://127.0.0.1:9876/healthz",
                                             "http://127.0.0.1:9876/v1/search"]
    assert json.loads(requests[1].data) == {"query": "секретный запрос", "limit": 5}


def test_unverified_target_exclusion_preserves_other_lanes_and_typed_identity():
    cases = [("known_target", "a", "tmdb:movie:7"), ("known_target", "b", "tmdb:tv:7"),
             ("known_target", "c", "tmdb:tv:7"), ("out_of_scope", "d", None)]
    assert bench.exclude_unverified(cases, ["tmdb:tv:7"]) == [cases[0], cases[3]]
    for exclusions in (["tmdb:tv:8"], ["tmdb:tv:7", "tmdb:tv:7"]):
        with pytest.raises(ValueError, match="distinct targets"):
            bench.exclude_unverified(cases, exclusions)

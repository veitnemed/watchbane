from types import SimpleNamespace
from unittest.mock import Mock

import pytest

pytest.importorskip("fastapi")

from candidates.story_semantic import StoryCandidateTrace
from tools.qa import run_story_retrieval_funnel as runner
from tools.qa.story_retrieval_funnel import FunnelTrace, score_retrieval_funnel


def test_evaluate_uses_catalogue_digest_and_one_observation_per_query(tmp_path, monkeypatch):
    synopsis = "fake provider synopsis"
    path = tmp_path / "sealed.jsonl"
    path.write_bytes(b"sealed rows")
    (tmp_path / "onnx").mkdir()
    (tmp_path / "onnx/model.onnx").write_bytes(b"fixture only")
    a, b, pending = "tmdb:movie:1", "tmdb:tv:1", "tmdb:tv:2"
    cases = [("known_target", "secret accuracy query", a),
             ("known_target", "pending should not run", pending),
             ("out_of_scope", "secret failure query", None)]
    cases_parser = Mock(return_value=cases)
    monkeypatch.setattr(runner, "parse_cases", cases_parser)
    docs = [SimpleNamespace(key=key, overview=synopsis) for key in (a, b)]
    monkeypatch.setattr(runner, "_load_documents", Mock(return_value=(docs, "x")))
    model = Mock(return_value=SimpleNamespace(variant="fp32", cache_identity="model-pin"))
    monkeypatch.setattr(runner, "LocalE5", model)
    calls = []

    class Engine:
        def __init__(self, documents, encoder):
            assert documents is docs and encoder is model.return_value

        def search(self, query, *, limit, include_route_reason, observe_candidates):
            calls.append(query)
            assert limit == 5 and include_route_reason is True
            if query == cases[2][1]:
                raise RuntimeError(query)
            observe_candidates(StoryCandidateTrace("retrieved", (a, b), (b,), frozenset({a, b})))
            return SimpleNamespace(hits=[SimpleNamespace(document=docs[0])])

    monkeypatch.setattr(runner, "SemanticStorySearch", Engine)
    result = runner.evaluate((path, path, tmp_path), cases_sha256="sealed-pin",
                             catalog_sha256="x", exclusions=[pending])
    assert calls == [cases[0][1], cases[2][1]]
    cases_parser.assert_called_once_with(b"sealed rows", "sealed-pin", runner.LANES)
    assert result["covered_funnel"]["top5_of_covered"] == {"n": 1, "d": 1}
    assert result["cohorts"]["out_of_scope"]["routes"]["error"] == 1
    assert result["excluded_unverified_query_count"] == result["excluded_unverified_target_count"] == 1
    assert not any(private in repr(result) for private in (synopsis, a, b, pending, *(row[1] for row in cases)))
    model.assert_called_once_with(tmp_path)
    with pytest.raises(ValueError, match="exact nonempty"):
        runner.evaluate((path, path, tmp_path), cases_sha256="sealed-pin", catalog_sha256="wrong")
    assert model.call_count == 1


def test_missing_observation_fails_closed():
    engine = SimpleNamespace(search=lambda *_args, **_kwargs: SimpleNamespace(hits=()))
    with pytest.raises(ValueError, match="one observation"):
        list(runner._collect(engine, [("out_of_scope", "arbitrary query", None)]))


def test_cli_status_and_output_do_not_expose_runtime_details(monkeypatch, capsys):
    key = "tmdb:movie:1"
    report = score_retrieval_funnel([FunnelTrace("out_of_scope", "error")], indexed=frozenset((key,)))
    args = ["--cases", "private-path", "--catalog", "other-private-path", "--model-dir", "third-private",
            "--cases-sha256", "c" * 64, "--catalog-sha256", "a" * 64]
    monkeypatch.setattr(runner, "evaluate", lambda *_args, **_kw: report)
    assert runner.main(args) == 1
    first = capsys.readouterr()
    assert key not in first.out
    assert not first.err

    monkeypatch.setattr(runner, "evaluate", Mock(side_effect=RuntimeError("sensitive exception details")))
    with pytest.raises(SystemExit) as error:
        runner.main(args)
    assert error.value.code == 2
    second = capsys.readouterr()
    assert not second.out
    assert "sensitive exception" not in second.err and "private-path" not in second.err

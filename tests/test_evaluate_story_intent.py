from hashlib import sha256
import json

import pytest

from tools.qa import evaluate_story_intent as audit


def sealed(*rows):
    raw = "".join(json.dumps(row) + "\n" for row in rows).encode()
    return raw, sha256(raw).hexdigest()


def make(identifier, query, expected, **options):
    return dict(id=identifier, query=query, expected=expected, **options)


def test_preflight_rejects_bad_digest_and_schema():
    raw, digest = sealed(make("a", "корабль", "search"))
    with pytest.raises(ValueError, match="digest mismatch"):
        audit.parse_sealed(raw + b"\n", digest)
    with pytest.raises(ValueError, match="row 1"):
        audit.parse_sealed(*sealed(make("a", "корабль", "match")))
    with pytest.raises(ValueError, match="row 2"):
        audit.parse_sealed(*sealed(make("a", "Корабль", "search"), make("b", "корабль", "search")))


def test_aggregate_distinguishes_three_actions_and_compares_injected_rule():
    ref = "как настроить маршрутизатор"
    rows = audit.parse_sealed(*sealed(
        make("ref", ref, "refuse"),
        make("amb", "космос", "clarify"),
        make("empty", "фильм", "clarify"),
        make("title", ref, "search", catalog_titles=[ref]),
    ))
    report = audit.evaluate(rows, candidate=lambda q, titles:
                            "clarify" if q == "космос" else audit.current_guard(q, titles))
    baseline = report["current_pre_search_guard"]
    assert baseline["expected_by_predicted"]["clarify"] == {"refuse": 0, "clarify": 1, "search": 1}
    assert baseline["expected_by_predicted"]["refuse"]["refuse"] == 1
    assert baseline["expected_by_predicted"]["search"]["search"] == 1
    assert report["candidate"]["correct"] == 4


def test_cli_outputs_only_counts_and_hash(tmp_path, capsys):
    raw, digest = sealed(make("fixture-secret-id", "неизвестный сюжетный запрос", "search"))
    file = tmp_path / "fixture.jsonl"
    file.write_bytes(raw)
    assert audit.main(["--cases", str(file), "--cases-sha256", digest]) == 0
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert result["cases_sha256"] == digest
    assert result["rules"]["current_pre_search_guard"]["n"] == 1
    assert "fixture-secret-id" not in captured.out and "сюжетный" not in captured.out


def test_sealed_acceptance_schema_does_not_confuse_exclusion_with_nonfilm_refusal():
    row = dict(id="a", query="фильм без убийств", expected_route="clarify", category="explicit_exclusion")
    cases = audit.parse_sealed(*sealed(row))
    assert audit.evaluate(cases)["current_pre_search_guard"]["expected_by_predicted"]["clarify"]["clarify"] == 1
    with pytest.raises(ValueError, match="row 1"):
        audit.parse_sealed(*sealed(dict(row, category="")))

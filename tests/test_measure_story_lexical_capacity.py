import json

from tools.qa import measure_story_lexical_capacity as qa


def test_fixture_is_distinct_and_deterministic_and_changes_density():
    for density in ("low", "high"):
        docs = list(qa.make_documents(1000, density))
        assert docs == list(qa.make_documents(1000, density))
        assert len({doc.overview for doc in docs}) == 1000
        assert len({doc.key for doc in docs}) == 1000
    low, high = (qa.measure(40, density) for density in ("low", "high"))
    assert high["gram_postings"] > 2 * low["gram_postings"]
    for run in (low, high):
        assert run["prepared_posting_array_bytes"] == 12 * run["gram_postings"]
        assert 0 <= run["exact_lexical_top40_probes"] <= run["parity_probes"]
        assert run["max_absolute_score_delta"] < 1e-12


def test_cli_scopes_the_results(capsys):
    assert qa.main(["--rows", "3"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["scope"] == "synthetic_qa_only_no_e5_no_rss"
    assert [run["rows"] for run in report["runs"]] == [3, 3]

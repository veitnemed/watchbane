import json
from hashlib import sha256

import pytest

from tools.qa import evaluate_story_query_intent as qa


def test_selection_and_report_count_only_additional_suppressions():
    def case(i, intent, *, cards=True, short=False, query="условие", exact=False):
        return qa.Case(str(i), query, intent, short, "fixture", cards, exact)

    cal = [
        (case(1, "nonfilm"), .91),
        (case(2, "nonfilm"), .91),
        (case(3, "nonfilm"), .81),
        (case(4, "film", short=True), .81),
        (case(5, "nonfilm", cards=False), .99),
        (case(6, "film", query="«Фильм»", short=True), .99),
        (case(7, "film", exact=True), .99),
    ]
    assert qa.choose_cutoff(cal) == .91
    assert qa.choose_cutoff(cal[2:]) == 2
    result = qa.report(cal, .91)
    assert result["suppression_precision"] == {"n": 2, "d": 2}
    assert result["baseline_nonfilm_card_reduction"] == {"n": 2, "d": 3}
    assert result["counts"]["nonfilm_baseline_already_empty"] == 1
    assert all(result["gates"].values())
    assert not qa.report(cal, .81)["gates"]["no_new_short_film_suppression"]


def test_private_select_validate_lock_and_reject_cross_split_family(tmp_path, capsys, monkeypatch):
    pytest.importorskip("sklearn")

    def files(split, examples):
        rows = [{"id": f"{split}-{i}", "family": family, "query": query, "intent": intent, "short": short}
                for i, (family, query, intent, short) in enumerate(examples)]
        file = tmp_path / split
        raw = b"\n".join(qa.canonical(row) for row in rows)
        file.write_bytes(raw)
        baseline_raw = qa.canonical({r["id"]: {"baseline_cards": True, "exact_title": False} for r in rows})
        baseline_path = tmp_path / (split + ".baseline")
        baseline_path.write_bytes(baseline_raw)
        return [f"--{split}", str(file), f"--{split}-sha256", sha256(raw).hexdigest()], [
            "--baseline", str(baseline_path), "--baseline-sha256", sha256(baseline_raw).hexdigest(),
        ]

    train, _ = files("train", [("a", "Подскажи инструкцию для ремонта шкафа", "nonfilm", False),
                               ("a", "Подскажи инструкцию для ремонта печи", "nonfilm", False),
                               ("a", "Пастух спасает друга", "film", True),
                               ("a", "Пастух мстит королю", "film", True)])
    cal, cal_baseline = files("calibration", [("b", "Подскажи инструкцию по ремонту мебели", "nonfilm", False),
                                             ("b", "Пастух бежит из тюрьмы", "film", True)])
    val, val_baseline = files("validation", [("c", "Подскажи инструкцию для ремонта стен", "nonfilm", False),
                                            ("c", "Пастух спасает волка", "film", True)])
    qa.main(["select", *train, *cal, *cal_baseline])
    lock = capsys.readouterr().out.encode()
    assert b"query" not in lock.replace(b"story-query-intent-v1", b"")
    selection = tmp_path / "selection"
    selection.write_bytes(lock)
    calibration_path = tmp_path / "calibration"
    calibration_path.unlink()
    selection_args = ["--selection", str(selection), "--selection-sha256", sha256(lock).hexdigest()]
    monkeypatch.setattr(qa, "choose_cutoff", lambda _: pytest.fail("validation recalibrated"))
    qa.main(["validate", *train, *selection_args, *val, *val_baseline])
    result = json.loads(capsys.readouterr().out)
    assert result["cutoff_hex"] == json.loads(lock)["cutoff_hex"]
    assert result["selection_sha256"] == sha256(lock).hexdigest()
    assert "private_calibration_fingerprints" not in result
    val, val_baseline = files("validation", [(" b ", "Инструкция для кулинарии", "nonfilm", False),
                                            ("z", "Король наступает", "film", True)])
    with pytest.raises(ValueError, match="overlapping split family"):
        qa.main(["validate", *train, *selection_args, *val, *val_baseline])


def test_short_guard_is_derived_from_real_word_tokens_not_annotation():
    short = qa.Case("short", "космос и тайна", "film", False, "fixture", True)
    long = qa.Case("long", "герой скрывается у входа в театр", "film", True, "fixture", True)
    result = qa.report(((short, .9), (long, .1)), .8)
    assert result["counts"]["short_film_total"] == 1
    assert result["counts"]["short_film_newly_suppressed"] == 1
    assert not result["gates"]["no_new_short_film_suppression"]

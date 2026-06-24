import json


def test_feature_ablation_module_imports():
    import model.feature_ablation

    assert model.feature_ablation is not None


def test_genre_markup_efficiency_module_imports():
    import model.genre_markup_efficiency

    assert model.genre_markup_efficiency is not None


def test_report_functions_import():
    from model.feature_ablation import (
        collect_feature_ablation_report,
        format_feature_ablation_report,
    )
    from model.genre_markup_efficiency import (
        collect_genre_markup_efficiency_report,
        format_genre_markup_efficiency_report,
    )

    assert callable(collect_feature_ablation_report)
    assert callable(format_feature_ablation_report)
    assert callable(collect_genre_markup_efficiency_report)
    assert callable(format_genre_markup_efficiency_report)


def test_tmp_path_can_write_utf8_json(tmp_path):
    path = tmp_path / "test.json"
    payload = {"title": "Во все тяжкие"}

    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    assert "Во все тяжкие" in path.read_text(encoding="utf-8")

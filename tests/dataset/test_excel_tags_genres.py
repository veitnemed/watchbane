"""Excel export/import modules stay free of UI imports."""

import importlib


def test_excel_work_wrapper_reexports_subpackage() -> None:
    from dataset.excel.export import export_dataset_to_excel
    from dataset.excel_work import export_dataset_to_excel as wrapped

    assert export_dataset_to_excel is wrapped


def test_tags_work_wrapper_reexports_mutations() -> None:
    from dataset.tags.mutations import add_tag
    from dataset.tags_work import add_tag as wrapped

    assert add_tag is wrapped


def test_genre_stats_wrapper_reexports_catalog() -> None:
    from dataset.genres.stats import build_dataset_genre_catalog
    from dataset.genre_stats import build_dataset_genre_catalog as wrapped

    assert build_dataset_genre_catalog is wrapped


def test_genre_import_wrapper_reexports_apply() -> None:
    from dataset.genre_import import apply_genre_markup
    from dataset.genres.import_flow import apply_genre_markup as source

    assert apply_genre_markup is source

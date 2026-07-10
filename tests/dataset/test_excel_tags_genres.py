"""Excel export/import modules stay free of UI imports."""


def test_excel_work_wrapper_reexports_subpackage() -> None:
    from dataset.excel.export import export_dataset_to_excel
    from dataset.excel_work import export_dataset_to_excel as wrapped

    assert export_dataset_to_excel is wrapped


def test_genre_stats_wrapper_reexports_catalog() -> None:
    from dataset.genres.stats import build_dataset_genre_catalog
    from dataset.genre_stats import build_dataset_genre_catalog as wrapped

    assert build_dataset_genre_catalog is wrapped

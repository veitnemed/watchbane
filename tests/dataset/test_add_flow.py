"""Add-title resolve bundle does not import web layer."""

import importlib


def test_add_title_service_does_not_import_web() -> None:
    module = importlib.import_module("dataset.add_title_service")
    source = importlib.import_module(module.__name__).__file__
    assert source is not None
    with open(source, encoding="utf-8") as handle:
        text = handle.read()
    assert "web." not in text
    assert "from web" not in text


def test_add_flow_preview_does_not_import_web() -> None:
    module = importlib.import_module("dataset.add_flow.preview")
    source = importlib.import_module(module.__name__).__file__
    assert source is not None
    with open(source, encoding="utf-8") as handle:
        text = handle.read()
    assert "web." not in text
    assert "from web" not in text

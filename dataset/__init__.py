"""Пользовательский dataset: записи, meta, Excel, статистика, теги, резолв тайтлов."""

from importlib import import_module


__all__ = ["service"]


def __getattr__(name: str):
    if name == "service":
        module = import_module("dataset.service")
        globals()[name] = module
        return module
    raise AttributeError(f"module 'dataset' has no attribute {name!r}")

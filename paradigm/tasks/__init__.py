import importlib

__all__ = ["DoorsTask", "PRLTask", "RDMTask", "ReversalEngine"]


def __getattr__(name: str):
    if name == "DoorsTask":
        return getattr(importlib.import_module("paradigm.tasks.doors"), name)
    if name in {"PRLTask", "ReversalEngine"}:
        return getattr(importlib.import_module("paradigm.tasks.prl"), name)
    if name == "RDMTask":
        return getattr(importlib.import_module("paradigm.tasks.rdm"), name)
    raise AttributeError(name)

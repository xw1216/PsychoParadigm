import importlib

__all__ = ["DoorsTask", "PRLTask", "RDMTask", "MarkerTestTask", "ReversalEngine"]


def __getattr__(name: str):
    if name == "DoorsTask":
        return getattr(importlib.import_module("paradigm.tasks.doors"), name)
    if name in {"PRLTask", "ReversalEngine"}:
        return getattr(importlib.import_module("paradigm.tasks.prl"), name)
    if name == "RDMTask":
        return getattr(importlib.import_module("paradigm.tasks.rdm"), name)
    if name == "MarkerTestTask":
        return getattr(importlib.import_module("paradigm.tasks.marker_test"), name)
    raise AttributeError(name)

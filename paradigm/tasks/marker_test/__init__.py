import importlib

from .marker_test_logic import build_test_marker_sequence

__all__ = ["MarkerTestTask", "build_test_marker_sequence"]


def __getattr__(name: str):
    if name == "MarkerTestTask":
        return getattr(importlib.import_module("paradigm.tasks.marker_test.marker_test"), name)
    raise AttributeError(name)
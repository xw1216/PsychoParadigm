from importlib import import_module
from typing import Any

__all__ = ["summarize_doors_run", "summarize_prl_run", "summarize_rdm_run"]


def __getattr__(name: str) -> Any:
    if name == "summarize_doors_run":
        return import_module(".doors.metrics", __name__).summarize_doors_run
    if name == "summarize_prl_run":
        return import_module(".prl.metrics", __name__).summarize_prl_run
    if name == "summarize_rdm_run":
        return import_module(".rdm.metrics", __name__).summarize_rdm_run
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
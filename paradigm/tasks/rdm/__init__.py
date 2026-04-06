import importlib

from .rdm_logic import (
    RDMTrial,
    build_rdm_trials,
    determine_rdm_trial_quality,
    resolve_rdm_feedback_plan,
)

__all__ = [
    "RDMTask",
    "RDMTrial",
    "build_rdm_trials",
    "determine_rdm_trial_quality",
    "resolve_rdm_feedback_plan",
]


def __getattr__(name: str):
    if name == "RDMTask":
        return getattr(importlib.import_module("paradigm.tasks.rdm.rdm"), name)
    raise AttributeError(name)
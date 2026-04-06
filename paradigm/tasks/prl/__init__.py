import importlib

from .prl_logic import (
    PRLTrialState,
    RescorlaWagnerAgent,
    ReversalEngine,
    classify_prl_expectedness,
    classify_prl_trial_phase,
    resolve_prl_timeout_policy,
)

__all__ = [
    "PRLTask",
    "PRLTrialState",
    "RescorlaWagnerAgent",
    "ReversalEngine",
    "classify_prl_expectedness",
    "classify_prl_trial_phase",
    "resolve_prl_timeout_policy",
]


def __getattr__(name: str):
    if name == "PRLTask":
        return getattr(importlib.import_module("paradigm.tasks.prl.prl"), name)
    raise AttributeError(name)
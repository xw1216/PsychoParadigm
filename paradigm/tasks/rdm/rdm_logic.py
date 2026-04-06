import random
from dataclasses import dataclass

from paradigm.config import RDMTaskConfig


@dataclass(slots=True)
class RDMTrial:
    block: int
    trial_index: int
    signed_coherence: float

    @property
    def direction(self) -> str:
        return "left" if self.signed_coherence < 0 else "right"

    @property
    def coherence(self) -> float:
        return abs(self.signed_coherence)


def resolve_rdm_feedback_plan(*, correct: bool, timeout: bool, feedback_mode: str) -> tuple[str | None, str | None, str | None]:
    if feedback_mode == "none":
        return "omitted", None, None
    if timeout:
        return "timeout", "feedback.timeout", "反应过慢"
    if correct:
        return "correct", "feedback.correct", "正确"
    return "error", "feedback.error", "错误"


def determine_rdm_trial_quality(*, timeout: bool, fixation_break_detected: bool, invalid_response: bool, exclude_timeouts_from_analysis: bool) -> tuple[bool, str | None]:
    if fixation_break_detected:
        return True, "fixation_break"
    if invalid_response:
        return True, "invalid_response"
    if timeout and exclude_timeouts_from_analysis:
        return True, "timeout"
    return False, None


def build_rdm_trials(task_config: RDMTaskConfig, rng: random.Random) -> list[RDMTrial]:
    condition_grid: list[float] = []
    for signed_coherence in task_config.signed_coherence_levels:
        for _ in range(task_config.trials_per_signed_coherence):
            condition_grid.append(signed_coherence)
    rng.shuffle(condition_grid)

    total_trials = len(condition_grid)
    block_size = max(1, total_trials // task_config.blocks)
    trials: list[RDMTrial] = []
    for index, signed_coherence in enumerate(condition_grid, start=1):
        block = min(((index - 1) // block_size) + 1, task_config.blocks)
        trials.append(RDMTrial(block=block, trial_index=index, signed_coherence=signed_coherence))
    return trials

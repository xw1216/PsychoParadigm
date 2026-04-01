from dataclasses import dataclass
from math import exp
from typing import Any


@dataclass(slots=True)
class PRLTrialState:
    block: int
    trial_index: int
    trial_in_block: int
    good_side: str
    is_reversal_boundary: bool


class ReversalEngine:
    def __init__(self, *, blocks: int, trials_per_block: int, reward_probability_good: float, reward_probability_bad: float, rng: Any) -> None:
        self.blocks = blocks
        self.trials_per_block = trials_per_block
        self.reward_probability_good = reward_probability_good
        self.reward_probability_bad = reward_probability_bad
        self.rng = rng
        self.block_good_sides = ["left" if block % 2 == 1 else "right" for block in range(1, blocks + 1)]

    def get_trial_state(self, global_trial_index: int) -> PRLTrialState:
        block = ((global_trial_index - 1) // self.trials_per_block) + 1
        trial_in_block = ((global_trial_index - 1) % self.trials_per_block) + 1
        is_reversal_boundary = trial_in_block == 1 and block > 1
        return PRLTrialState(block=block, trial_index=global_trial_index, trial_in_block=trial_in_block, good_side=self.block_good_sides[block - 1], is_reversal_boundary=is_reversal_boundary)

    def resolve_feedback_for_state(self, state: PRLTrialState, choice: str) -> tuple[bool, bool]:
        chosen_good = choice == state.good_side
        probability = self.reward_probability_good if chosen_good else self.reward_probability_bad
        reward = self.rng.random() < probability
        return chosen_good, reward


def classify_prl_expectedness(chosen_good: bool, reward: bool) -> str:
    if chosen_good and reward:
        return "expected_reward"
    if chosen_good and not reward:
        return "unexpected_no_reward"
    if not chosen_good and reward:
        return "unexpected_reward"
    return "expected_no_reward"


def classify_prl_trial_phase(state: PRLTrialState, *, total_blocks: int, trials_per_block: int, early_post_reversal_trials: int, relearning_trials: int, stable_pre_reversal_trials: int) -> str:
    if state.block == 1 and state.trial_in_block <= early_post_reversal_trials:
        return "initial_stable"
    if state.block > 1 and state.trial_in_block <= early_post_reversal_trials:
        return "early_post_reversal"
    if state.block > 1 and state.trial_in_block <= early_post_reversal_trials + relearning_trials:
        return "relearning"
    if state.block < total_blocks and state.trial_in_block > 0:
        block_tail_start = max(1, trials_per_block - stable_pre_reversal_trials + 1)
        if state.trial_in_block >= block_tail_start:
            return "stable_pre_reversal"
    return "late_stable"


def resolve_prl_timeout_policy(timeout: bool) -> dict[str, bool | str]:
    if timeout:
        return {
            "rl_update_applied": False,
            "counted_for_choice_dynamics": False,
            "timeout_feedback_presented": True,
            "exclude_trial": True,
            "exclude_reason": "timeout",
            "invalid_response": True,
        }
    return {
        "rl_update_applied": True,
        "counted_for_choice_dynamics": True,
        "timeout_feedback_presented": False,
        "exclude_trial": False,
        "exclude_reason": None,
        "invalid_response": False,
    }


class RescorlaWagnerAgent:
    def __init__(self, learning_rate: float, inverse_temperature: float, initial_q: float) -> None:
        self.learning_rate = learning_rate
        self.inverse_temperature = inverse_temperature
        self.q_values = {"left": initial_q, "right": initial_q}

    def choice_probability_left(self) -> float:
        left_score = exp(self.inverse_temperature * self.q_values["left"])
        right_score = exp(self.inverse_temperature * self.q_values["right"])
        return left_score / (left_score + right_score)

    def update(self, choice: str, reward: bool) -> float:
        outcome = 1.0 if reward else 0.0
        prediction_error = outcome - self.q_values[choice]
        self.q_values[choice] += self.learning_rate * prediction_error
        return prediction_error

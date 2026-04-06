from collections import deque
from dataclasses import dataclass
from math import exp
from typing import Any


@dataclass(slots=True)
class PRLTrialState:
    block: int
    trial_index: int
    trial_in_block: int
    reversal_index: int
    good_stimulus: str
    left_stimulus: str
    right_stimulus: str
    is_reversal_boundary: bool
    trials_since_reversal: int


@dataclass(slots=True)
class PRLFeedbackOutcome:
    chosen_stimulus: str
    unchosen_stimulus: str
    optimal_choice: bool
    reward: bool
    misleading_feedback: bool


class ReversalEngine:
    def __init__(
        self,
        *,
        blocks: int,
        trials_per_block: int,
        reward_probability_good: float,
        reward_probability_bad: float,
        criterion_window: int,
        criterion_optimal_choices: int,
        min_trials_before_reversal: int,
        stimulus_labels: tuple[str, str],
        rng: Any,
    ) -> None:
        self.blocks = blocks
        self.trials_per_block = trials_per_block
        self.reward_probability_good = reward_probability_good
        self.reward_probability_bad = reward_probability_bad
        self.criterion_window = criterion_window
        self.criterion_optimal_choices = criterion_optimal_choices
        self.min_trials_before_reversal = min_trials_before_reversal
        self.stimulus_labels = stimulus_labels
        self.rng = rng
        self.good_stimulus = stimulus_labels[0]
        self.bad_stimulus = stimulus_labels[1]
        self.reversal_index = 0
        self.trials_since_reversal = 0
        self._pending_reversal = False
        self._optimal_history: deque[bool] = deque(maxlen=criterion_window)

    def _apply_reversal_if_pending(self) -> bool:
        if not self._pending_reversal:
            return False
        self.good_stimulus, self.bad_stimulus = self.bad_stimulus, self.good_stimulus
        self.reversal_index += 1
        self.trials_since_reversal = 0
        self._optimal_history.clear()
        self._pending_reversal = False
        return True

    def get_trial_state(self, global_trial_index: int) -> PRLTrialState:
        is_reversal_boundary = self._apply_reversal_if_pending()
        block = ((global_trial_index - 1) // self.trials_per_block) + 1
        trial_in_block = ((global_trial_index - 1) % self.trials_per_block) + 1
        left_stimulus, right_stimulus = self.stimulus_labels
        return PRLTrialState(
            block=block,
            trial_index=global_trial_index,
            trial_in_block=trial_in_block,
            reversal_index=self.reversal_index,
            good_stimulus=self.good_stimulus,
            left_stimulus=left_stimulus,
            right_stimulus=right_stimulus,
            is_reversal_boundary=is_reversal_boundary,
            trials_since_reversal=self.trials_since_reversal,
        )

    def resolve_feedback_for_state(self, state: PRLTrialState, choice: str) -> PRLFeedbackOutcome:
        chosen_stimulus = state.left_stimulus if choice == "left" else state.right_stimulus
        unchosen_stimulus = state.right_stimulus if choice == "left" else state.left_stimulus
        optimal_choice = chosen_stimulus == state.good_stimulus
        probability = self.reward_probability_good if optimal_choice else self.reward_probability_bad
        reward = self.rng.random() < probability
        misleading_feedback = (optimal_choice and not reward) or ((not optimal_choice) and reward)
        return PRLFeedbackOutcome(
            chosen_stimulus=chosen_stimulus,
            unchosen_stimulus=unchosen_stimulus,
            optimal_choice=optimal_choice,
            reward=reward,
            misleading_feedback=misleading_feedback,
        )

    def update_after_trial(self, *, optimal_choice: bool | None, timeout: bool) -> dict[str, bool | int | None]:
        self.trials_since_reversal += 1
        criterion_reached = False
        trials_to_criterion = None
        if not timeout and optimal_choice is not None:
            self._optimal_history.append(bool(optimal_choice))
            if (
                bool(optimal_choice)
                and self.trials_since_reversal >= self.min_trials_before_reversal
                and len(self._optimal_history) == self.criterion_window
                and sum(self._optimal_history) >= self.criterion_optimal_choices
            ):
                criterion_reached = True
                trials_to_criterion = self.trials_since_reversal
                self._pending_reversal = True
        return {
            "criterion_reached": criterion_reached,
            "trials_to_criterion": trials_to_criterion,
            "reversal_scheduled": self._pending_reversal,
        }


def classify_prl_expectedness(optimal_choice: bool, reward: bool) -> str:
    if optimal_choice and reward:
        return "expected_reward"
    if optimal_choice and not reward:
        return "unexpected_no_reward"
    if not optimal_choice and reward:
        return "unexpected_reward"
    return "expected_no_reward"


def classify_prl_trial_phase(state: PRLTrialState, *, early_post_reversal_trials: int, relearning_trials: int) -> str:
    if state.reversal_index == 0 and state.trials_since_reversal < early_post_reversal_trials + relearning_trials:
        return "initial_learning"
    if state.reversal_index > 0 and state.trials_since_reversal < early_post_reversal_trials:
        return "early_post_reversal"
    if state.reversal_index > 0 and state.trials_since_reversal < early_post_reversal_trials + relearning_trials:
        return "relearning"
    return "stable"


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
    def __init__(
        self,
        positive_learning_rate: float,
        negative_learning_rate: float,
        inverse_temperature: float,
        stickiness: float,
        initial_q: float,
        stimulus_labels: tuple[str, str],
    ) -> None:
        self.positive_learning_rate = positive_learning_rate
        self.negative_learning_rate = negative_learning_rate
        self.inverse_temperature = inverse_temperature
        self.stickiness = stickiness
        self.q_values = {label: initial_q for label in stimulus_labels}

    def choice_probability_left(self, *, left_stimulus: str, right_stimulus: str, previous_choice_stimulus: str | None = None) -> float:
        left_logit = self.inverse_temperature * self.q_values[left_stimulus]
        right_logit = self.inverse_temperature * self.q_values[right_stimulus]
        if previous_choice_stimulus == left_stimulus:
            left_logit += self.stickiness
        if previous_choice_stimulus == right_stimulus:
            right_logit += self.stickiness
        left_score = exp(left_logit)
        right_score = exp(right_logit)
        return left_score / (left_score + right_score)

    def update(self, chosen_stimulus: str, reward: bool) -> tuple[float, float]:
        outcome = 1.0 if reward else 0.0
        prediction_error = outcome - self.q_values[chosen_stimulus]
        learning_rate = self.positive_learning_rate if reward else self.negative_learning_rate
        self.q_values[chosen_stimulus] += learning_rate * prediction_error
        return prediction_error, abs(prediction_error)

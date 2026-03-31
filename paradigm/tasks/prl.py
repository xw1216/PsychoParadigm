from dataclasses import dataclass
from typing import Any
from math import exp

from psychopy import visual

from paradigm.config import AppConfig
from paradigm.runtime import AOIRegion, BaseExperiment, SafeExitRequested


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


class PRLTask(BaseExperiment):
    def __init__(self, participant: str, session: str, config: AppConfig | None = None) -> None:
        super().__init__(task_name="prl", participant=participant, session=session, config=config)
        self.task_config = self.config.prl
        self.reversal_engine = ReversalEngine(
            blocks=self.task_config.blocks,
            trials_per_block=self.task_config.trials_per_block,
            reward_probability_good=self.task_config.reward_probability_good,
            reward_probability_bad=self.task_config.reward_probability_bad,
            rng=self.rng,
        )
        self.left_option = visual.Rect(self.window, width=0.2, height=0.2, pos=(-0.25, 0), lineColor="white", fillColor=None, lineWidth=3)
        self.right_option = visual.Rect(self.window, width=0.2, height=0.2, pos=(0.25, 0), lineColor="white", fillColor=None, lineWidth=3)
        self.left_label = visual.TextStim(self.window, text="A", pos=(-0.25, 0), height=0.07, color="white")
        self.right_label = visual.TextStim(self.window, text="B", pos=(0.25, 0), height=0.07, color="white")
        self.feedback_text = visual.TextStim(self.window, text="", pos=(0, 0), height=0.08, color="white")
        self.choice_aois = [AOIRegion(name="left_option", left=-0.35, right=-0.15, bottom=-0.1, top=0.1), AOIRegion(name="right_option", left=0.15, right=0.35, bottom=-0.1, top=0.1)]
        self.rl_agent = RescorlaWagnerAgent(
            learning_rate=self.task_config.learning_rate,
            inverse_temperature=self.task_config.inverse_temperature,
            initial_q=self.task_config.initial_q,
        )

    def _draw_choice_screen(self, selected: str | None = None) -> None:
        self.left_option.fillColor = "darkgreen" if selected == "left" else None
        self.right_option.fillColor = "darkgreen" if selected == "right" else None
        self.left_option.draw()
        self.right_option.draw()
        self.left_label.draw()
        self.right_label.draw()

    def _draw_feedback(self) -> None:
        self.feedback_text.draw()

    @staticmethod
    def _event(name: str) -> str:
        return f"prl.{name}"

    def run(self) -> None:
        total_trials = self.task_config.blocks * self.task_config.trials_per_block
        mode_prefix = "练习模式：" if self.config.practice.enabled else ""
        trial_rows: list[dict] = []
        try:
            self.show_labrecorder_wait_screen()
            self.experiment_clock.reset()
            self.send_marker_now(event_name=self._event("experiment.start"), metadata={"task": self.task_name})
            self.show_message(
                f"{mode_prefix}概率反转学习任务\n\n请使用左右方向键选择左侧或右侧选项。\n不同阶段的奖励概率会发生变化。\n\n按 {self.continue_key_label()} 开始。"
            )

            previous_choice = None

            for global_trial in range(1, total_trials + 1):
                state = self.reversal_engine.get_trial_state(global_trial)
                fixation_event = self._event("fixation.onset")
                choice_event = self._event("choice.onset")
                timeout_event = self._event("response.timeout")
                response_left_event = self._event("response.left")
                response_right_event = self._event("response.right")
                feedback_reward_event = self._event("feedback.reward")
                feedback_no_reward_event = self._event("feedback.no_reward")
                iti_event = self._event("iti.onset")
                if state.trial_in_block == 1:
                    self.send_marker_now(event_name=self._event("block.start"), metadata={"task": self.task_name, "block": state.block, "good_side": state.good_side}, block=state.block, trial=state.trial_index)
                if state.is_reversal_boundary:
                    self.send_marker_now(event_name=self._event("reversal.boundary"), metadata={"task": self.task_name, "block": state.block, "good_side": state.good_side}, block=state.block, trial=state.trial_index)

                fixation_onset = self.fixation_period(duration_s=self.task_config.fixation_s, event_name=fixation_event, block=state.block, trial=state.trial_index)
                response_data = self.wait_for_response(
                    draw_fn=self._draw_choice_screen,
                    valid_keys=self.task_config.response_keys,
                    timeout_s=self.task_config.response_timeout_s,
                    onset_event_code=None,
                    onset_label=None,
                    onset_event_name=choice_event,
                    block=state.block,
                    trial=state.trial_index,
                    metadata={"task": self.task_name, "block": state.block, "trial": state.trial_index},
                )
                self.poll_and_log_aoi(aoi_regions=self.choice_aois, block=state.block, trial=state.trial_index)
                response = response_data["response"]
                timeout = response_data["timeout"]
                lsl_codes: list[int] = [self.task_config.marker_codes[choice_event]]
                lpt_codes: list[int] = [self.task_config.marker_codes[choice_event]]
                event_keys: list[str] = [choice_event]
                fnirs_codes: list[int] = []
                choice_fnirs = self.fnirs_code_for(self.task_config.marker_codes[choice_event])
                if choice_fnirs is not None:
                    fnirs_codes.append(choice_fnirs)

                chosen_good = None
                reward = False
                prediction_error = None
                outcome_expectedness = None
                q_left = self.rl_agent.q_values["left"]
                q_right = self.rl_agent.q_values["right"]
                choice_probability_left = self.rl_agent.choice_probability_left()
                switch_from_previous = response is not None and previous_choice is not None and response != previous_choice
                trial_phase = classify_prl_trial_phase(
                    state,
                    total_blocks=self.task_config.blocks,
                    trials_per_block=self.task_config.trials_per_block,
                    early_post_reversal_trials=self.task_config.early_post_reversal_trials,
                    relearning_trials=self.task_config.relearning_trials,
                    stable_pre_reversal_trials=self.task_config.stable_pre_reversal_trials,
                )
                timeout_policy = resolve_prl_timeout_policy(timeout)
                if timeout:
                    timeout_marker = self.send_marker_now(event_name=timeout_event, metadata={"task": self.task_name, "block": state.block, "trial": state.trial_index}, block=state.block, trial=state.trial_index)
                    lsl_codes.append(timeout_marker.code if timeout_marker.lsl_sent else -1)
                    lpt_codes.append(timeout_marker.code if timeout_marker.lpt_sent else -1)
                    event_keys.append(timeout_marker.label or timeout_event)
                    if timeout_marker.fnirs_sent:
                        fnirs_codes.append(timeout_marker.payload.get("fnirs_code", -1))
                    response_event = timeout_event
                    feedback_label = "timeout"
                    feedback_event_name = self._event("feedback.timeout")
                    feedback_code = self.task_config.marker_codes[feedback_event_name]
                    self.feedback_text.text = self.task_config.timeout_feedback_text
                    self.feedback_text.color = "gold"
                else:
                    response_event_name = response_left_event if response == "left" else response_right_event
                    response_marker = self.send_marker_now(event_name=response_event_name, metadata={"task": self.task_name, "block": state.block, "trial": state.trial_index, "rt": response_data["rt"]}, block=state.block, trial=state.trial_index)
                    lsl_codes.append(response_marker.code if response_marker.lsl_sent else -1)
                    lpt_codes.append(response_marker.code if response_marker.lpt_sent else -1)
                    event_keys.append(response_marker.label or response_event_name)
                    if response_marker.fnirs_sent:
                        fnirs_codes.append(response_marker.payload.get("fnirs_code", -1))
                    response_event = response_marker.label or response_event_name
                    chosen_good, reward = self.reversal_engine.resolve_feedback_for_state(state, response)
                    prediction_error = self.rl_agent.update(response, reward)
                    previous_choice = response
                    outcome_expectedness = classify_prl_expectedness(chosen_good, reward)

                    if reward:
                        feedback_label = "reward"
                        feedback_event_name = feedback_reward_event
                        feedback_code = self.task_config.marker_codes[feedback_event_name]
                        self.feedback_text.text = f"+{self.task_config.reward_value}"
                        self.feedback_text.color = "lightgreen"
                    else:
                        feedback_label = "no_reward"
                        feedback_event_name = feedback_no_reward_event
                        feedback_code = self.task_config.marker_codes[feedback_event_name]
                        self.feedback_text.text = str(self.task_config.no_reward_value)
                        self.feedback_text.color = "tomato"

                post_choice_delay = self.sample_iti(self.task_config.post_choice_delay_range_s)
                self.present_interval(lambda: self._draw_choice_screen(selected=response), duration_s=post_choice_delay)

                feedback_onset = self.present_timed_event(
                    draw_fn=self._draw_feedback,
                    duration_s=self.task_config.feedback_s,
                    event_code=None,
                    label=None,
                    event_name=feedback_event_name,
                    block=state.block,
                    trial=state.trial_index,
                    metadata={"task": self.task_name, "block": state.block, "trial": state.trial_index, "reward": reward, "good_side": state.good_side, "chosen_good": chosen_good},
                )
                lsl_codes.append(feedback_code)
                lpt_codes.append(feedback_code)
                event_keys.append(feedback_event_name)
                feedback_fnirs = self.fnirs_code_for(feedback_code)
                if feedback_fnirs is not None:
                    fnirs_codes.append(feedback_fnirs)

                iti_duration = self.sample_iti(self.task_config.iti_range_s)
                iti_onset = self.present_timed_event(draw_fn=self.fixation.draw, duration_s=iti_duration, event_code=None, label=None, event_name=iti_event, block=state.block, trial=state.trial_index, metadata={"task": self.task_name, "block": state.block, "trial": state.trial_index, "iti_s": iti_duration})
                lsl_codes.append(self.task_config.marker_codes[iti_event])
                lpt_codes.append(self.task_config.marker_codes[iti_event])
                event_keys.append(iti_event)
                iti_fnirs = self.fnirs_code_for(self.task_config.marker_codes[iti_event])
                if iti_fnirs is not None:
                    fnirs_codes.append(iti_fnirs)

                trial_row = {
                        "participant": self.participant,
                        "session": self.session,
                        "task": self.task_name,
                        "block": state.block,
                        "trial_index": state.trial_index,
                        "condition": f"good_side_{state.good_side}",
                        "stimulus_parameters": {"good_side": state.good_side, "reward_probability_good": self.task_config.reward_probability_good, "reward_probability_bad": self.task_config.reward_probability_bad, "trial_in_block": state.trial_in_block, "is_reversal_boundary": state.is_reversal_boundary},
                        "response": response,
                        "rt": response_data["rt"],
                        "correct": chosen_good,
                        "feedback": feedback_label,
                        "timeout": timeout,
                        "fixation_onset": fixation_onset,
                        "stim_onset": response_data["onset_flip"],
                        "response_time_abs": response_data["response_abs"],
                        "feedback_onset": feedback_onset,
                        "iti_onset": iti_onset,
                        "trial_end": iti_onset + iti_duration,
                        "lsl_marker_codes": lsl_codes,
                        "lpt_marker_codes": lpt_codes,
                        "event_keys": event_keys,
                        "fnirs_marker_codes": fnirs_codes,
                        "task_specific_data": {
                            "good_side": state.good_side,
                            "reward": reward,
                            "chosen_good": chosen_good,
                            "trial_in_block": state.trial_in_block,
                            "is_reversal_boundary": state.is_reversal_boundary,
                            "trial_phase": trial_phase,
                            "outcome_expectedness": outcome_expectedness,
                            "response_event": response_event,
                            "feedback_event": feedback_event_name,
                            "q_left": q_left,
                            "q_right": q_right,
                            "prediction_error": prediction_error,
                            "choice_probability_left": choice_probability_left,
                            "switch_from_previous": switch_from_previous,
                            "rl_update_applied": timeout_policy["rl_update_applied"],
                            "counted_for_choice_dynamics": timeout_policy["counted_for_choice_dynamics"],
                            "timeout_feedback_presented": timeout_policy["timeout_feedback_presented"],
                            "exclude_trial": timeout_policy["exclude_trial"],
                            "exclude_reason": timeout_policy["exclude_reason"],
                            "invalid_response": timeout_policy["invalid_response"],
                            "first_fixation_aoi": None,
                            "last_fixation_aoi": None,
                            "dwell_left_s": None,
                            "dwell_right_s": None,
                            "dwell_asymmetry": None,
                            "exploration_after_reversal": None,
                            "aoi_summary_available": False,
                        },
                    }
                self.log_trial_row(trial_row)
                trial_rows.append(trial_row)

                if state.trial_in_block == self.task_config.trials_per_block:
                    self.send_marker_now(event_name=self._event("block.end"), metadata={"task": self.task_name, "block": state.block}, block=state.block, trial=state.trial_index)
                    if state.block < self.task_config.blocks:
                        self.show_break(block=state.block, completed_trials=state.trial_index, total_trials=total_trials)

            self.send_marker_now(event_name=self._event("experiment.end"), metadata={"task": self.task_name})
            non_timeout_rows = [row for row in trial_rows if not row["timeout"]]
            chosen_good_rate = None
            if non_timeout_rows:
                chosen_good_rate = sum(1 for row in non_timeout_rows if row["correct"]) / len(non_timeout_rows)
            early_post_rows = [row for row in non_timeout_rows if row["task_specific_data"]["trial_phase"] == "early_post_reversal"]
            late_stable_rows = [row for row in non_timeout_rows if row["task_specific_data"]["trial_phase"] in {"late_stable", "stable_pre_reversal"}]
            self.run_summary = {
                "n_trials": len(trial_rows),
                "timeout_rate": (sum(1 for row in trial_rows if row["timeout"]) / len(trial_rows)) if trial_rows else None,
                "high_probability_choice_rate": chosen_good_rate,
                "early_post_reversal_choice_rate": (sum(1 for row in early_post_rows if row["correct"]) / len(early_post_rows)) if early_post_rows else None,
                "late_stable_choice_rate": (sum(1 for row in late_stable_rows if row["correct"]) / len(late_stable_rows)) if late_stable_rows else None,
                "expected_reward_count": sum(1 for row in trial_rows if row["task_specific_data"].get("outcome_expectedness") == "expected_reward"),
                "unexpected_reward_count": sum(1 for row in trial_rows if row["task_specific_data"].get("outcome_expectedness") == "unexpected_reward"),
                "task_positioning": "main pilot for learning updates, reversal recovery, and expected versus unexpected outcomes",
            }
            self.final_status = "completed"
            self.show_message(f"{mode_prefix}PRL 任务已完成。\n\n按 {self.continue_key_label()} 结束。")
        except SafeExitRequested:
            self.final_status = "safe_exit"
            self.log_event(event_name="system.safe_exit.requested")
        finally:
            self.finalize()
